"""
API routes for FastAPI Proxy Service.
Supports streaming responses for OpenAI-compatible APIs.
"""
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import Response, StreamingResponse
from datetime import datetime
from typing import Optional
import json
from .auth import verify_token
from ..core.proxy_forwarder import ProxyForwarder
from ..core.config import config

router = APIRouter()

# Global proxy pool instance (will be set by main.py)
_proxy_pool = None
_proxy_forwarder = None


def get_proxy_pool():
    """Dependency injection for proxy pool."""
    global _proxy_pool
    return _proxy_pool


def set_proxy_pool(pool):
    """Set the global proxy pool instance."""
    global _proxy_pool
    global _proxy_forwarder
    _proxy_pool = pool
    _proxy_forwarder = ProxyForwarder(pool)


def get_proxy_forwarder():
    """Dependency injection for proxy forwarder."""
    global _proxy_forwarder
    return _proxy_forwarder


@router.get("/api/proxies")
async def get_proxies(token = Depends(verify_token), pool = Depends(get_proxy_pool)):
    """
    Get list of valid proxies.

    Requires Bearer token authentication.

    Returns:
        JSON response with proxy list and metadata
    """
    proxies = pool.get_proxies()
    return {
        "proxies": proxies,
        "last_updated": pool.last_updated,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def _is_stream_request(headers: dict, body: bytes) -> bool:
    """
    Detect if request is a streaming request.

    Checks:
    1. Accept header for text/event-stream
    2. Request body contains "stream": true (OpenAI style)
    3. Request body contains "sse": true (airforce and other platforms style)

    Args:
        headers: Request headers dict
        body: Request body bytes

    Returns:
        True if this is a streaming request
    """
    # Check Accept header
    accept = headers.get("accept", "").lower()
    if "text/event-stream" in accept:
        return True

    # Check body for stream/sse flags (OpenAI and alternative API styles)
    if body:
        try:
            body_str = body.decode("utf-8") if isinstance(body, bytes) else body
            body_json = json.loads(body_str)
            # OpenAI style: stream: true
            if body_json.get("stream") is True:
                return True
            # Alternative style (airforce, etc.): sse: true
            if body_json.get("sse") is True:
                return True
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return False


def _is_stream_response(response) -> bool:
    """
    Check if response is a streaming response.

    Args:
        response: The requests Response object

    Returns:
        True if response is streaming (SSE)
    """
    content_type = response.headers.get("content-type", "").lower()
    return "text/event-stream" in content_type


def _stream_generator(response, proxy_used: str):
    """
    Generator that yields response chunks for streaming.

    Args:
        response: The requests Response object with stream=True
        proxy_used: The proxy that was used (for header injection)

    Yields:
        Response chunks as bytes
    """
    try:
        # First, yield SSE comment with proxy info (non-intrusive)
        yield f": proxy-used: {proxy_used}\n\n".encode("utf-8")
        
        # Then yield the actual response chunks
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                yield chunk
    finally:
        response.close()


@router.api_route("/api/proxy/forward", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def forward_request(
    request: Request,
    url: str = Query(..., description="Target URL to forward request to"),
    proxy_type: str = Query("http", description="Proxy type: 'http' or 'socks5'"),
    timeout: Optional[int] = Query(None, description="Request timeout in seconds"),
    token = Depends(verify_token),
    forwarder = Depends(get_proxy_forwarder),
    pool = Depends(get_proxy_pool)
):
    """
    Forward HTTP request through proxy pool.

    This endpoint acts as a proxy forwarder. It receives a request,
    selects a proxy from the pool using round-robin, and forwards
    the request to the target URL.

    Supports both HTTP and SOCKS5 proxies.

    **Streaming Support**: Automatically detects and handles OpenAI-style
    streaming requests (SSE). The response will be streamed chunk by chunk.

    **Fallback**: If proxy pool is empty, falls back to direct request.

    **Authentication (use ONE of these methods):**
    - `X-Proxy-Authorization: Bearer <token>` header (recommended)
    - `?proxy_token=<token>` query parameter

    **Query Parameters:**
    - url: Target URL (required)
    - proxy_type: "http" or "socks5" (default: "http")
    - timeout: Request timeout in seconds (default: from config)

    **Request Headers:**
    - All headers are forwarded to target, INCLUDING Authorization
    - Only X-Proxy-Authorization is removed (used for proxy auth only)

    **Response Headers:**
    - X-Proxy-Used: The proxy used (e.g., "1.2.3.4:8080") or "DIRECT" if fallback
    - For streaming responses, proxy info is sent as SSE comment: `: proxy-used: xxx`

    **Response:**
    - Returns the target response with status code, headers, and body
    - Streaming responses are returned as Server-Sent Events (SSE)
    """
    # Validate proxy type
    if proxy_type.lower() not in ["http", "socks5"]:
        raise HTTPException(status_code=400, detail="proxy_type must be 'http' or 'socks5'")

    # Get request headers
    # Remove only proxy-specific headers and host, keep Authorization for target
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("x-proxy-authorization", None)  # Remove proxy auth header

    # Get request body
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
        if len(body) > config.FORWARD_MAX_BODY_SIZE:
            raise HTTPException(status_code=413, detail="Request body too large")

    # Detect if this is a streaming request
    is_stream = _is_stream_request(headers, body)

    # Forward the request (with fallback to direct request)
    response, proxy_or_error = forwarder.forward_request(
        method=request.method,
        url=url,
        headers=headers,
        body=body,
        proxy_type=proxy_type.lower(),
        timeout=timeout,
        max_retries=config.FORWARD_MAX_RETRIES,
        fallback_direct=True,
        stream=is_stream  # Pass stream flag
    )

    if response is None:
        raise HTTPException(status_code=502, detail=f"Request failed: {proxy_or_error}")

    # Build response headers
    excluded_headers = {"content-encoding", "transfer-encoding", "connection"}
    response_headers = {
        k: v for k, v in response.headers.items()
        if k.lower() not in excluded_headers
    }

    # Check if response is streaming (SSE)
    is_stream_response = _is_stream_response(response)

    if is_stream_response or is_stream:
        # For streaming responses, use StreamingResponse
        # Inject proxy info as SSE comment in the stream
        return StreamingResponse(
            _stream_generator(response, proxy_or_error),
            status_code=response.status_code,
            headers=response_headers,
            media_type="text/event-stream"
        )
    else:
        # For non-streaming responses, add proxy info header
        response_headers["X-Proxy-Used"] = proxy_or_error

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type")
        )


@router.get("/api/proxy/status")
async def get_forward_status(
    token = Depends(verify_token),
    pool = Depends(get_proxy_pool)
):
    """
    Get proxy forwarding status.

    Returns:
        JSON response with proxy pool status and configuration
    """
    status = pool.get_status()
    status["forward_config"] = {
        "timeout": config.FORWARD_TIMEOUT,
        "max_retries": config.FORWARD_MAX_RETRIES,
        "max_body_size": config.FORWARD_MAX_BODY_SIZE
    }
    return status