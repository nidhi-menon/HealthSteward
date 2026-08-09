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
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    sample_condition_data,
    sample_medication_data,
    mock_claude_response,
):
    """Test visit preparation endpoint with mocked Claude API."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

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
    # Ties the assertion to the mocked Claude response's actual content, not
    # just response shape — guards against issue #79 (this test silently
    # exercising real/fallback Ollama instead of the intended mock).
    assert data["generated_questions"] == {"General": ["Test question"]}
    assert mock_client.messages.create.called


@pytest.mark.asyncio
async def test_prepare_visit_includes_doctor_notes_in_context(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Regression test for issue #51: Doctor.notes was persisted and
    user-editable but never reached the visit-prep context, unlike
    Condition.notes/Appointment.visit_notes.
    """
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

    mock_message = _mock_text_response(
        '{"questions": {"General": ["Test question"]}, "context_summary": "Test summary"}'
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    context_message = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert sample_doctor_data["notes"] in context_message


@pytest.mark.asyncio
async def test_get_visit_prep(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test getting visit preparation after it's been generated."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

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
    # Ties to the mocked Claude response's actual content — see #79.
    assert data["generated_questions"] == {"Test": ["Question 1"]}


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
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test visit preparation with additional patient concerns."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

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
    # Ties to the mocked Claude response's actual content — see #79.
    assert data["generated_questions"] == {"Concerns": ["About fatigue"]}


@pytest.mark.asyncio
async def test_prepare_visit_logs_redaction_events(
    client: AsyncClient,
    db_session,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Issue #16: redaction events (type + span + stable id, never the raw
    matched value) must land in the assistant ConversationLog row's
    extra_data["redaction_events"], aggregated across the whole request.
    """
    from sqlalchemy import select

    from src.config import get_settings
    from src.data.models import ConversationLog

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_data = {
        **sample_appointment_data,
        "doctor_id": doctor_id,
        "purpose": "Follow-up, call patient at 555-123-4567 to confirm",
    }
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    mock_message = _mock_text_response(
        '{"questions": {"Concerns": ["About fatigue"]}, "context_summary": "..."}'
    )

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(
            f"/api/visits/{appointment_id}/prepare",
            json={"additional_concerns": "Also, MRN: 12345678 for reference"},
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(ConversationLog)
        .where(ConversationLog.role == "assistant")
        .order_by(ConversationLog.timestamp.desc())
    )
    latest_assistant_log = result.scalars().first()

    events = latest_assistant_log.extra_data.get("redaction_events")
    assert events is not None
    assert len(events) >= 2  # phone in purpose, MRN in additional_concerns

    entity_types = {e["entity_type"] for e in events}
    assert "phone" in entity_types
    assert "mrn" in entity_types

    for event in events:
        # Never the raw matched value, only type/span/id/field/document link
        assert set(event.keys()) <= {
            "entity_id", "entity_type", "start", "end", "field_name",
            "document_id", "document_link",
        }
        assert "555-123-4567" not in str(event.values())
        assert "12345678" not in str(event.values())
        # No document lineage for appointment purpose / user-typed concerns
        assert event.get("document_link") == "none"


@pytest.mark.asyncio
async def test_prepare_visit_redaction_entity_ids_stable_across_runs(
    client: AsyncClient,
    db_session,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Same underlying field, redacted across two separate prepare_visit
    calls, must produce the same entity ids (issue #16) — a deterministic
    hash, not a random UUID per run."""
    from sqlalchemy import select

    from src.config import get_settings
    from src.data.models import ConversationLog

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_data = {
        **sample_appointment_data,
        "doctor_id": doctor_id,
        "purpose": "Follow-up, call patient at 555-123-4567 to confirm",
    }
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    mock_message = _mock_text_response(
        '{"questions": {"Concerns": ["About fatigue"]}, "context_summary": "..."}'
    )

    async def _run_once():
        with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
             patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_anthropic.return_value = mock_client
            mock_anthropic_backend.return_value = mock_client

            resp = await client.post(f"/api/visits/{appointment_id}/prepare")
        assert resp.status_code == 200

        result = await db_session.execute(
            select(ConversationLog)
            .where(ConversationLog.role == "assistant")
            .order_by(ConversationLog.timestamp.desc())
        )
        latest = result.scalars().first()
        return latest.extra_data.get("redaction_events")

    events1 = await _run_once()
    events2 = await _run_once()

    ids1 = sorted(e["entity_id"] for e in events1)
    ids2 = sorted(e["entity_id"] for e in events2)
    assert ids1 == ids2
    assert len(ids1) > 0


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
    # This is the agentic-loop-doesn't-converge fallback (DEC-009/013), which
    # still produced a real single-shot LLM response — not issue #47's
    # "backend failed entirely" fallback, so used_fallback must be False.
    assert data["used_fallback"] is False


@pytest.mark.asyncio
async def test_prepare_visit_surfaces_used_fallback_when_backend_fails_entirely(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Regression test for issue #47: when both the agentic loop and its
    single-shot fallback fail (e.g. an unreachable/misconfigured backend
    URL), prepare_visit's outer except returns the hardcoded generic
    placeholder questions — but must also flag used_fallback=True so the
    frontend can warn the user, instead of looking like a normal successful
    generation.
    """
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

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("connection refused"))
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()
    assert data["used_fallback"] is True
    assert "General Questions" in data["generated_questions"]


@pytest.mark.asyncio
async def test_prepare_visit_logs_tool_calls_from_agentic_loop(
    client: AsyncClient,
    db_session,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    sample_medication_data,
):
    """Regression test for #52: tool calls made during the agentic loop must
    land in the converging ConversationLog row's extra_data["tool_calls"],
    not just live transiently in the in-memory conversation list.
    """
    from sqlalchemy import select

    from src.config import get_settings
    from src.data.models import ConversationLog

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

    result = await db_session.execute(
        select(ConversationLog)
        .where(ConversationLog.role == "assistant")
        .order_by(ConversationLog.timestamp.desc())
    )
    latest_assistant_log = result.scalars().first()

    logged_tool_calls = latest_assistant_log.extra_data.get("tool_calls")
    assert logged_tool_calls is not None
    assert len(logged_tool_calls) == 1
    assert logged_tool_calls[0]["name"] == "get_medication_details"
    assert logged_tool_calls[0]["input"] == {}
    assert "Metformin" in logged_tool_calls[0]["result"]


@pytest.mark.asyncio
async def test_prepare_visit_logs_tool_calls_across_multiple_turns(
    client: AsyncClient,
    db_session,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    sample_medication_data,
):
    """Regression test for #52: tool_call_log accumulates across the whole
    loop rather than being reset per turn, so a 2-turn loop (a different
    tool call each turn) must log both calls, in order, not just the last.
    """
    from sqlalchemy import select

    from src.config import get_settings
    from src.data.models import ConversationLog

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

    turn1_response = MagicMock()
    turn1_response.content = [
        SimpleNamespace(
            type="tool_use", id="call_1", name="get_medication_details", input={}
        )
    ]

    turn2_response = MagicMock()
    turn2_response.content = [
        SimpleNamespace(
            type="tool_use",
            id="call_2",
            name="lookup_past_visits",
            input={"specialty": "Cardiology"},
        )
    ]

    final_response = _mock_text_response(
        '{"questions": {"Medication Review": ["Is Metformin still working well?"]}, '
        '"context_summary": "Patient on Metformin for diabetes."}'
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[turn1_response, turn2_response, final_response]
        )
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200

    result = await db_session.execute(
        select(ConversationLog)
        .where(ConversationLog.role == "assistant")
        .order_by(ConversationLog.timestamp.desc())
    )
    latest_assistant_log = result.scalars().first()

    logged_tool_calls = latest_assistant_log.extra_data.get("tool_calls")
    assert logged_tool_calls is not None
    assert len(logged_tool_calls) == 2
    assert logged_tool_calls[0]["name"] == "get_medication_details"
    assert logged_tool_calls[1]["name"] == "lookup_past_visits"
    assert logged_tool_calls[1]["input"] == {"specialty": "Cardiology"}
    assert "No matching past visits found." in logged_tool_calls[1]["result"]


@pytest.mark.asyncio
async def test_prepare_visit_falls_back_when_agentic_loop_calls_unknown_tool(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Regression test for #53: a hallucinated/unrecognized tool name must
    trigger the single-shot fallback, not be silently fed back into the
    conversation as if it were a legitimate tool result.
    """
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

    unknown_tool_use_response = MagicMock()
    unknown_tool_use_response.content = [
        SimpleNamespace(type="tool_use", id="call_1", name="not_a_real_tool", input={})
    ]

    fallback_response = _mock_text_response(
        '{"questions": {"General": ["Fallback question"]}, "context_summary": "Fallback summary"}'
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[unknown_tool_use_response, fallback_response]
        )
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()
    assert data["generated_questions"] == {"General": ["Fallback question"]}


# ============================================================================
# PATCH /api/visits/{appointment_id}/prep — editing generated prep (issue #14)
# ============================================================================


async def _generate_prep(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    questions_json: str = '{"questions": {"Medication Review": ["Original question"], '
                          '"Lifestyle": ["Keep me"]}, "context_summary": "Original summary"}',
) -> str:
    """Create profile/doctor/appointment and generate a prep against a mocked
    Claude call. Returns the appointment id."""
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

    mock_message = _mock_text_response(questions_json)
    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client
        await client.post(f"/api/visits/{appointment_id}/prepare")

    return appointment_id


@pytest.mark.asyncio
async def test_patch_prep_updates_questions(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """The core of issue #14: reword a question, add one of your own, and drop
    one that doesn't apply — without re-running the agent."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    edited = {
        "Medication Review": ["Reworded question", "A question of my own"],
    }
    response = await client.patch(
        f"/api/visits/{appointment_id}/prep", json={"generated_questions": edited}
    )

    assert response.status_code == 200
    assert response.json()["generated_questions"] == edited

    # Persisted, not just echoed back.
    fetched = await client.get(f"/api/visits/{appointment_id}/prep")
    assert fetched.json()["generated_questions"] == edited
    # The dropped category is really gone.
    assert "Lifestyle" not in fetched.json()["generated_questions"]


@pytest.mark.asyncio
async def test_patch_prep_updates_context_summary_only(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """A partial update must leave the omitted field untouched — saving a
    summary tweak shouldn't require round-tripping every question."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    response = await client.patch(
        f"/api/visits/{appointment_id}/prep", json={"context_summary": "My own summary"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["context_summary"] == "My own summary"
    assert data["generated_questions"] == {
        "Medication Review": ["Original question"],
        "Lifestyle": ["Keep me"],
    }


@pytest.mark.asyncio
async def test_patch_prep_questions_only_leaves_summary(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """The mirror of the above — the other single-field partial update."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    response = await client.patch(
        f"/api/visits/{appointment_id}/prep",
        json={"generated_questions": {"Only": ["One"]}},
    )

    assert response.status_code == 200
    assert response.json()["context_summary"] == "Original summary"


@pytest.mark.asyncio
async def test_patch_prep_bumps_updated_at(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """updated_at must move, so the UI can show when the patient last edited."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )
    before = (await client.get(f"/api/visits/{appointment_id}/prep")).json()["updated_at"]

    response = await client.patch(
        f"/api/visits/{appointment_id}/prep",
        json={"context_summary": "Edited"},
    )
    assert response.status_code == 200
    assert response.json()["updated_at"] >= before


@pytest.mark.asyncio
async def test_patch_prep_404_when_no_prep_exists(
    client: AsyncClient, sample_profile_data, sample_doctor_data, sample_appointment_data,
):
    """Editing an appointment that has no prep is a 404, not a silent create —
    there'd be nothing to edit, and creating one would hide a client bug."""
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_response.json()["id"]}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    response = await client.patch(
        f"/api/visits/{appointment_id}/prep", json={"context_summary": "x"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_prep_404_when_appointment_missing(client: AsyncClient):
    response = await client.patch(
        "/api/visits/does-not-exist/prep", json={"context_summary": "x"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_prep_empty_payload_rejected(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )
    response = await client.patch(f"/api/visits/{appointment_id}/prep", json={})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_patch_prep_rejects_malformed_questions_shape(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """generated_questions is typed dict[str, list[str]] on the update schema
    specifically because this endpoint is user-writable and the frontend renders
    every value as a list of strings — arbitrary JSON would break the page that
    has to display it."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    response = await client.patch(
        f"/api/visits/{appointment_id}/prep",
        json={"generated_questions": {"Category": "not a list"}},
    )
    assert response.status_code == 422

    # And the stored prep is untouched by the rejected write.
    fetched = await client.get(f"/api/visits/{appointment_id}/prep")
    assert fetched.json()["generated_questions"] == {
        "Medication Review": ["Original question"],
        "Lifestyle": ["Keep me"],
    }


@pytest.mark.asyncio
async def test_patch_prep_clears_used_fallback(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """used_fallback drives the "these are generic default questions, not
    personalized — regenerate" warning (issue #47). Once the patient has
    hand-edited the content, that warning is no longer true, so PATCH clears
    the flag regardless of how the prep was originally generated."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    response = await client.patch(
        f"/api/visits/{appointment_id}/prep",
        json={"generated_questions": {"Edited": ["Question"]}},
    )
    assert response.status_code == 200
    assert response.json()["used_fallback"] is False

    fetched = await client.get(f"/api/visits/{appointment_id}/prep")
    assert fetched.json()["used_fallback"] is False


@pytest.mark.asyncio
async def test_regenerate_after_edit_replaces_edits(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """Documents the interaction the issue's own resolved comment settled:
    Regenerate still replaces wholesale, so edits are lost by design. Pinned as
    a test so a future change to that behavior is a deliberate one."""
    from src.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    appointment_id = await _generate_prep(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )
    await client.patch(
        f"/api/visits/{appointment_id}/prep",
        json={"generated_questions": {"Mine": ["Hand-written"]}},
    )

    regenerated = _mock_text_response(
        '{"questions": {"Fresh": ["Regenerated question"]}, "context_summary": "Fresh summary"}'
    )
    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=regenerated)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    assert response.json()["generated_questions"] == {"Fresh": ["Regenerated question"]}


@pytest.mark.asyncio
async def test_prepare_visit_tokenises_free_text_consistently(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Issue #17: within one prepare_visit(), the same free-text value resolves
    to the same token everywhere, so the model can tell distinct entities apart
    instead of seeing one undifferentiated `[REDACTED]`.

    The same number appears in the appointment purpose and in the user's typed
    concerns — two separate `anonymize_text()` entry points — and a second,
    different number appears alongside it.
    """
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")

    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_data = {
        **sample_appointment_data,
        "doctor_id": doctor_id,
        "purpose": "Follow-up, call the clinic at 555-123-4567",
    }
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    mock_message = _mock_text_response(
        '{"questions": {"General": ["Q"]}, "context_summary": "S"}'
    )

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(
            f"/api/visits/{appointment_id}/prepare",
            json={
                "additional_concerns":
                    "Same number 555-123-4567, my partner is on 555-987-6543",
            },
        )

    assert response.status_code == 200

    sent = str(mock_client.messages.create.call_args.kwargs["messages"])
    assert "555-123-4567" not in sent and "555-987-6543" not in sent
    # One entity, one token — reached from two different call sites.
    assert sent.count("PHONE_1") == 2
    # ...and the other number is visibly a different entity.
    assert "PHONE_2" in sent
    assert "[REDACTED]" not in sent


@pytest.mark.asyncio
async def test_prepare_visit_scrubs_tokens_the_model_echoes_back(
    client: AsyncClient,
    monkeypatch,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Issue #17's leakage guard: a model handed `PERSON_1` can echo it into a
    generated question. The patient must never see the raw token — it falls
    back to `[REDACTED]`, which is exactly what they'd have seen before #17.
    """
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

    mock_message = _mock_text_response(
        '{"questions": {"Care Team": ["What did PERSON_1 recommend?"]},'
        ' "context_summary": "Referred by PERSON_1 to PERSON_2."}'
    )

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
         patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        mock_anthropic_backend.return_value = mock_client

        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()

    assert data["generated_questions"] == {
        "Care Team": ["What did [REDACTED] recommend?"]
    }
    assert data["context_summary"] == "Referred by [REDACTED] to [REDACTED]."
