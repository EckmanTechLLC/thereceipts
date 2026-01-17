"""
Configuration management for TheReceipts backend.

Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database configuration
    POSTGRES_HOST: str = "192.168.50.10"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "thereceipts_dev"
    POSTGRES_USER: str = "thereceipts"
    POSTGRES_PASSWORD: str

    # Service configuration
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8008

    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # WebSocket configuration
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds

    # Agent pipeline configuration
    PIPELINE_TIMEOUT: int = 300  # seconds (5 minutes per agent max)
    SEMANTIC_SEARCH_THRESHOLD: float = 0.92  # Similarity threshold for cache hits (high to avoid matching related but different claims)

    # Chat configuration
    MAX_MESSAGE_LENGTH: int = 2000  # Maximum characters in a chat message
    MAX_CONVERSATION_HISTORY: int = 50  # Maximum messages to keep in history

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


# Global settings instance
settings = Settings()
