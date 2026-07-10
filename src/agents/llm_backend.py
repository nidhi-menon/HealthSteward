"""Pluggable LLM backend abstraction for agentic tool-use (DEC-009, DEC-013).

Provides a single interface (`LLMBackend`) that both Claude API and local
Ollama can implement, so the agentic tool-use loop in `visit_prep.py` doesn't
need to know which provider it's talking to.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from anthropic import AsyncAnthropic
from loguru import logger

from src.config import Settings


class ToolCallParsingError(Exception):
    """Raised when a backend's tool-call response can't be parsed.

    Callers should treat this as a signal to fall back to non-agentic,
    single-shot generation rather than a hard failure (see DEC-009's
    documented caveat about unreliable tool-calling on small local models).
    """


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMTurnResult:
    """The result of one turn of a conversation with an LLM backend."""

    text: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_assistant_content: Any = None  # echoed back into the next turn's messages
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use"


class LLMBackend(ABC):
    """Common interface for a tool-calling-capable LLM provider."""

    @abstractmethod
    async def call(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMTurnResult:
        """Send messages (+ optional tool specs) and get back one turn's result."""
        ...

    @abstractmethod
    def build_assistant_message(self, result: LLMTurnResult) -> dict[str, Any]:
        """Build the assistant message to append to history after a turn."""
        ...

    @abstractmethod
    def build_tool_result_message(self, tool_call: ToolCall, result_content: str) -> dict[str, Any]:
        """Build the message representing a tool's result, to append to history."""
        ...


class ClaudeBackend(LLMBackend):
    """LLMBackend implementation wrapping the Anthropic Messages API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def call(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMTurnResult:
        kwargs: dict[str, Any] = {
            "model": self.settings.anthropic_model,
            "max_tokens": self.settings.anthropic_max_tokens,
            "system": system,
            "messages": messages,
            "temperature": 0.7,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        return LLMTurnResult(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            raw_assistant_content=response.content,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )

    def build_assistant_message(self, result: LLMTurnResult) -> dict[str, Any]:
        return {"role": "assistant", "content": result.raw_assistant_content}

    def build_tool_result_message(self, tool_call: ToolCall, result_content: str) -> dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result_content,
                }
            ],
        }


class OllamaBackend(LLMBackend):
    """LLMBackend implementation wrapping Ollama's /api/chat tool-calling support.

    Not all local models support reliable tool calling (see DEC-009). Malformed
    or missing tool-call data raises ToolCallParsingError so the caller can fall
    back to single-shot generation.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model

    async def call(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMTurnResult:
        ollama_messages = [{"role": "system", "content": system}, *messages]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": 0.7},
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=120.0) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            raise ToolCallParsingError(f"Ollama request failed: {e}") from e

        message = data.get("message", {})
        text = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls: list[ToolCall] = []
        for i, raw in enumerate(raw_tool_calls):
            try:
                fn = raw["function"]
                tool_calls.append(
                    ToolCall(id=f"ollama-call-{i}", name=fn["name"], input=fn.get("arguments") or {})
                )
            except (KeyError, TypeError) as e:
                raise ToolCallParsingError(f"Malformed tool_call from Ollama: {raw!r}") from e

        return LLMTurnResult(
            text=text,
            tool_calls=tool_calls,
            raw_assistant_content=message,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )

    def build_assistant_message(self, result: LLMTurnResult) -> dict[str, Any]:
        return {"role": "assistant", "content": result.text or "", "tool_calls": result.raw_assistant_content.get("tool_calls")}

    def build_tool_result_message(self, tool_call: ToolCall, result_content: str) -> dict[str, Any]:
        return {"role": "tool", "content": result_content}


class CustomOpenAICompatibleBackend(LLMBackend):
    """LLMBackend implementation for any OpenAI-compatible /chat/completions endpoint.

    Covers OpenAI itself, OpenRouter, Groq, Together, a self-hosted vLLM/LM
    Studio server, etc. — anything speaking the same tool-calling wire format
    Ollama already uses. Same fallback-on-malformed-tool-call behavior as
    OllamaBackend (see DEC-009's caveat about unreliable tool-calling on small
    models, which applies regardless of who's hosting the model).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = (settings.custom_llm_base_url or "").rstrip("/")
        self.model = settings.custom_llm_model
        self.api_key = settings.custom_llm_api_key

    async def call(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMTurnResult:
        chat_messages = [{"role": "system", "content": system}, *messages]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=120.0) as client:
                response = await client.post("/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            raise ToolCallParsingError(f"Custom LLM request failed: {e}") from e

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise ToolCallParsingError(f"Unexpected response shape from custom LLM: {data!r}") from e

        text = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls: list[ToolCall] = []
        for raw in raw_tool_calls:
            try:
                fn = raw["function"]
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    import json

                    args = json.loads(args) if args else {}
                tool_calls.append(ToolCall(id=raw.get("id") or fn["name"], name=fn["name"], input=args))
            except (KeyError, TypeError, ValueError) as e:
                raise ToolCallParsingError(f"Malformed tool_call from custom LLM: {raw!r}") from e

        return LLMTurnResult(
            text=text,
            tool_calls=tool_calls,
            raw_assistant_content=message,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )

    def build_assistant_message(self, result: LLMTurnResult) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": result.text or "",
            "tool_calls": result.raw_assistant_content.get("tool_calls"),
        }

    def build_tool_result_message(self, tool_call: ToolCall, result_content: str) -> dict[str, Any]:
        return {"role": "tool", "tool_call_id": tool_call.id, "content": result_content}


def get_llm_backend(settings: Settings) -> LLMBackend:
    """Get the configured LLMBackend implementation."""
    if settings.llm_provider == "ollama":
        logger.debug("Using Ollama backend for agentic loop")
        return OllamaBackend(settings)
    if settings.llm_provider == "custom":
        logger.debug("Using custom OpenAI-compatible backend for agentic loop")
        return CustomOpenAICompatibleBackend(settings)
    logger.debug("Using Claude backend for agentic loop")
    return ClaudeBackend(settings)
