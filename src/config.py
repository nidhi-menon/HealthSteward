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

    # LLM Provider: "ollama" (default, local-first — DEC-016), "claude", or "custom"
    llm_provider: str = "ollama"

    # Anthropic API (used when llm_provider="claude")
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-5"
    anthropic_max_tokens: int = 4096

    # Anthropic judge/baseline model — used by the evaluation harness to score
    # coordination outputs (groundedness, relevance) and as the cloud-tier
    # upper baseline against local Ollama output. Deliberately a stronger tier
    # than anthropic_model to reduce self-grading bias when judging its output.
    anthropic_judge_model: str = "claude-opus-4-8"

    # Ollama (used when llm_provider="ollama" or for local LLM scoring)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Custom OpenAI-compatible provider (used when llm_provider="custom") —
    # any endpoint speaking OpenAI's /chat/completions + tool-calling format:
    # OpenAI itself, OpenRouter, Groq, Together, a self-hosted vLLM/LM Studio
    # server, etc. (DEC-016)
    custom_llm_base_url: Optional[str] = None
    custom_llm_api_key: Optional[str] = None
    custom_llm_model: Optional[str] = None

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
    # Cap on how many candidates get sent to Stage 2's sequential, unbatched
    # LLM scoring calls — provisional default, not measured against real
    # per-call latency yet. See issue #56 to ground this in an actual
    # p50/p95 measurement (and evaluate batching scoring into one call).
    context_stage2_max_candidates: int = 15

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
