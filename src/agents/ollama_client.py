"""Ollama client for local LLM inference.

This module provides an async client for Ollama, enabling:
- Local LLM inference for maximum privacy
- Relevance scoring in context selection (Stage 2)
- Summarization for token budget management (Stage 3)
- Full visit prep generation as alternative to Claude

Per DEC-006, Ollama is supported as a privacy-first alternative to Claude API.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx

from src.config import get_settings


@dataclass
class OllamaResponse:
    """Response from Ollama API."""

    model: str
    response: str
    done: bool
    context: Optional[list] = None
    total_duration: Optional[int] = None
    eval_count: Optional[int] = None


class OllamaClient:
    """Async client for Ollama local LLM inference."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """Initialize the Ollama client.

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434)
            model: Default model to use (default: from settings or llama3.2)
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.base_url = base_url or getattr(settings, 'ollama_base_url', 'http://localhost:11434')
        self.model = model or getattr(settings, 'ollama_model', 'llama3.2')
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def is_available(self) -> bool:
        """Check if Ollama is available and responsive.

        Returns:
            True if Ollama is running and accessible
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False

    async def list_models(self) -> list[str]:
        """List available models.

        Returns:
            List of model names
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except (httpx.RequestError, httpx.HTTPStatusError):
            return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt
            model: Model to use (defaults to instance model)
            system: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text response
        """
        client = await self._get_client()

        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if system:
            payload["system"] = system

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()

        data = response.json()
        return data.get("response", "")

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Chat with the LLM using message history.

        Args:
            messages: List of messages with 'role' and 'content'
            model: Model to use (defaults to instance model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            The assistant's response text
        """
        client = await self._get_client()

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()

        data = response.json()
        return data.get("message", {}).get("content", "")


# Module-level convenience
_default_client: Optional[OllamaClient] = None


async def get_ollama_client() -> Optional[OllamaClient]:
    """Get the Ollama client if available.

    Returns:
        OllamaClient if Ollama is available, None otherwise
    """
    global _default_client

    if _default_client is None:
        _default_client = OllamaClient()

    if await _default_client.is_available():
        return _default_client

    return None


async def check_ollama_available() -> bool:
    """Check if Ollama is available.

    Returns:
        True if Ollama is running and accessible
    """
    client = OllamaClient()
    try:
        return await client.is_available()
    finally:
        await client.close()
