"""Tests for visit-prep fallback-rate diagnostics (issue #30, DEC-026).

Two layers are covered here: that `prepare_visit()` records *how* each run was
produced on its `ConversationLog` row, and that
`GET /api/diagnostics/visit-prep-fallback` aggregates those records correctly.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.data.models import ConversationLog


def _mock_text_response(text: str) -> MagicMock:
    """Mock Anthropic response with a single text block (see test_visit_prep.py)."""
    mock_message = MagicMock()
    mock_message.content = [SimpleNamespace(type="text", text=text)]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_message


def _mock_tool_use_response(name: str = "get_medication_details", call_id: str = "call_1") -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = [
        SimpleNamespace(type="tool_use", id=call_id, name=name, input={})
    ]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_message


_VALID_JSON = (
    '{"questions": {"Medication Review": ["Is this still the right dose?"]}, '
    '"context_summary": "Summary."}'
)


@pytest.fixture(autouse=True)
def _no_ollama_client(monkeypatch):
    """Same rationale as test_visit_prep.py's fixture of this name — keep the
    module-level Ollama singleton out of these tests entirely."""
    monkeypatch.setattr(
        "src.agents.visit_prep.get_ollama_client",
        AsyncMock(return_value=None),
    )


@pytest.fixture(autouse=True)
def _claude_provider(monkeypatch):
    """These tests drive the Claude backend, which is what the mocks patch."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "claude")


async def _make_appointment(
    client: AsyncClient, sample_profile_data, sample_doctor_data, sample_appointment_data
) -> str:
    """Create a profile, doctor and appointment; return the appointment id."""
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/",
        json={**sample_appointment_data, "doctor_id": doctor_id},
    )
    return appointment_response.json()["id"]


async def _latest_run_diagnostics(db_session) -> dict:
    """run_diagnostics from the most recently written assistant log row."""
    result = await db_session.execute(
        select(ConversationLog)
        .where(ConversationLog.role == "assistant")
        .order_by(ConversationLog.timestamp.desc(), ConversationLog.id.desc())
    )
    latest = result.scalars().first()
    assert latest is not None, "expected an assistant ConversationLog row"
    return (latest.extra_data or {}).get("run_diagnostics")


# ============================================================================
# Logging: how each run was produced
# ============================================================================


@pytest.mark.asyncio
async def test_converged_agentic_run_is_logged_as_agentic(
    client: AsyncClient, db_session, sample_profile_data, sample_doctor_data,
    sample_appointment_data, sample_medication_data,
):
    """A run that goes through the agentic loop and converges records
    agentic_path=True with no fallback reason."""
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]
    await client.post(f"/api/profiles/{profile_id}/medications/", json=sample_medication_data)
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/",
        json={**sample_appointment_data, "doctor_id": doctor_response.json()["id"]},
    )
    appointment_id = appointment_response.json()["id"]

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[_mock_tool_use_response(), _mock_text_response(_VALID_JSON)]
        )
        mock_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    diagnostics = await _latest_run_diagnostics(db_session)
    assert diagnostics == {"agentic_path": True, "fallback_reason": None}


