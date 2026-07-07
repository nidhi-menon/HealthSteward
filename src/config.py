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

    # LLM Provider: "claude" or "ollama"
    llm_provider: str = "claude"

    # Anthropic API (used when llm_provider="claude")
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 4096

    # Ollama (used when llm_provider="ollama" or for local LLM scoring)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # AVS PDF Parser
    avs_parser_model: str = "qwen2.5:7b"
    avs_scan_path: str = "data/avs"

    # Anonymization
    use_anonymization: bool = True  # Anonymize data before sending to LLM
    use_ner_anonymization: bool = True  # Use spaCy NER for name detection

    # Context Selection
    context_stage2_threshold: int = 5  # Run LLM scoring if more than N visits
    context_relevance_cutoff: float = 7.0  # Keep visits scoring >= this
    context_max_tokens: int = 2000  # Max tokens for visit context

    # Agentic Visit Prep (DEC-009 / DEC-013)
    agent_tool_use_enabled: bool = True  # Kill switch: falls back to single-shot if False
    agent_max_turns: int = 6  # Max tool-call round trips before falling back to single-shot

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
