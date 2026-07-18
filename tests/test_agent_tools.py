"""Tests for the visit-prep agentic loop's tools (src/agents/tools.py)."""

from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.tools import UnknownToolError, VisitPrepTools, claude_tools, ollama_tools
from src.data.models import Appointment, Doctor, HealthProfile, Medication
from src.utils.anonymization import Anonymizer


def test_claude_tools_shape():
    tools = claude_tools()
    assert len(tools) == 2
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_ollama_tools_shape():
    tools = ollama_tools()
    assert len(tools) == 2
    for tool in tools:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "parameters" in tool["function"]


@pytest.fixture
async def profile_with_medication(db_session: AsyncSession) -> HealthProfile:
    profile = HealthProfile(name="Test Patient", date_of_birth=date(1990, 1, 1))
    db_session.add(profile)
    await db_session.flush()

    doctor = Doctor(profile_id=profile.id, name="Dr. Smith", specialty="Endocrinology")
    db_session.add(doctor)
    await db_session.flush()

    medication = Medication(
        profile_id=profile.id,
        name="Metformin",
        dosage="500mg",
        frequency="twice daily",
        purpose="Blood sugar control",
        side_effects="Occasional nausea",
        prescribing_doctor="Dr. Smith",
    )
    db_session.add(medication)

    appointment = Appointment(
        profile_id=profile.id,
        doctor_id=doctor.id,
        scheduled_date=datetime(2024, 1, 15, 10, 0, 0),
        purpose="Routine diabetes checkup",
        visit_notes="Discussed dosage increase",
        status="completed",
    )
    db_session.add(appointment)

    await db_session.commit()
    return profile


@pytest.mark.asyncio
async def test_get_medication_details_all(db_session, profile_with_medication):
    tools = VisitPrepTools(db_session, Anonymizer(use_ner=False), profile_with_medication.id)
    result = await tools.execute("get_medication_details", {})

    assert "Metformin" in result
    assert "500mg" in result
    assert "Blood sugar control" in result
    assert "Prescribing physician" in result  # prescribing_doctor anonymized
    assert "Dr. Smith" not in result


@pytest.mark.asyncio
async def test_get_medication_details_filtered_no_match(db_session, profile_with_medication):
    tools = VisitPrepTools(db_session, Anonymizer(use_ner=False), profile_with_medication.id)
    result = await tools.execute("get_medication_details", {"medication_name": "Nonexistent"})

    assert result == "No matching medications found."


@pytest.mark.asyncio
async def test_lookup_past_visits(db_session, profile_with_medication):
    tools = VisitPrepTools(db_session, Anonymizer(use_ner=False), profile_with_medication.id)
    result = await tools.execute("lookup_past_visits", {})

    assert "your Endocrinology" in result
    assert "Routine diabetes checkup" in result
    assert "Dr. Smith" not in result  # doctor name must be anonymized


@pytest.mark.asyncio
async def test_lookup_past_visits_specialty_filter_no_match(db_session, profile_with_medication):
    tools = VisitPrepTools(db_session, Anonymizer(use_ner=False), profile_with_medication.id)
    result = await tools.execute("lookup_past_visits", {"specialty": "Cardiology"})

    assert result == "No matching past visits found."


@pytest.mark.asyncio
async def test_unknown_tool_name(db_session, profile_with_medication):
    tools = VisitPrepTools(db_session, Anonymizer(use_ner=False), profile_with_medication.id)

    with pytest.raises(UnknownToolError, match="not_a_real_tool"):
        await tools.execute("not_a_real_tool", {})
