"""
Authentication module for Bearer Token verification.
"""
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.config import config

security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verify authentication token.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        True if token is valid

    Raises:
        HTTPException: If token is invalid
    """
    if credentials.credentials != config.PROXY_API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True