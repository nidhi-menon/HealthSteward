"""Tests for the runtime app settings API (DEC-016)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_settings_defaults_to_ollama(client: AsyncClient):
    """With no DB overrides, effective settings fall back to env defaults."""
    response = await client.get("/api/settings/")
    assert response.status_code == 200
    data = response.json()
    assert data["llm_provider"] == "ollama"
    assert data["ollama_base_url"]
    assert data["ollama_model"]


@pytest.mark.asyncio
async def test_update_settings_switches_provider(client: AsyncClient):
    response = await client.put("/api/settings/", json={"llm_provider": "claude"})
    assert response.status_code == 200
    assert response.json()["llm_provider"] == "claude"

    # Persisted — a fresh GET reflects the switch.
    response = await client.get("/api/settings/")
    assert response.json()["llm_provider"] == "claude"


@pytest.mark.asyncio
async def test_update_settings_rejects_invalid_provider(client: AsyncClient):
    response = await client.put("/api/settings/", json={"llm_provider": "not-a-provider"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_settings_masks_api_key_on_read(client: AsyncClient):
    await client.put(
        "/api/settings/",
        json={"llm_provider": "claude", "anthropic_api_key": "sk-ant-abcdef1234"},
    )
    response = await client.get("/api/settings/")
    data = response.json()
    assert data["anthropic_api_key"] != "sk-ant-abcdef1234"
    assert data["anthropic_api_key"].endswith("1234")


@pytest.mark.asyncio
async def test_update_settings_custom_provider_fields(client: AsyncClient):
    response = await client.put(
        "/api/settings/",
        json={
            "llm_provider": "custom",
            "custom_llm_base_url": "https://api.example.com/v1",
            "custom_llm_model": "some-model",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["llm_provider"] == "custom"
    assert data["custom_llm_base_url"] == "https://api.example.com/v1"
    assert data["custom_llm_model"] == "some-model"


@pytest.mark.asyncio
async def test_update_settings_empty_payload_rejected(client: AsyncClient):
    response = await client.put("/api/settings/", json={})
    assert response.status_code == 400
