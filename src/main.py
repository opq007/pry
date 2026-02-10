"""
FastAPI Proxy Service - Main Application.
"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.proxy_pool import ProxyPool
from .core.worker import ProxyWorker
from .core.config import config
from .api.routes import router, set_proxy_pool

# Global start time for uptime tracking
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    print("Starting background worker...")
    worker.start()
    print("API server ready!")
    yield
    # Shutdown
    print("Stopping background worker...")
    worker.stop()
    print("API server stopped.")


# Initialize FastAPI app
app = FastAPI(
    title="Proxy API Service",
    description="RESTful API for retrieving validated proxy servers",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize proxy pool and worker
proxy_pool = ProxyPool(target_count=config.TARGET_COUNT)
worker = ProxyWorker(proxy_pool)

# Set proxy pool for routes
set_proxy_pool(proxy_pool)

# Register routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting Proxy API Service on {config.HOST}:{config.PORT}")
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower()
    )