"""Pluggable LLM backend abstraction for agentic tool-use (DEC-009, DEC-013, DEC-016).

Provides a single interface (`LLMBackend`) that Claude API, local Ollama, and
any custom OpenAI-compatible provider can implement, so the agentic tool-use
loop in `visit_prep.py` doesn't need to know which provider it's talking to.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from anthropic import AsyncAnthropic
from loguru import logger

from src.config import Settings

# Total wall-clock ceiling for one _OpenAIStyleHTTPBackend.call — distinct
# from httpx.Timeout's per-chunk read timeout below, which a slow/trickling
# response can bypass indefinitely. See _OpenAIStyleHTTPBackend.call's
# docstring-adjacent comment for how this was found.
_TOTAL_CALL_TIMEOUT_SECONDS = 150.0


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
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class LLMBackend(ABC):
    """Common interface for a tool-calling-capable LLM provider."""

    @abstractmethod
    async def call(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> LLMTurnResult:
        """Send messages (+ optional tool specs) and get back one turn's result.

        temperature defaults to production's existing 0.7 — the eval harness
        (issue #29) passes 0.0 explicitly to make eval runs reproducible
        across repeats, since the loop's own non-determinism otherwise makes
        a single eval run's pass/fail meaningless.
        """
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
        temperature: float = 0.7,
    ) -> LLMTurnResult:
        kwargs: dict[str, Any] = {
            "model": self.settings.anthropic_model,
            "max_tokens": self.settings.anthropic_max_tokens,
            "system": system,
            "messages": messages,
            "temperature": temperature,
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
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
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


class _OpenAIStyleHTTPBackend(LLMBackend):
    """Shared implementation for backends that speak OpenAI-style tool-calling
    over HTTP: same request/response shape, same tool-call-argument parsing
    (including coercing a JSON-string `arguments` field, which some
    OpenAI-compatible servers return instead of a parsed object). Subclasses
    only need to say where the message lives in the response envelope, what
    endpoint path to hit, and how to synthesize a tool-call id if the
    provider doesn't supply one.

    Not all models support reliable tool calling (see DEC-009). Malformed or
    missing tool-call data raises ToolCallParsingError so the caller can fall
    back to single-shot generation.
    """

    _endpoint_path: str
    _error_label: str

    def __init__(self, base_url: str, model: Optional[str], headers: Optional[dict[str, str]] = None):
        self.base_url = base_url
        self.model = model
        self.headers = headers or {}

    def _extract_message(self, data: dict[str, Any]) -> dict[str, Any]:
        """Pull the assistant message out of the raw response body."""
        raise NotImplementedError

    def _tool_call_id(self, index: int, raw: dict[str, Any], fn: dict[str, Any]) -> str:
        """Synthesize a tool-call id when the response doesn't include one."""
        return f"call-{index}"

    def _sampling_payload(self, temperature: float) -> dict[str, Any]:
        """Provider-specific payload fields for sampling + streaming.

        Default: OpenAI-compatible /chat/completions shape (top-level
        `temperature`, explicit `stream: false` so a response is always a
        single JSON body rather than depending on the server's streaming
        default). OllamaBackend overrides this — Ollama's native /api/chat
        takes `temperature` nested under `options`, not top-level, and
        defaults to `stream: true` if unset, which previously made
        `response.json()` raise `json.JSONDecodeError: Extra data` on any
        real (multi-chunk) response, silently degrading every Ollama-backed
        call straight to the outer fallback response instead of either
        succeeding or reaching DEC-013's single-shot fallback.
        """
        return {"temperature": temperature, "stream": False}

    def _context_budget_warning(
        self, chat_messages: list[dict[str, Any]], tools: Optional[list[dict[str, Any]]]
    ) -> Optional[str]:
        """Return a warning message if this request is likely to exceed the
        provider's context window, or None if there's no such window to check
        (default: no-op). Overridden by OllamaBackend, where `num_ctx` is an
        explicit, known ceiling — see issue #71.
        """
        return None

    async def call(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> LLMTurnResult:
        chat_messages = [{"role": "system", "content": system}, *messages]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            **self._sampling_payload(temperature),
        }
        if tools:
            payload["tools"] = tools

        budget_warning = self._context_budget_warning(chat_messages, tools)
        if budget_warning:
            logger.warning(budget_warning)

        async def _do_request() -> Any:
            # Fail fast (~5s) on an unreachable/hung host at the connect
            # phase, while still allowing generous time for generation once
            # connected — a misconfigured or unreachable endpoint shouldn't
            # block a request before falling back.
            timeout = httpx.Timeout(120.0, connect=5.0)
            async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout) as client:
                response = await client.post(self._endpoint_path, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()

        try:
            # httpx.Timeout(120.0, ...) only bounds the gap between chunks of
            # a streaming/slow response, not total request duration — a
            # response that keeps trickling data can run unbounded with no
            # error raised (found running the eval harness (#29) against a
            # real local model: one call ran 30+ minutes on an active
            # connection with no timeout, no log, no fallback triggered).
            # Wrapping in wait_for enforces an actual wall-clock ceiling.
            data = await asyncio.wait_for(_do_request(), timeout=_TOTAL_CALL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as e:
            raise ToolCallParsingError(
                f"{self._error_label} request exceeded {_TOTAL_CALL_TIMEOUT_SECONDS}s total wall-clock time"
            ) from e
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            raise ToolCallParsingError(f"{self._error_label} request failed: {e}") from e

        try:
            message = self._extract_message(data)
        except (KeyError, IndexError, TypeError) as e:
            raise ToolCallParsingError(f"Unexpected response shape from {self._error_label}: {data!r}") from e

        text = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls: list[ToolCall] = []
        for i, raw in enumerate(raw_tool_calls):
            try:
                fn = raw["function"]
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args) if args else {}
                tool_calls.append(
                    ToolCall(id=raw.get("id") or self._tool_call_id(i, raw, fn), name=fn["name"], input=args)
                )
            except (KeyError, TypeError, ValueError) as e:
                raise ToolCallParsingError(f"Malformed tool_call from {self._error_label}: {raw!r}") from e

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


# Rough chars-per-token ratio for estimating request size against `num_ctx`
# without a real tokenizer per model. English text is commonly ~4 chars/token;
# this is a heuristic early-warning signal, not a precise count — it exists to
# make an already-likely-truncated request visible in logs (issue #71's
# "fails loudly" requirement), not to gate/block the request.
_CHARS_PER_TOKEN_ESTIMATE = 4
# Warn once the estimate crosses this fraction of num_ctx, leaving headroom
# for the model's own response tokens within the same context window.
_CONTEXT_BUDGET_WARNING_THRESHOLD = 0.75


class OllamaBackend(_OpenAIStyleHTTPBackend):
    """LLMBackend implementation wrapping Ollama's /api/chat tool-calling support."""

    _endpoint_path = "/api/chat"
    _error_label = "Ollama"

    def __init__(self, settings: Settings):
        self.settings = settings
        super().__init__(base_url=settings.ollama_base_url, model=settings.ollama_model)

    def _extract_message(self, data: dict[str, Any]) -> dict[str, Any]:
        return data.get("message", {})

    def _tool_call_id(self, index: int, raw: dict[str, Any], fn: dict[str, Any]) -> str:
        return f"ollama-call-{index}"

    def _sampling_payload(self, temperature: float) -> dict[str, Any]:
        return {
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": self.settings.ollama_num_ctx},
        }

    def _context_budget_warning(
        self, chat_messages: list[dict[str, Any]], tools: Optional[list[dict[str, Any]]]
    ) -> Optional[str]:
        char_count = sum(len(json.dumps(m)) for m in chat_messages)
        if tools:
            char_count += sum(len(json.dumps(t)) for t in tools)
        estimated_tokens = char_count // _CHARS_PER_TOKEN_ESTIMATE
        threshold = int(self.settings.ollama_num_ctx * _CONTEXT_BUDGET_WARNING_THRESHOLD)
        if estimated_tokens > threshold:
            return (
                f"Ollama request estimated at ~{estimated_tokens} tokens, over "
                f"{int(_CONTEXT_BUDGET_WARNING_THRESHOLD * 100)}% of ollama_num_ctx "
                f"({self.settings.ollama_num_ctx}) — response quality may silently "
                f"degrade from context truncation. Consider raising ollama_num_ctx "
                f"or reducing context_max_tokens/agent_max_turns."
            )
        return None


class CustomOpenAICompatibleBackend(_OpenAIStyleHTTPBackend):
    """LLMBackend implementation for any OpenAI-compatible /chat/completions endpoint.

    Covers OpenAI itself, OpenRouter, Groq, Together, a self-hosted vLLM/LM
    Studio server, etc. — anything speaking the same tool-calling wire format
    Ollama already uses.
    """

    _endpoint_path = "/chat/completions"
    _error_label = "custom LLM"

    def __init__(self, settings: Settings):
        self.settings = settings
        base_url = (settings.custom_llm_base_url or "").rstrip("/")
        headers = {"Authorization": f"Bearer {settings.custom_llm_api_key}"} if settings.custom_llm_api_key else {}
        super().__init__(base_url=base_url, model=settings.custom_llm_model, headers=headers)

    def _extract_message(self, data: dict[str, Any]) -> dict[str, Any]:
        return data["choices"][0]["message"]

    def _tool_call_id(self, index: int, raw: dict[str, Any], fn: dict[str, Any]) -> str:
        return fn["name"]


def uses_openai_style_wire_format(provider: str) -> bool:
    """Whether a provider speaks the OpenAI-style tool-calling wire format.

    Single source of truth for the ollama/custom vs. claude split — used by
    both `get_llm_backend` (which backend class) and
    `get_tools_for_provider` (which tool-spec shape) so they can't disagree
    on an unrecognized `llm_provider` value the way two independent
    `== "ollama"` / `== "claude"` checks could.
    """
    return provider in ("ollama", "custom")


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