@pytest.mark.asyncio
async def test_non_convergence_is_logged_distinctly(
    client: AsyncClient, db_session, monkeypatch, sample_profile_data,
    sample_doctor_data, sample_appointment_data,
):
    """Running out of turns is the bounded loop working as designed — it must
    be recorded as non_convergence, not lumped in with real errors."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "agent_max_turns", 2)
    appointment_id = await _make_appointment(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        # Never stops calling tools, so the loop exhausts its turn budget;
        # the third response serves the single-shot fallback.
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _mock_tool_use_response(call_id="call_1"),
                _mock_tool_use_response(call_id="call_2"),
                _mock_text_response(_VALID_JSON),
            ]
        )
        mock_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    diagnostics = await _latest_run_diagnostics(db_session)
    assert diagnostics == {"agentic_path": False, "fallback_reason": "non_convergence"}


@pytest.mark.asyncio
async def test_unknown_tool_is_logged_distinctly(
    client: AsyncClient, db_session, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """A hallucinated tool name is a real defect, and must not be recorded as
    the same thing as a loop that simply ran long."""
    appointment_id = await _make_appointment(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _mock_tool_use_response(name="not_a_real_tool"),
                _mock_text_response(_VALID_JSON),
            ]
        )
        mock_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    diagnostics = await _latest_run_diagnostics(db_session)
    assert diagnostics == {"agentic_path": False, "fallback_reason": "unknown_tool"}


@pytest.mark.asyncio
async def test_malformed_tool_call_is_logged_as_parse_error(
    client: AsyncClient, db_session, monkeypatch, sample_profile_data,
    sample_doctor_data, sample_appointment_data,
):
    """A backend emitting an unparseable tool call — the specific degradation
    DEC-013 warns about on small local models — gets its own reason."""
    from src.agents.llm_backend import ToolCallParsingError
    from src.agents.visit_prep import VisitPrepAgent

    async def _raise_parse_error(*args, **kwargs):
        raise ToolCallParsingError("could not parse tool call")

    monkeypatch.setattr(VisitPrepAgent, "_run_agentic_loop", _raise_parse_error)

    appointment_id = await _make_appointment(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_mock_text_response(_VALID_JSON))
        mock_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    diagnostics = await _latest_run_diagnostics(db_session)
    assert diagnostics == {"agentic_path": False, "fallback_reason": "parse_error"}


@pytest.mark.asyncio
async def test_tool_use_disabled_is_logged_as_such(
    client: AsyncClient, db_session, monkeypatch, sample_profile_data,
    sample_doctor_data, sample_appointment_data,
):
    """The DEC-009 kill switch being off is a configuration choice, not a
    failure — it must not inflate the failure reasons."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "agent_tool_use_enabled", False)
    appointment_id = await _make_appointment(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_mock_text_response(_VALID_JSON))
        mock_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    diagnostics = await _latest_run_diagnostics(db_session)
    assert diagnostics == {"agentic_path": False, "fallback_reason": "tool_use_disabled"}


@pytest.mark.asyncio
async def test_hard_failure_is_logged_even_though_nothing_was_generated(
    client: AsyncClient, db_session, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """The blind spot issue #30 is really about: when both paths fail there is
    no LLM response to log, so without an explicit record a totally unreachable
    backend would be invisible to the fallback rate."""
    appointment_id = await _make_appointment(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("connection refused"))
        mock_backend.return_value = mock_client
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    assert response.json()["used_fallback"] is True

    diagnostics = await _latest_run_diagnostics(db_session)
    assert diagnostics["agentic_path"] is False
    assert diagnostics["fallback_reason"] == "backend_unavailable"
    # The agentic loop failed first (same connection error) — that has to be
    # preserved, or a backend breaking tool use on its way down reads as a
    # plain outage.
    assert diagnostics["prior_agentic_failure"] == "loop_error"
    assert diagnostics["error_type"] == "RuntimeError"


# ============================================================================
# GET /api/diagnostics/visit-prep-fallback
# ============================================================================


@pytest.mark.asyncio
async def test_fallback_rate_is_zero_with_no_runs(client: AsyncClient):
    """No runs yet must report 0.0, not divide by zero."""
    response = await client.get("/api/diagnostics/visit-prep-fallback")

    assert response.status_code == 200
    data = response.json()
    assert data["runs_considered"] == 0
    assert data["fallback_rate"] == 0.0
    assert data["reasons"] == {}
    assert data["oldest_run_at"] is None


@pytest.mark.asyncio
async def test_fallback_rate_aggregates_mixed_runs(
    client: AsyncClient, monkeypatch, sample_profile_data, sample_doctor_data,
    sample_appointment_data, sample_medication_data,
):
    """One agentic run and one unknown-tool fallback → 50%, with the reason
    attributed rather than collapsed into a bare count."""
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]
    await client.post(f"/api/profiles/{profile_id}/medications/", json=sample_medication_data)
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    appointment_ids = []
    for _ in range(2):
        appointment_response = await client.post(
            f"/api/profiles/{profile_id}/appointments/",
            json={**sample_appointment_data, "doctor_id": doctor_id},
        )
        appointment_ids.append(appointment_response.json()["id"])

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[_mock_tool_use_response(), _mock_text_response(_VALID_JSON)]
        )
        mock_backend.return_value = mock_client
        await client.post(f"/api/visits/{appointment_ids[0]}/prepare")

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _mock_tool_use_response(name="not_a_real_tool"),
                _mock_text_response(_VALID_JSON),
            ]
        )
        mock_backend.return_value = mock_client
        await client.post(f"/api/visits/{appointment_ids[1]}/prepare")

    response = await client.get("/api/diagnostics/visit-prep-fallback")

    assert response.status_code == 200
    data = response.json()
    assert data["runs_considered"] == 2
    assert data["agentic_runs"] == 1
    assert data["fallback_runs"] == 1
    assert data["hard_failure_runs"] == 0
    assert data["fallback_rate"] == 0.5
    assert data["reasons"] == {"unknown_tool": 1}
    assert data["oldest_run_at"] is not None
    assert data["newest_run_at"] is not None


