"""Tests for the pluggable LLM backend abstraction (src/agents/llm_backend.py)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agents.llm_backend import (
    ClaudeBackend,
    CustomOpenAICompatibleBackend,
    OllamaBackend,
    ToolCallParsingError,
    get_llm_backend,
    uses_openai_style_wire_format,
)
from src.agents.tools import get_tools_for_provider, claude_tools, ollama_tools
from src.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(anthropic_api_key="test-key", **overrides)


def test_get_llm_backend_claude():
    backend = get_llm_backend(_settings(llm_provider="claude"))
    assert isinstance(backend, ClaudeBackend)


def test_get_llm_backend_ollama():
    backend = get_llm_backend(_settings(llm_provider="ollama"))
    assert isinstance(backend, OllamaBackend)


def test_get_llm_backend_custom():
    backend = get_llm_backend(_settings(llm_provider="custom"))
    assert isinstance(backend, CustomOpenAICompatibleBackend)


@pytest.mark.parametrize("provider", ["claude", "ollama", "custom", "", "Claude", "unknown"])
def test_backend_and_tools_dispatch_agree_on_every_provider_value(provider):
    """get_llm_backend() and get_tools_for_provider() must never disagree on
    which wire format a provider speaks — even for garbage/miscased input —
    or a Claude backend can end up sent OpenAI-shaped tool specs (or vice
    versa)."""
    backend = get_llm_backend(_settings(llm_provider=provider))
    tools = get_tools_for_provider(provider)

    if isinstance(backend, ClaudeBackend):
        assert not uses_openai_style_wire_format(provider)
        assert tools == claude_tools()
    else:
        assert uses_openai_style_wire_format(provider)
        assert tools == ollama_tools()


@pytest.mark.asyncio
async def test_claude_backend_text_only_response():
    mock_response = MagicMock()
    mock_response.content = [SimpleNamespace(type="text", text="hello")]
    mock_response.usage = SimpleNamespace(input_tokens=123, output_tokens=45)

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        backend = ClaudeBackend(_settings())
        result = await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert result.text == "hello"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 123
    assert result.output_tokens == 45


@pytest.mark.asyncio
async def test_claude_backend_tool_use_response():
    mock_response = MagicMock()
    mock_response.content = [
        SimpleNamespace(type="text", text="checking meds"),
        SimpleNamespace(
            type="tool_use", id="call_1", name="get_medication_details", input={"medication_name": "Metformin"}
        ),
    ]

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        backend = ClaudeBackend(_settings())
        result = await backend.call(
            messages=[{"role": "user", "content": "hi"}], system="sys", tools=[{"name": "x"}]
        )

    assert result.stop_reason == "tool_use"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_medication_details"
    assert result.tool_calls[0].input == {"medication_name": "Metformin"}

    tool_result_msg = backend.build_tool_result_message(result.tool_calls[0], "Metformin 500mg")
    assert tool_result_msg["content"][0]["tool_use_id"] == "call_1"


def _bad_request_error(message: str) -> "anthropic.BadRequestError":
    import anthropic

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request, json={"error": {"message": message}})
    return anthropic.BadRequestError(message, response=response, body=None)


@pytest.mark.asyncio
async def test_claude_backend_retries_without_temperature_when_deprecated():
    """Some model families (observed: claude-opus-4-8) reject `temperature`
    outright rather than clamping an out-of-range value. The backend must
    retry once without it rather than fail the call entirely."""
    mock_response = MagicMock()
    mock_response.content = [SimpleNamespace(type="text", text="judged")]
    mock_response.usage = SimpleNamespace(input_tokens=10, output_tokens=5)

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[_bad_request_error("`temperature` is deprecated for this model."), mock_response]
        )
        mock_anthropic.return_value = mock_client

        backend = ClaudeBackend(_settings(), model="claude-opus-4-8")
        result = await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys", temperature=0.0)

    assert result.text == "judged"
    assert mock_client.messages.create.call_count == 2
    first_call_kwargs = mock_client.messages.create.call_args_list[0].kwargs
    second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
    assert first_call_kwargs["temperature"] == 0.0
    assert "temperature" not in second_call_kwargs


@pytest.mark.asyncio
async def test_claude_backend_reraises_unrelated_bad_request_errors():
    """Only the specific temperature-deprecation error should be retried —
    any other 400 must propagate normally, not be silently swallowed."""
    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=_bad_request_error("max_tokens is required"))
        mock_anthropic.return_value = mock_client

        backend = ClaudeBackend(_settings())
        with pytest.raises(Exception, match="max_tokens is required"):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert mock_client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_ollama_backend_requests_non_streaming_with_nested_temperature():
    """Regression test: Ollama's native /api/chat defaults to stream: true
    and expects temperature nested under `options`, not top-level. Sending
    neither previously meant a real (multi-chunk) response body was NDJSON,
    and response.json() raised an uncaught json.JSONDecodeError ("Extra
    data") that skipped straight past the single-shot fallback (DEC-013) to
    the outer generic fallback response — found by running the eval harness
    (issue #29) against a real local Ollama server rather than only mocks.
    """
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}
    captured_payload = {}

    async def fake_post(self, url, json, headers=None):
        captured_payload.update(json)
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys", temperature=0.0)

    assert captured_payload["stream"] is False
    assert captured_payload["options"]["temperature"] == 0.0
    assert "temperature" not in captured_payload  # must not be top-level for Ollama's native API


@pytest.mark.asyncio
async def test_ollama_backend_sets_num_ctx_from_settings():
    """Regression test for issue #71: without an explicit num_ctx, Ollama
    silently falls back to its own runtime default (commonly 2048 for a
    freshly-pulled model), independent of this app's own context_max_tokens
    budget — see Settings.ollama_num_ctx.
    """
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}
    captured_payload = {}

    async def fake_post(self, url, json, headers=None):
        captured_payload.update(json)
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama", ollama_num_ctx=4096))
        await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert captured_payload["options"]["num_ctx"] == 4096


@pytest.mark.asyncio
async def test_ollama_backend_warns_when_request_likely_exceeds_num_ctx():
    """Regression test for issue #71's "fails loudly" requirement: an
    oversized request should produce a visible warning rather than silently
    risking context truncation.
    """
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post), patch(
        "src.agents.llm_backend.logger"
    ) as mock_logger:
        backend = OllamaBackend(_settings(llm_provider="ollama", ollama_num_ctx=100))
        await backend.call(messages=[{"role": "user", "content": "x" * 2000}], system="sys")

    assert mock_logger.warning.called
    assert "ollama_num_ctx" in mock_logger.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_ollama_backend_no_warning_for_small_request():
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post), patch(
        "src.agents.llm_backend.logger"
    ) as mock_logger:
        backend = OllamaBackend(_settings(llm_provider="ollama", ollama_num_ctx=8192))
        await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert not mock_logger.warning.called


@pytest.mark.asyncio
async def test_ollama_backend_warns_when_output_room_is_low_even_under_old_input_only_threshold():
    """Regression test for DEC-037: the old version of this warning checked
    only input size against a flat 75% of ollama_num_ctx, silently assuming
    the remaining 25% covered the response — and never fired during the
    real investigation that found a genuine truncation. This message (13000
    chars at num_ctx=6000) is sized to land below that old 75%-of-input
    threshold (estimated ~4355 input tokens vs. a 4500 old threshold) while
    still leaving less than _RESERVED_OUTPUT_TOKENS_ESTIMATE (2000) tokens
    of room for the response — exactly the gap the old check missed.
    """
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post), patch(
        "src.agents.llm_backend.logger"
    ) as mock_logger:
        backend = OllamaBackend(_settings(llm_provider="ollama", ollama_num_ctx=6000))
        await backend.call(messages=[{"role": "user", "content": "x" * 13000}], system="sys")

    assert mock_logger.warning.called
    warning_text = mock_logger.warning.call_args[0][0]
    assert "for the response" in warning_text


@pytest.mark.asyncio
async def test_ollama_backend_applies_response_schema_when_no_tools():
    mock_json = {"message": {"role": "assistant", "content": "{}", "tool_calls": None}}
    captured_payload = {}

    async def fake_post(self, url, json, headers=None):
        captured_payload.update(json)
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        await backend.call(
            messages=[{"role": "user", "content": "hi"}], system="sys", response_schema=schema,
        )

    assert captured_payload["format"] == schema


@pytest.mark.asyncio
async def test_ollama_backend_ignores_response_schema_when_tools_present():
    """DEC-039's core safety property: response_schema must never be sent
    alongside tools — mixing Ollama's schema-constrained decoding with
    tool-calling is untested and risks the tool-calling reliability
    DEC-037/DEC-038 spent this whole review stabilizing.
    """
    mock_json = {"message": {"role": "assistant", "content": "", "tool_calls": None}}
    captured_payload = {}

    async def fake_post(self, url, json, headers=None):
        captured_payload.update(json)
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        await backend.call(
            messages=[{"role": "user", "content": "hi"}], system="sys",
            tools=[{"type": "function", "function": {"name": "x"}}],
            response_schema=schema,
        )

    assert "format" not in captured_payload


@pytest.mark.asyncio
async def test_ollama_backend_no_format_key_when_response_schema_not_given():
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}
    captured_payload = {}

    async def fake_post(self, url, json, headers=None):
        captured_payload.update(json)
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert "format" not in captured_payload


@pytest.mark.asyncio
async def test_claude_backend_ignores_response_schema():
    """Claude backend accepts response_schema (interface parity) but does
    nothing with it — see LLMBackend.call's docstring."""
    mock_message = MagicMock()
    mock_message.content = [SimpleNamespace(type="text", text="hello")]
    mock_message.usage = MagicMock(input_tokens=10, output_tokens=5)

    backend = ClaudeBackend(_settings(llm_provider="claude"))
    with patch.object(backend.client.messages, "create", AsyncMock(return_value=mock_message)) as mock_create:
        await backend.call(
            messages=[{"role": "user", "content": "hi"}], system="sys",
            response_schema={"type": "object"},
        )

    assert "response_format" not in mock_create.call_args.kwargs
    assert "format" not in mock_create.call_args.kwargs


@pytest.mark.asyncio
async def test_custom_backend_requests_non_streaming_with_top_level_temperature():
    """CustomOpenAICompatibleBackend hits /chat/completions, where top-level
    `temperature` (OpenAI's convention) is correct — unlike Ollama's native
    /api/chat, which needs it nested under `options` (see the Ollama
    regression test above).
    """
    mock_json = {"choices": [{"message": {"role": "assistant", "content": "hi", "tool_calls": None}}]}
    captured_payload = {}

    async def fake_post(self, url, json, headers=None):
        captured_payload.update(json)
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = CustomOpenAICompatibleBackend(_settings(
            llm_provider="custom", custom_llm_base_url="http://custom", custom_llm_model="m",
        ))
        await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys", temperature=0.0)

    assert captured_payload["stream"] is False
    assert captured_payload["temperature"] == 0.0


@pytest.mark.asyncio
async def test_ollama_backend_text_only_response():
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        result = await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert result.text == "hello"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_ollama_backend_tool_use_response():
    mock_json = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "lookup_past_visits", "arguments": {"specialty": "Cardiology"}}}
            ],
        }
    }

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        result = await backend.call(
            messages=[{"role": "user", "content": "hi"}], system="sys", tools=[{"type": "function"}]
        )

    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "lookup_past_visits"
    assert result.tool_calls[0].input == {"specialty": "Cardiology"}


