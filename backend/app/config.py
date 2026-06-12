"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Support AI"
    DEBUG: bool = False
    VERSION: str = "0.1.0"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    DATABASE_URL: str = (
        "postgresql+asyncpg://support_ai:support_ai@localhost:5432/support_ai"
    )
    MCP_TELEMETRY_SERVER_URL: str = "http://localhost:8001"
    MCP_BILLING_SERVER_URL: str = "http://localhost:8002"
    MCP_REQUEST_TIMEOUT: float = 30.0

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
