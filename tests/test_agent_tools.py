"""Tests for the visit-prep agentic loop's tools (src/agents/tools.py)."""

from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

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
async def test_lookup_past_visits_excludes_context_selection_visits(db_session, profile_with_medication):
    """DEC-024: visits Stage 1-4 already selected into the base context
    shouldn't be re-surfaced by the tool call."""
    appointment = (
        await db_session.execute(
            select(Appointment).where(Appointment.profile_id == profile_with_medication.id)
        )
    ).scalar_one()

    tools = VisitPrepTools(
        db_session, Anonymizer(use_ner=False), profile_with_medication.id,
        exclude_appointment_ids=[appointment.id],
    )
    result = await tools.execute("lookup_past_visits", {})

    assert result == "No matching past visits found."


@pytest.fixture
async def profile_with_visit_history(db_session: AsyncSession) -> dict:
    """A patient with two providers and an interleaved visit history.

    Timeline (all completed):
        2023-01-10  Endocrinology  "Old endo checkup"
        2023-06-05  Cardiology     "Old cardiology consult"
        2024-01-15  Endocrinology  "Last endo visit"      <-- window anchor
        2024-03-20  Cardiology     "Cardiology follow-up"
        2024-07-02  Dermatology    "Skin check"

    Prepping the *next* Endocrinology visit should surface only what happened
    from 2024-01-15 onward — the two 2023 visits are what the unbounded query
    used to drag in.
    """
    profile = HealthProfile(name="History Patient", date_of_birth=date(1980, 5, 5))
    db_session.add(profile)
    await db_session.flush()

    endo = Doctor(profile_id=profile.id, name="Dr. Endo", specialty="Endocrinology")
    cardio = Doctor(profile_id=profile.id, name="Dr. Cardio", specialty="Cardiology")
    derm = Doctor(profile_id=profile.id, name="Dr. Derm", specialty="Dermatology")
    db_session.add_all([endo, cardio, derm])
    await db_session.flush()

    visits = [
        (endo, datetime(2023, 1, 10), "Old endo checkup"),
        (cardio, datetime(2023, 6, 5), "Old cardiology consult"),
        (endo, datetime(2024, 1, 15), "Last endo visit"),
        (cardio, datetime(2024, 3, 20), "Cardiology follow-up"),
        (derm, datetime(2024, 7, 2), "Skin check"),
    ]
    for doctor, when, purpose in visits:
        db_session.add(Appointment(
            profile_id=profile.id,
            doctor_id=doctor.id,
            scheduled_date=when,
            purpose=purpose,
            status="completed",
        ))

    # The appointment being prepped — still scheduled, not part of history.
    upcoming = Appointment(
        profile_id=profile.id,
        doctor_id=endo.id,
        scheduled_date=datetime(2024, 9, 1),
        purpose="Upcoming endo visit",
        status="scheduled",
    )
    db_session.add(upcoming)

    await db_session.commit()
    return {"profile": profile, "endo": endo, "cardio": cardio, "derm": derm, "upcoming": upcoming}


