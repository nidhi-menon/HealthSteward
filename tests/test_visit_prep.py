"""Tests for visit preparation agent with mocked Claude API."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


def _mock_text_response(text: str) -> MagicMock:
    """Build a mock Anthropic response with a single text content block.

    Uses SimpleNamespace (not MagicMock) for the content block so
    `block.type == "text"` comparisons in ClaudeBackend behave like the
    real SDK's TextBlock, rather than always being falsy against a MagicMock.
    """
    mock_message = MagicMock()
    mock_message.content = [SimpleNamespace(type="text", text=text)]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_message


@pytest.fixture(autouse=True)
def _no_ollama_client(monkeypatch):
    """None of these tests create past appointments, so Stage 2 relevance
    scoring is never actually exercised (stage1_results is always empty,
    well below stage2_threshold) — but get_ollama_client() still runs its
    real availability check and, if Ollama happens to be running locally,
    caches a shared httpx client across the module-level singleton. That
    singleton doesn't survive pytest-asyncio's per-event-loop-per-test
    isolation and causes "Event loop is closed" failures on teardown.
    Stub it out entirely rather than depend on the dev machine's local
    Ollama state, which these tests don't need in the first place.
    """
    monkeypatch.setattr(
        "src.agents.visit_prep.get_ollama_client",
        AsyncMock(return_value=None),
    )


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response for visit preparation."""
    return {
        "questions": {
            "Medication Questions": [
                "How is Metformin working for blood sugar control?",
                "Should I be concerned about any side effects?",
            ],
            "Diabetes Management": [
                "What should my target blood sugar levels be?",
                "How often should I monitor my blood sugar?",
            ],
            "Lifestyle Questions": [
                "Are there dietary changes I should make?",
                "How much exercise is recommended for my condition?",
            ],
        },
        "context_summary": "Patient with Type 2 Diabetes, currently on Metformin, "
        "scheduled for a routine checkup with their endocrinologist.",
    }


@pytest.mark.asyncio
async def test_prepare_visit(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    sample_condition_data,
    sample_medication_data,
    mock_claude_response,
):
    """Test visit preparation endpoint with mocked Claude API."""
    # Create a profile
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Create condition and medication
    await client.post(
        f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data
    )
    await client.post(
        f"/api/profiles/{profile_id}/medications/", json=sample_medication_data
    )

    # Create a doctor
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    # Create an appointment
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Mock the Claude API call
    mock_message = _mock_text_response(
        '{"questions": {"General": ["Test question"]}, "context_summary": "Test summary"}'
    )

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client

        # Request visit preparation
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()
    assert "generated_questions" in data
    assert "context_summary" in data
    assert data["appointment_id"] == appointment_id


