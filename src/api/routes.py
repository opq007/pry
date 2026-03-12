"""
API routes for FastAPI Proxy Service.
Supports streaming responses for OpenAI-compatible APIs.
"""
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import Response, StreamingResponse
from datetime import datetime
from typing import Optional
import json
import logging
from .auth import verify_token
from ..core.proxy_forwarder import ProxyForwarder
from ..core.config import config

logger = logging.getLogger(__name__)

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


def _is_stream_response(response, is_stream_mode: bool = False) -> bool:
    """
    Check if response is a streaming response.

    Detection strategy:
    1. Check content-type header for text/event-stream
    2. Fallback (only when not in stream mode): check if response content
       starts with "data:" (SSE format). This handles platforms like airforce
       that return SSE but may not set correct content-type header.

    Args:
        response: The requests Response object
        is_stream_mode: True if the request was made with stream=True.
                       When True, we cannot safely read response.content.

    Returns:
        True if response is streaming (SSE)
    """
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type:
        return True

    # Fallback: detect SSE by content pattern (only when not in stream mode)
    # This is safe because response.content is already cached
    if not is_stream_mode:
        try:
            # response._content is None if not read yet, otherwise cached
            if response._content is not None:
                peek_size = 100
                content = response.content[:peek_size]
                content_str = content.decode('utf-8', errors='ignore').strip()
                # Check for SSE patterns: "data:" or ": " (SSE comment)
                if content_str.startswith('data:') or content_str.startswith(':'):
                    return True
        except Exception:
            pass

    return False


def _parse_sse_content(content: bytes) -> list:
    """
    Parse SSE content and extract JSON data lines.

    Args:
        content: SSE response content as bytes

    Returns:
        List of parsed JSON objects from SSE data lines
    """
    results = []
    try:
        content_str = content.decode('utf-8', errors='ignore')
        for line in content_str.split('\n'):
            line = line.strip()
            # Skip empty lines, comments, and [DONE] marker
            if not line or line.startswith(':') or line == 'data: [DONE]':
                continue
            if line.startswith('data: '):
                json_str = line[6:]  # Remove "data: " prefix
                try:
                    data = json.loads(json_str)
                    results.append(data)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return results