class TestLookupPastVisitsDefaultWindow:
    """Issue #21: with no explicit filters, `lookup_past_visits` defaults to
    'since the patient last saw this provider' instead of an unbounded dig
    through their entire history."""

    @pytest.mark.asyncio
    async def test_window_starts_at_last_visit_with_target_provider(
        self, db_session, profile_with_visit_history
    ):
        h = profile_with_visit_history
        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=h["endo"].id,
            current_appointment_id=h["upcoming"].id,
        )
        result = await tools.execute("lookup_past_visits", {})

        # On or after the 2024-01-15 anchor
        assert "Last endo visit" in result
        assert "Cardiology follow-up" in result
        assert "Skin check" in result
        # Before the anchor — previously returned, now windowed out
        assert "Old endo checkup" not in result
        assert "Old cardiology consult" not in result

    @pytest.mark.asyncio
    async def test_window_is_inclusive_of_the_anchor_visit(
        self, db_session, profile_with_visit_history
    ):
        """Per the issue's `scheduled_date >= last visit`, the anchoring visit
        is itself included — what was covered last time is useful context for
        what to follow up on."""
        h = profile_with_visit_history
        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=h["endo"].id,
            current_appointment_id=h["upcoming"].id,
        )
        result = await tools.execute("lookup_past_visits", {})
        assert "Last endo visit" in result

    @pytest.mark.asyncio
    async def test_no_prior_visit_with_provider_falls_back_to_unbounded(
        self, db_session, profile_with_visit_history
    ):
        """A provider the patient has never completed a visit with gives no
        date to anchor to — fall back to the previous unbounded behavior
        rather than inventing a default window."""
        h = profile_with_visit_history
        new_doctor = Doctor(
            profile_id=h["profile"].id, name="Dr. New", specialty="Neurology"
        )
        db_session.add(new_doctor)
        await db_session.commit()

        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=new_doctor.id,
        )
        result = await tools.execute("lookup_past_visits", {})

        assert "Old endo checkup" in result
        assert "Old cardiology consult" in result
        assert "Skin check" in result

    @pytest.mark.asyncio
    async def test_no_target_doctor_falls_back_to_unbounded(
        self, db_session, profile_with_visit_history
    ):
        """An appointment with no doctor set has no provider to anchor to."""
        h = profile_with_visit_history
        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=None,
        )
        result = await tools.execute("lookup_past_visits", {})
        assert "Old endo checkup" in result

    @pytest.mark.asyncio
    async def test_explicit_specialty_filter_searches_full_history(
        self, db_session, profile_with_visit_history
    ):
        """An explicit filter means the model is asking a targeted question, so
        the default window steps out of the way — otherwise asking for
        cardiology history would silently hide the pre-anchor cardiology visit
        the model was looking for."""
        h = profile_with_visit_history
        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=h["endo"].id,
            current_appointment_id=h["upcoming"].id,
        )
        result = await tools.execute("lookup_past_visits", {"specialty": "Cardiology"})

        assert "Old cardiology consult" in result  # pre-anchor, still found
        assert "Cardiology follow-up" in result
        assert "Skin check" not in result  # specialty filter still applies

    @pytest.mark.asyncio
    async def test_explicit_keyword_filter_searches_full_history(
        self, db_session, profile_with_visit_history
    ):
        h = profile_with_visit_history
        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=h["endo"].id,
            current_appointment_id=h["upcoming"].id,
        )
        result = await tools.execute("lookup_past_visits", {"keyword": "Old endo"})
        assert "Old endo checkup" in result

    @pytest.mark.asyncio
    async def test_window_composes_with_exclude_appointment_ids(
        self, db_session, profile_with_visit_history
    ):
        """DEC-024's exclusion and the new window are independent filters that
        must both apply — excluding the anchor visit from the *results* must not
        stop it anchoring the window."""
        h = profile_with_visit_history
        anchor = (
            await db_session.execute(
                select(Appointment).where(Appointment.purpose == "Last endo visit")
            )
        ).scalar_one()

        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            exclude_appointment_ids=[anchor.id],
            target_doctor_id=h["endo"].id,
            current_appointment_id=h["upcoming"].id,
        )
        result = await tools.execute("lookup_past_visits", {})

        # Excluded from results...
        assert "Last endo visit" not in result
        # ...but still anchored the window, so pre-anchor visits stay out.
        assert "Old endo checkup" not in result
        assert "Old cardiology consult" not in result
        # And post-anchor visits are still returned.
        assert "Cardiology follow-up" in result

    @pytest.mark.asyncio
    async def test_prepping_a_completed_appointment_does_not_anchor_to_itself(
        self, db_session, profile_with_visit_history
    ):
        """Prep can be re-run on an already-completed appointment. Without
        excluding it from the anchor query it would anchor to its own date and
        window out the history it's asking about — the same reason
        _get_past_appointments carries an `Appointment.id !=` guard."""
        h = profile_with_visit_history
        completed_endo = (
            await db_session.execute(
                select(Appointment).where(Appointment.purpose == "Last endo visit")
            )
        ).scalar_one()

        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=h["endo"].id,
            current_appointment_id=completed_endo.id,
        )
        result = await tools.execute("lookup_past_visits", {})

        # Anchors to the *previous* endo visit (2023-01-10), not to itself.
        assert "Old endo checkup" in result
        assert "Old cardiology consult" in result

    @pytest.mark.asyncio
    async def test_cancelled_visits_do_not_anchor_the_window(
        self, db_session, profile_with_visit_history
    ):
        """Only completed visits count as "last saw this provider" — a
        cancelled appointment isn't a visit."""
        h = profile_with_visit_history
        db_session.add(Appointment(
            profile_id=h["profile"].id,
            doctor_id=h["endo"].id,
            scheduled_date=datetime(2024, 8, 1),
            purpose="Cancelled endo visit",
            status="cancelled",
        ))
        await db_session.commit()

        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), h["profile"].id,
            target_doctor_id=h["endo"].id,
            current_appointment_id=h["upcoming"].id,
        )
        result = await tools.execute("lookup_past_visits", {})

        # Still anchored to 2024-01-15, not the 2024-08-01 cancellation.
        assert "Last endo visit" in result
        assert "Cardiology follow-up" in result
        assert "Cancelled endo visit" not in result

    @pytest.mark.asyncio
    async def test_backwards_compatible_when_no_window_args_supplied(
        self, db_session, profile_with_medication
    ):
        """Constructing VisitPrepTools without the new args behaves exactly as
        before — the window is opt-in via the call site."""
        tools = VisitPrepTools(
            db_session, Anonymizer(use_ner=False), profile_with_medication.id
        )
        result = await tools.execute("lookup_past_visits", {})
        assert "Routine diabetes checkup" in result


@pytest.mark.asyncio
async def test_unknown_tool_name(db_session, profile_with_medication):
    tools = VisitPrepTools(db_session, Anonymizer(use_ner=False), profile_with_medication.id)

    with pytest.raises(UnknownToolError, match="not_a_real_tool"):
        await tools.execute("not_a_real_tool", {})
