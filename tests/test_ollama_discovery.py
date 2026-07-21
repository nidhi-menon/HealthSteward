"""Tests for Ollama base-URL auto-discovery (issue #48)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from src.utils.ollama_discovery import CANDIDATE_OLLAMA_URLS, discover_ollama_url, probe_ollama_url


@pytest.mark.asyncio
async def test_probe_ollama_url_true_on_200():
    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request("GET", url))

    with patch.object(httpx.AsyncClient, "get", fake_get):
        assert await probe_ollama_url("http://localhost:11434") is True


@pytest.mark.asyncio
async def test_probe_ollama_url_false_on_connection_error():
    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    with patch.object(httpx.AsyncClient, "get", fake_get):
        assert await probe_ollama_url("http://localhost:11434") is False


@pytest.mark.asyncio
async def test_probe_ollama_url_false_on_non_200():
    async def fake_get(self, url, **kwargs):
        return httpx.Response(500, request=httpx.Request("GET", url))

    with patch.object(httpx.AsyncClient, "get", fake_get):
        assert await probe_ollama_url("http://localhost:11434") is False


@pytest.mark.asyncio
async def test_discover_ollama_url_returns_first_responding_candidate():
    responding = CANDIDATE_OLLAMA_URLS[2]

    async def fake_get(self, url, **kwargs):
        if url.startswith(responding):
            return httpx.Response(200, request=httpx.Request("GET", url))
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    with patch.object(httpx.AsyncClient, "get", fake_get):
        assert await discover_ollama_url() == responding


@pytest.mark.asyncio
async def test_discover_ollama_url_returns_none_when_nothing_responds():
    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    with patch.object(httpx.AsyncClient, "get", fake_get):
        assert await discover_ollama_url() is None


@pytest.mark.asyncio
async def test_discover_ollama_route_found(client: AsyncClient):
    with patch(
        "src.api.settings.discover_ollama_url", AsyncMock(return_value="http://localhost:11434")
    ):
        response = await client.get("/api/settings/discover-ollama")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["base_url"] == "http://localhost:11434"
    assert data["candidates_tried"] == CANDIDATE_OLLAMA_URLS


@pytest.mark.asyncio
async def test_discover_ollama_route_not_found(client: AsyncClient):
    with patch("src.api.settings.discover_ollama_url", AsyncMock(return_value=None)):
        response = await client.get("/api/settings/discover-ollama")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["base_url"] is None
