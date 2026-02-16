"""
Application configuration.

All configuration is loaded from environment variables.
Never hardcode secrets or connection strings in code.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Core Banking Simulator"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5432/core_banking"
    )

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


@lru_cache()
def get_settings() -> Settings:
    """
    Return cached settings instance.

    Using lru_cache means the Settings object is created once
    and reused for all subsequent calls. This avoids reading
    environment variables repeatedly.
    """
    return Settings()
