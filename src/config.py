"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = "development"

    # Anthropic API
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 4096

    # Database
    database_url: str = "sqlite+aiosqlite:///data/healthsteward.db"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/healthsteward.log"
    log_rotation: str = "10 MB"
    log_retention: str = "7 days"

    # Application
    app_name: str = "HealthSteward"
    app_version: str = "0.1.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