@pytest.mark.asyncio
async def test_ollama_backend_malformed_tool_call_raises():
    mock_json = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {}}],  # missing required "name" key
        }
    }

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        with pytest.raises(ToolCallParsingError):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys", tools=[{}])


@pytest.mark.asyncio
async def test_ollama_backend_request_error_raises_tool_call_parsing_error():
    async def fake_post(self, url, json, headers=None):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        with pytest.raises(ToolCallParsingError):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")


@pytest.mark.asyncio
async def test_backend_call_enforces_total_wall_clock_timeout(monkeypatch):
    """Regression test: a response that keeps trickling data within each
    httpx per-chunk read-timeout window (never idle long enough to trip
    httpx.Timeout(120.0, ...) on its own) must still be bounded by a real
    total-duration ceiling — found by an eval-harness (#29) run against a
    real local model that hung 30+ minutes on an active connection with no
    error, no log, no fallback triggered.
    """
    import asyncio as asyncio_module

    import src.agents.llm_backend as llm_backend_module

    monkeypatch.setattr(llm_backend_module, "_TOTAL_CALL_TIMEOUT_SECONDS", 0.05)

    async def fake_post(self, url, json, headers=None):
        await asyncio_module.sleep(10)  # never actually reached — total timeout fires first
        return httpx.Response(200, json={}, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        with pytest.raises(ToolCallParsingError, match="total wall-clock"):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")


def _custom_settings(**overrides) -> Settings:
    defaults = {
        "llm_provider": "custom",
        "custom_llm_base_url": "https://api.example.com/v1",
        "custom_llm_model": "some-model",
        "custom_llm_api_key": "secret-key",
    }
    defaults.update(overrides)
    return _settings(**defaults)


@pytest.mark.asyncio
async def test_custom_backend_text_only_response():
    mock_json = {"choices": [{"message": {"role": "assistant", "content": "hello", "tool_calls": None}}]}

    captured = {}

    async def fake_post(self, url, json, headers=None):
        captured["headers"] = headers
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = CustomOpenAICompatibleBackend(_custom_settings())
        result = await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert result.text == "hello"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"
    assert captured["headers"] == {"Authorization": "Bearer secret-key"}


@pytest.mark.asyncio
async def test_custom_backend_no_api_key_sends_no_auth_header():
    mock_json = {"choices": [{"message": {"role": "assistant", "content": "hi", "tool_calls": None}}]}
    captured = {}

    async def fake_post(self, url, json, headers=None):
        captured["headers"] = headers
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = CustomOpenAICompatibleBackend(_custom_settings(custom_llm_api_key=None))
        await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert captured["headers"] == {}


@pytest.mark.asyncio
async def test_custom_backend_tool_use_response():
    mock_json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "lookup_past_visits",
                                "arguments": '{"specialty": "Cardiology"}',
                            },
                        }
                    ],
                }
            }
        ]
    }

    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = CustomOpenAICompatibleBackend(_custom_settings())
        result = await backend.call(
            messages=[{"role": "user", "content": "hi"}], system="sys", tools=[{"type": "function"}]
        )

    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "lookup_past_visits"
    assert result.tool_calls[0].input == {"specialty": "Cardiology"}

    tool_result_msg = backend.build_tool_result_message(result.tool_calls[0], "some result")
    assert tool_result_msg == {"role": "tool", "tool_call_id": "call_1", "content": "some result"}


@pytest.mark.asyncio
async def test_custom_backend_malformed_response_raises():
    async def fake_post(self, url, json, headers=None):
        return httpx.Response(200, json={"unexpected": "shape"}, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = CustomOpenAICompatibleBackend(_custom_settings())
        with pytest.raises(ToolCallParsingError):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")


@pytest.mark.asyncio
async def test_custom_backend_request_error_raises_tool_call_parsing_error():
    async def fake_post(self, url, json, headers=None):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = CustomOpenAICompatibleBackend(_custom_settings())
        with pytest.raises(ToolCallParsingError):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")
