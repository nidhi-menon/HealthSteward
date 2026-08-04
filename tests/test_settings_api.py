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


@pytest.mark.asyncio
async def test_short_secret_is_fully_redacted_not_leaked(client: AsyncClient):
    """A secret of 8 chars or fewer must never come back readable — showing
    its last 4 characters would leak half or more of it."""
    await client.put(
        "/api/settings/",
        json={"llm_provider": "claude", "anthropic_api_key": "abcd"},
    )
    response = await client.get("/api/settings/")
    assert response.json()["anthropic_api_key"] == "***"


@pytest.mark.asyncio
async def test_clearing_a_field_to_empty_string_falls_back_to_default(client: AsyncClient):
    """Persisting an empty-string override must behave like never having set
    it — not like overriding the default with a blank value."""
    default_response = await client.get("/api/settings/")
    default_base_url = default_response.json()["ollama_base_url"]

    await client.put("/api/settings/", json={"ollama_base_url": "http://example.com:1234"})
    changed = await client.get("/api/settings/")
    assert changed.json()["ollama_base_url"] == "http://example.com:1234"

    await client.put("/api/settings/", json={"ollama_base_url": ""})
    reset = await client.get("/api/settings/")
    assert reset.json()["ollama_base_url"] == default_base_url


# ---------------------------------------------------------------------------
# avs_parser_model (issue #59) — same overlay plumbing as ollama_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_settings_exposes_avs_parser_model_default(client: AsyncClient):
    """The AVS parser model is readable from the API and falls back to the env
    default when no DB override is set — previously it was config.py-only, with
    no way to see it without reading source."""
    response = await client.get("/api/settings/")
    assert response.status_code == 200
    assert response.json()["avs_parser_model"] == "qwen2.5:7b"


@pytest.mark.asyncio
async def test_update_avs_parser_model_persists(client: AsyncClient):
    response = await client.put("/api/settings/", json={"avs_parser_model": "llama3.2:3b"})
    assert response.status_code == 200
    assert response.json()["avs_parser_model"] == "llama3.2:3b"

    # Persisted — a fresh GET reflects the change, no restart needed.
    response = await client.get("/api/settings/")
    assert response.json()["avs_parser_model"] == "llama3.2:3b"


@pytest.mark.asyncio
async def test_clearing_avs_parser_model_falls_back_to_default(client: AsyncClient):
    """Empty string means "unset", matching every other overlay field — a
    cleared Settings field must not shadow the env default with a blank."""
    await client.put("/api/settings/", json={"avs_parser_model": "mistral:7b"})
    assert (await client.get("/api/settings/")).json()["avs_parser_model"] == "mistral:7b"

    await client.put("/api/settings/", json={"avs_parser_model": ""})
    assert (await client.get("/api/settings/")).json()["avs_parser_model"] == "qwen2.5:7b"


@pytest.mark.asyncio
async def test_avs_parser_model_is_independent_of_ollama_model(client: AsyncClient):
    """The two models are deliberately separate knobs — changing the agentic
    loop's model must not silently change what parses AVS PDFs, or vice versa."""
    await client.put(
        "/api/settings/",
        json={"ollama_model": "llama3.1:8b", "avs_parser_model": "qwen2.5:14b"},
    )
    data = (await client.get("/api/settings/")).json()
    assert data["ollama_model"] == "llama3.1:8b"
    assert data["avs_parser_model"] == "qwen2.5:14b"

    await client.put("/api/settings/", json={"ollama_model": "llama3.2:1b"})
    data = (await client.get("/api/settings/")).json()
    assert data["ollama_model"] == "llama3.2:1b"
    assert data["avs_parser_model"] == "qwen2.5:14b"


@pytest.mark.asyncio
async def test_avs_parser_model_override_survives_provider_switch(client: AsyncClient):
    """AVS parsing always runs on local Ollama regardless of which provider
    generates visit prep, so the override must not be tied to llm_provider.
    This is why the Settings field lives outside the provider-specific Ollama
    card in the UI."""
    await client.put("/api/settings/", json={"avs_parser_model": "qwen2.5:3b"})
    await client.put("/api/settings/", json={"llm_provider": "claude"})

    data = (await client.get("/api/settings/")).json()
    assert data["llm_provider"] == "claude"
    assert data["avs_parser_model"] == "qwen2.5:3b"