@pytest.mark.asyncio
async def test_hard_failure_counted_as_both_fallback_and_hard_failure(
    client: AsyncClient, sample_profile_data, sample_doctor_data, sample_appointment_data,
):
    """hard_failure_runs is a subset of fallback_runs, not a third bucket —
    otherwise the counts wouldn't add up to runs_considered."""
    appointment_id = await _make_appointment(
        client, sample_profile_data, sample_doctor_data, sample_appointment_data
    )

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("connection refused"))
        mock_backend.return_value = mock_client
        await client.post(f"/api/visits/{appointment_id}/prepare")

    data = (await client.get("/api/diagnostics/visit-prep-fallback")).json()

    assert data["runs_considered"] == 1
    assert data["agentic_runs"] == 0
    assert data["fallback_runs"] == 1
    assert data["hard_failure_runs"] == 1
    assert data["fallback_rate"] == 1.0
    # Both the outage and the tool-use failure that preceded it are attributed.
    assert data["reasons"] == {"backend_unavailable": 1, "loop_error": 1}


@pytest.mark.asyncio
async def test_limit_bounds_the_window(
    client: AsyncClient, sample_profile_data, sample_doctor_data, sample_appointment_data,
):
    """The window is a rolling one — 'is tool use working now', not all-time."""
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    for _ in range(3):
        appointment_response = await client.post(
            f"/api/profiles/{profile_id}/appointments/",
            json={**sample_appointment_data, "doctor_id": doctor_id},
        )
        appointment_id = appointment_response.json()["id"]
        with patch("src.agents.llm_backend.AsyncAnthropic") as mock_backend:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_text_response(_VALID_JSON)
            )
            mock_backend.return_value = mock_client
            await client.post(f"/api/visits/{appointment_id}/prepare")

    all_runs = (await client.get("/api/diagnostics/visit-prep-fallback")).json()
    windowed = (await client.get("/api/diagnostics/visit-prep-fallback?limit=2")).json()

    assert all_runs["runs_considered"] == 3
    assert windowed["runs_considered"] == 2


@pytest.mark.asyncio
async def test_rows_without_run_diagnostics_are_ignored(client: AsyncClient, db_session):
    """Assistant rows written before this landed (and any other agent's rows)
    carry no run_diagnostics and must not be counted as successful runs."""
    db_session.add(
        ConversationLog(
            role="assistant",
            content="a response from before this feature existed",
            extra_data={"anonymized": True, "model": "some-model"},
        )
    )
    await db_session.commit()

    data = (await client.get("/api/diagnostics/visit-prep-fallback")).json()

    assert data["runs_considered"] == 0
