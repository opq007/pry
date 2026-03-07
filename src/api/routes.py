"""
API routes for FastAPI Proxy Service.
"""
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import Response
from datetime import datetime
from typing import Optional
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

    **Response:**
    - Returns the target response with status code, headers, and body
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

    # Forward the request (with fallback to direct request)
    response, proxy_or_error = forwarder.forward_request(
        method=request.method,
        url=url,
        headers=headers,
        body=body,
        proxy_type=proxy_type.lower(),
        timeout=timeout,
        max_retries=config.FORWARD_MAX_RETRIES,
        fallback_direct=True
    )

    if response is None:
        raise HTTPException(status_code=502, detail=f"Request failed: {proxy_or_error}")

    # Build response headers
    excluded_headers = {"content-encoding", "transfer-encoding", "connection"}
    response_headers = {
        k: v for k, v in response.headers.items()
        if k.lower() not in excluded_headers
    }
    # Add proxy info header
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