@pytest.mark.asyncio
async def test_get_visit_prep(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test getting visit preparation after it's been generated."""
    # Create a profile
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Create a doctor
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    # Create an appointment
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Mock the Claude API call
    mock_message = _mock_text_response(
        '{"questions": {"Test": ["Question 1"]}, "context_summary": "Summary"}'
    )

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client

        # Generate visit preparation
        await client.post(f"/api/visits/{appointment_id}/prepare")

    # Get the visit preparation
    response = await client.get(f"/api/visits/{appointment_id}/prep")

    assert response.status_code == 200
    data = response.json()
    assert data["appointment_id"] == appointment_id
    assert "generated_questions" in data


@pytest.mark.asyncio
async def test_get_visit_prep_not_found(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test getting visit prep when it hasn't been generated yet."""
    # Create a profile
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Create a doctor
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    # Create an appointment
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Try to get visit prep without generating it first
    response = await client.get(f"/api/visits/{appointment_id}/prep")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_prepare_visit_with_additional_concerns(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test visit preparation with additional patient concerns."""
    # Create a profile
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Create a doctor
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    # Create an appointment
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Mock the Claude API call
    mock_message = _mock_text_response(
        '{"questions": {"Concerns": ["About fatigue"]}, "context_summary": "Patient concerned about fatigue"}'
    )

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client

        # Request visit preparation with additional concerns
        response = await client.post(
            f"/api/visits/{appointment_id}/prepare",
            json={"additional_concerns": "I've been feeling very tired lately"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "generated_questions" in data


@pytest.mark.asyncio
async def test_prepare_visit_appointment_not_found(client: AsyncClient):
    """Test visit preparation for non-existent appointment."""
    response = await client.post("/api/visits/non-existent-id/prepare")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_prepare_visit_agentic_tool_use(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    sample_medication_data,
):
    """Test the agentic loop: a tool_use turn followed by a final text turn."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    await client.post(f"/api/profiles/{profile_id}/medications/", json=sample_medication_data)

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    tool_use_response = MagicMock()
    tool_use_response.content = [
        SimpleNamespace(
            type="tool_use",
            id="call_1",
            name="get_medication_details",
            input={},
        )
    ]

    final_response = _mock_text_response(
        '{"questions": {"Medication Review": ["Is Metformin still working well?"]}, '
        '"context_summary": "Patient on Metformin for diabetes."}'
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=[tool_use_response, final_response])
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()
    assert data["generated_questions"] == {
        "Medication Review": ["Is Metformin still working well?"]
    }
    assert mock_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_prepare_visit_wires_ollama_client_into_stage2_scoring(
    client: AsyncClient,
    db_session,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
):
    """Stage 2 relevance scoring should actually run when Ollama is available
    and there are enough past visits — regression test for the bug where
    ContextSelector.ollama_client was never wired in from VisitPrepAgent, so
    Stage 2 silently no-opped in production regardless of Ollama's state.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.agents.visit_prep import VisitPrepAgent
    from src.data.models import Appointment
    from src.config import get_settings

    # Single-shot generation only, not the agentic loop — irrelevant to this test.
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")
    monkeypatch.setattr(get_settings(), "agent_tool_use_enabled", False)

    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Target doctor is a specialist; past visits are with a *different*,
    # Primary Care doctor so they pass Stage 1 via the PCP rule rather than
    # collapsing into the (single-visit-only) same-doctor pin.
    target_doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    target_doctor_id = target_doctor_response.json()["id"]

    pcp_doctor_data = {**sample_doctor_data, "name": "Dr. Primary Care", "specialty": "Primary Care"}
    pcp_doctor_response = await client.post(f"/api/profiles/{profile_id}/doctors/", json=pcp_doctor_data)
    pcp_doctor_id = pcp_doctor_response.json()["id"]

    # More than stage2_threshold (5) completed past visits, to trigger Stage 2.
    for i in range(6):
        await client.post(
            f"/api/profiles/{profile_id}/appointments/",
            json={
                "doctor_id": pcp_doctor_id,
                "scheduled_date": f"2024-0{(i % 9) + 1}-10T10:00:00",
                "purpose": f"Checkup {i}",
                "status": "completed",
                "notes": "Routine visit",
            },
        )

    target_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/",
        json={
            "doctor_id": target_doctor_id,
            "scheduled_date": "2025-06-01T10:00:00",
            "purpose": "Annual physical",
            "status": "scheduled",
        },
    )
    target_id = target_response.json()["id"]

    mock_ollama = AsyncMock()
    mock_ollama.generate = AsyncMock(return_value="9")
    monkeypatch.setattr(
        "src.agents.visit_prep.get_ollama_client",
        AsyncMock(return_value=mock_ollama),
    )

    mock_message = _mock_text_response(
        '{"questions": {"General": ["Test question"]}, "context_summary": "Test summary"}'
    )

    from src.data.models import HealthProfile

    result = await db_session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.doctor),
            selectinload(Appointment.profile).selectinload(HealthProfile.conditions),
            selectinload(Appointment.profile).selectinload(HealthProfile.medications),
            selectinload(Appointment.profile).selectinload(HealthProfile.doctors),
        )
        .where(Appointment.id == target_id)
    )
    target_appointment = result.scalar_one()

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic_backend.return_value = mock_client

        agent = VisitPrepAgent(db_session)
        result = await agent.prepare_visit(target_appointment)

    assert "questions" in result
    # Stage 2 must have actually scored candidates via the wired-in client —
    # this is the crux of the regression test.
    assert mock_ollama.generate.call_count > 0


@pytest.mark.asyncio
async def test_prepare_visit_falls_back_when_agentic_loop_does_not_converge(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """If the agentic loop never converges, prepare_visit falls back to single-shot."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Every agentic-loop turn requests another tool call, so it never converges
    # within agent_max_turns and prepare_visit must fall back to single-shot.
    looping_tool_use_response = MagicMock()
    looping_tool_use_response.content = [
        SimpleNamespace(type="tool_use", id="call_1", name="get_medication_details", input={})
    ]

    fallback_response = _mock_text_response(
        '{"questions": {"General": ["Fallback question"]}, "context_summary": "Fallback summary"}'
    )

    # The single-shot fallback now also routes through get_llm_backend()
    # (src.agents.llm_backend.ClaudeBackend), same as the agentic loop, so
    # both share one mocked client: agent_max_turns looping responses,
    # then the fallback response on the single-shot call after that.
    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[looping_tool_use_response] * get_settings().agent_max_turns + [fallback_response]
        )
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()
    assert data["generated_questions"] == {"General": ["Fallback question"]}
