"""
FastAPI Proxy Service - Startup Script.
Run this file from the project root directory to start the service.
"""
import uvicorn
import os

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "7860")),
        log_level="info",
        reload=False
    )