def _convert_sse_to_openai_json(sse_data: list) -> dict:
    """
    Convert SSE data list to standard OpenAI image generation response format.

    OpenAI images/generations response format:
    {
        "created": timestamp,
        "data": [
            {"url": "https://..."} or {"b64_json": "..."}
        ]
    }

    Args:
        sse_data: List of parsed JSON objects from SSE stream

    Returns:
        Standard OpenAI format response dict
    """
    # Collect all image URLs/data from SSE events
    images = []
    created = None

    for item in sse_data:
        # Handle various SSE response formats
        if isinstance(item, dict):
            # Try to extract image data from common patterns
            # Pattern 1: Direct image data
            if 'url' in item:
                images.append({'url': item['url']})
            elif 'b64_json' in item:
                images.append({'b64_json': item['b64_json']})
            # Pattern 2: Nested in 'data' field
            elif 'data' in item:
                data = item['data']
                if isinstance(data, list):
                    for d in data:
                        if isinstance(d, dict):
                            if 'url' in d:
                                images.append({'url': d['url']})
                            elif 'b64_json' in d:
                                images.append({'b64_json': d['b64_json']})
                elif isinstance(data, dict):
                    if 'url' in data:
                        images.append({'url': data['url']})
                    elif 'b64_json' in data:
                        images.append({'b64_json': data['b64_json']})
            # Pattern 3: image_url field
            elif 'image_url' in item:
                img_url = item['image_url']
                if isinstance(img_url, dict) and 'url' in img_url:
                    images.append({'url': img_url['url']})
                elif isinstance(img_url, str):
                    images.append({'url': img_url})
            # Capture created timestamp if available
            if 'created' in item and created is None:
                created = item['created']

    # Build OpenAI compatible response
    if created is None:
        import time
        created = int(time.time())

    return {
        "created": created,
        "data": images if images else []
    }


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

        # Stream mode: yield chunks iteratively
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

    Supports HTTP, SOCKS5 proxies, and self-configured proxy.

    **Streaming Support**: Automatically detects and handles OpenAI-style
    streaming requests (SSE). The response will be streamed chunk by chunk.

    **Fallback**: If proxy pool is empty, falls back to direct request.

    **Authentication (use ONE of these methods):**
    - `X-Proxy-Authorization: Bearer <token>` header (recommended)
    - `?proxy_token=<token>` query parameter

    **Query Parameters:**
    - url: Target URL (required)
    - proxy_type: "http", "socks5", "self", or "direct" (default: "http")
        - "http": Use HTTP proxy from pool
        - "socks5": Use SOCKS5 proxy from pool
        - "self": Use self-configured proxy from SELF_PROXY_HOST env var,
                  or direct connection if not configured
        - "direct": Direct connection without any proxy
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
    if proxy_type.lower() not in ["http", "socks5", "self", "direct"]:
        raise HTTPException(status_code=400, detail="proxy_type must be 'http', 'socks5', 'self', or 'direct'")

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

    # Handle "self" and "direct" proxy types - bypass proxy pool
    if proxy_type.lower() in ["self", "direct"]:
        import requests as direct_requests
        
        proxies = None
        proxy_used = "DIRECT"
        
        if proxy_type.lower() == "self":
            self_proxy = config.SELF_PROXY_HOST.strip()
            if self_proxy:
                # Parse self proxy URL to determine type and build proxy config
                # Expected format: http://user:pass@host:port or socks5://user:pass@host:port
                if self_proxy.startswith("socks5://"):
                    proxies = {
                        "http": self_proxy,
                        "https": self_proxy
                    }
                elif self_proxy.startswith("http://") or self_proxy.startswith("https://"):
                    proxies = {
                        "http": self_proxy,
                        "https": self_proxy
                    }
                else:
                    # Assume HTTP proxy if no scheme specified
                    proxies = {
                        "http": f"http://{self_proxy}",
                        "https": f"http://{self_proxy}"
                    }
                # Extract proxy address for display (hide credentials)
                proxy_display = self_proxy
                if "@" in proxy_display:
                    # Hide credentials: http://user:pass@host:port -> host:port
                    proxy_display = proxy_display.split("@")[-1]
                # Remove scheme prefix for display
                for scheme in ["socks5://", "http://", "https://"]:
                    if proxy_display.startswith(scheme):
                        proxy_display = proxy_display[len(scheme):]
                        break
                proxy_used = f"SELF:{proxy_display}"
        # For "direct" type: proxies remains None, proxy_used remains "DIRECT"
        
        # Prepare timeout
        req_timeout = timeout if timeout else config.FORWARD_TIMEOUT
        if is_stream:
            req_timeout = (req_timeout, None)  # No read timeout for streaming
        
        try:
            response = direct_requests.request(
                method=request.method.upper(),
                url=url,
                headers=headers,
                data=body,
                proxies=proxies,
                timeout=req_timeout,
                allow_redirects=True,
                stream=is_stream
            )
            proxy_or_error = proxy_used
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Direct request failed: {str(e)}")
    else:
        # Forward the request using proxy pool (with fallback to direct request)
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

    # Check if response is streaming (SSE) - with fallback detection
    is_stream_response = _is_stream_response(response, is_stream_mode=is_stream)

    if is_stream:
        # Request explicitly asked for stream, return SSE as-is
        return StreamingResponse(
            _stream_generator(response, proxy_or_error),
            status_code=response.status_code,
            headers=response_headers,
            media_type="text/event-stream"
        )
    elif is_stream_response:
        # Fallback: Request expected non-stream, but got SSE response
        # Convert SSE to standard OpenAI JSON format
        original_content = response.content
        original_content_str = original_content.decode('utf-8', errors='ignore') if original_content else ''
        
        logger.info(f"[SSE-to-JSON] URL: {url}")
        logger.info(f"[SSE-to-JSON] Original SSE content ({len(original_content)} bytes):\n{original_content_str[:2000]}{'...' if len(original_content_str) > 2000 else ''}")
        
        sse_data = _parse_sse_content(original_content)
        logger.info(f"[SSE-to-JSON] Parsed {len(sse_data)} SSE events: {json.dumps(sse_data, ensure_ascii=False)[:1000]}")
        
        json_response = _convert_sse_to_openai_json(sse_data)
        logger.info(f"[SSE-to-JSON] Converted OpenAI response: {json.dumps(json_response, ensure_ascii=False)}")
        
        response_headers["X-Proxy-Used"] = proxy_or_error
        response_headers["X-SSE-Converted"] = "true"  # Indicate conversion happened

        return Response(
            content=json.dumps(json_response),
            status_code=response.status_code,
            headers=response_headers,
            media_type="application/json"
        )
    else:
        # Standard non-streaming response
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