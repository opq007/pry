"""
API routes for FastAPI Proxy Service.
"""
from fastapi import APIRouter, Depends
from datetime import datetime
from .auth import verify_token

router = APIRouter()

# Global proxy pool instance (will be set by main.py)
_proxy_pool = None


def get_proxy_pool():
    """Dependency injection for proxy pool."""
    global _proxy_pool
    return _proxy_pool


def set_proxy_pool(pool):
    """Set the global proxy pool instance."""
    global _proxy_pool
    _proxy_pool = pool


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