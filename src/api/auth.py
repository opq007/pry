"""
Authentication module for Bearer Token verification.

Supports multiple authentication methods to avoid conflict with target server's Authorization:
1. X-Proxy-Authorization header (recommended): X-Proxy-Authorization: Bearer <token>
2. proxy_token query parameter: ?proxy_token=<token>
"""
from fastapi import HTTPException, Request, Query, Depends
from typing import Optional
from ..core.config import config


async def verify_token(
    request: Request,
    proxy_token: Optional[str] = Query(None, description="Proxy authentication token (alternative to header)")
):
    """
    Verify authentication token.

    Supports two methods (priority order):
    1. X-Proxy-Authorization header
    2. proxy_token query parameter

    Args:
        request: FastAPI Request object
        proxy_token: Token from query parameter

    Returns:
        True if token is valid

    Raises:
        HTTPException: If token is invalid or missing
    """
    token = None

    # Priority 1: X-Proxy-Authorization header (recommended for forwarding)
    auth_header = request.headers.get("X-Proxy-Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # Priority 2: proxy_token query parameter
    elif proxy_token:
        token = proxy_token

    # No valid token found
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication. Use 'X-Proxy-Authorization: Bearer <token>' header or 'proxy_token' query parameter",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token != config.PROXY_API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True