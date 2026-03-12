"""
Configuration management module for FastAPI Proxy Service.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


class Config:
    """Application configuration."""

    # API Authentication
    PROXY_API_TOKEN: str = os.getenv("PROXY_API_TOKEN", "dev_token_123")

    # Proxy Pool Configuration
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "600"))
    TARGET_COUNT: int = 200
    TIMEOUT_SEC: int = 3
    MAX_THREADS: int = 2000

    # Proxy Forwarding Configuration
    FORWARD_TIMEOUT: int = int(os.getenv("FORWARD_TIMEOUT", "30"))
    FORWARD_MAX_RETRIES: int = int(os.getenv("FORWARD_MAX_RETRIES", "3"))
    FORWARD_MAX_BODY_SIZE: int = int(os.getenv("FORWARD_MAX_BODY_SIZE", str(10 * 1024 * 1024)))  # 10MB

    # Self Proxy Configuration (used when proxy_type="self")
    # Format: http://user:pass@host:port or socks5://user:pass@host:port
    # If empty, requests will be forwarded directly without proxy
    SELF_PROXY_HOST: str = os.getenv("SELF_PROXY_HOST", "")

    # Validation
    VALIDATION_URL: str = "https://www.youtube.com"

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Validate configuration and log warnings."""
        if cls.PROXY_API_TOKEN == "dev_token_123":
            print("⚠️  WARNING: Using default dev token. Set PROXY_API_TOKEN environment variable for production!")
        if cls.PROXY_API_TOKEN == "":
            raise ValueError("PROXY_API_TOKEN cannot be empty!")


# Initialize configuration
config = Config()
config.validate()