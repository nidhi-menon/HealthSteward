"""Tests for the pluggable LLM backend abstraction (src/agents/llm_backend.py)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.agents.llm_backend import (
    ClaudeBackend,
    OllamaBackend,
    ToolCallParsingError,
    get_llm_backend,
)
from src.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(anthropic_api_key="test-key", **overrides)


def test_get_llm_backend_claude():
    backend = get_llm_backend(_settings(llm_provider="claude"))
    assert isinstance(backend, ClaudeBackend)


def test_get_llm_backend_ollama():
    backend = get_llm_backend(_settings(llm_provider="ollama"))
    assert isinstance(backend, OllamaBackend)


@pytest.mark.asyncio
async def test_claude_backend_text_only_response():
    mock_response = MagicMock()
    mock_response.content = [SimpleNamespace(type="text", text="hello")]

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        backend = ClaudeBackend(_settings())
        result = await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")

    assert result.text == "hello"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"


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


@pytest.mark.asyncio
async def test_ollama_backend_text_only_response():
    mock_json = {"message": {"role": "assistant", "content": "hello", "tool_calls": None}}

    async def fake_post(self, url, json):
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

    async def fake_post(self, url, json):
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

    async def fake_post(self, url, json):
        return httpx.Response(200, json=mock_json, request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        with pytest.raises(ToolCallParsingError):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys", tools=[{}])


@pytest.mark.asyncio
async def test_ollama_backend_request_error_raises_tool_call_parsing_error():
    async def fake_post(self, url, json):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", "http://test"))

    with patch.object(httpx.AsyncClient, "post", fake_post):
        backend = OllamaBackend(_settings(llm_provider="ollama"))
        with pytest.raises(ToolCallParsingError):
            await backend.call(messages=[{"role": "user", "content": "hi"}], system="sys")
