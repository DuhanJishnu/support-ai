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
    MCP_TELEMETRY_SERVER_URL: str = "http://telemetry:8001/sse"
    MCP_BILLING_SERVER_URL: str = "http://billing:8002/sse"
    MCP_SERVER_URLS: list[str] = []
    MCP_REQUEST_TIMEOUT: float = 30.0

    # LLM settings
    GOOGLE_API_KEY_DEFAULT: str = ""
    GOOGLE_API_KEY: str = GOOGLE_API_KEY_DEFAULT
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    # Ollama settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4:12b"
    USE_OLLAMA: bool = True

    @property
    def is_gemini_available(self) -> bool:
        """Check if a non-default Gemini API key is provided."""
        return bool(
            self.GOOGLE_API_KEY and self.GOOGLE_API_KEY != self.GOOGLE_API_KEY_DEFAULT
        )

    @property
    def mcp_server_urls(self) -> list[str]:
        """Return configured MCP server URLs, preserving existing env vars."""
        return self.MCP_SERVER_URLS or [
            self.MCP_TELEMETRY_SERVER_URL,
            self.MCP_BILLING_SERVER_URL,
        ]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
