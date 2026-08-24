"""Detection accuracy for the Needs Attention / disengagement-detection panel
(paper evaluation piece — issue #122 follow-up family).

tests/test_action_items.py covers snooze/unsnooze *behavior*. This file
covers detection *correctness*: given synthetic scenarios with a known
ground-truth label (should this nudge fire, yes/no), does each endpoint
return exactly the right set, including boundary cases around the 14-day
completed_without_avs rule where off-by-one errors are most likely.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Appointment, Document, Vitals, VisitPrep


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _make_appointment(
    db_session: AsyncSession, profile_id: str, scheduled_date: datetime, status: str = "scheduled",
) -> Appointment:
    appt = Appointment(profile_id=profile_id, scheduled_date=scheduled_date, status=status)
    db_session.add(appt)
    await db_session.commit()
    await db_session.refresh(appt)
    return appt


async def _make_document(
    db_session: AsyncSession, profile_id: str, visit_date: str, appointment_id: str | None = None,
) -> Document:
    doc = Document(
        profile_id=profile_id,
        appointment_id=appointment_id,
        original_filename="avs.pdf",
        file_path="/tmp/avs.pdf",
        file_size_bytes=100,
        visit_date=visit_date,
        parse_status="completed",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def _make_vitals(db_session: AsyncSession, profile_id: str, document_id: str, **kwargs) -> Vitals:
    v = Vitals(profile_id=profile_id, document_id=document_id, **kwargs)
    db_session.add(v)
    await db_session.commit()
    await db_session.refresh(v)
    return v


# ── past_due ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_past_due_detection_accuracy(client: AsyncClient, db_session: AsyncSession, sample_profile_data):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)

    past_scheduled = await _make_appointment(db_session, profile_id, now - timedelta(days=5), status="scheduled")
    past_completed = await _make_appointment(db_session, profile_id, now - timedelta(days=5), status="completed")
    future_scheduled = await _make_appointment(db_session, profile_id, now + timedelta(days=5), status="scheduled")

    resp = await client.get(f"/api/profiles/{profile_id}/past-due-appointments")
    ids = {a["id"] for a in resp.json()}

    assert ids == {past_scheduled.id}, f"expected only {past_scheduled.id}, got {ids}"
    assert past_completed.id not in ids  # already closed out — should not fire
    assert future_scheduled.id not in ids  # not past due yet


# ── upcoming_without_prep ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upcoming_without_prep_detection_accuracy(client: AsyncClient, db_session: AsyncSession, sample_profile_data):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)

    no_prep = await _make_appointment(db_session, profile_id, now + timedelta(days=10))
    has_prep = await _make_appointment(db_session, profile_id, now + timedelta(days=10))
    db_session.add(VisitPrep(appointment_id=has_prep.id, generated_questions={"q": ["x"]}))
    await db_session.commit()
    too_far_out = await _make_appointment(db_session, profile_id, now + timedelta(days=45))
    past_no_prep = await _make_appointment(db_session, profile_id, now - timedelta(days=5))

    resp = await client.get(f"/api/profiles/{profile_id}/upcoming-without-prep")
    ids = {a["id"] for a in resp.json()}

    assert ids == {no_prep.id}, f"expected only {no_prep.id}, got {ids}"
    assert has_prep.id not in ids  # already prepped — should not fire
    assert too_far_out.id not in ids  # outside default 30-day window
    assert past_no_prep.id not in ids  # not upcoming


# ── completed_without_avs — boundary cases around the 14-day rule ─────────

@pytest.mark.asyncio
async def test_completed_without_avs_14_day_boundary(client: AsyncClient, db_session: AsyncSession, sample_profile_data):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)

    # Ground truth: each appointment's own date, spaced far apart (>>14 days
    # from each other) so each one's document-proximity check is isolated —
    # _doc_near_appointment matches ANY parsed document for the profile
    # within 14 days of a given appointment's date, not a document tied to
    # that specific appointment_id, so appointments placed close together
    # would otherwise contaminate each other's ground truth (see the
    # separate cross-appointment ambiguity test below).
    appt_exactly_14 = await _make_appointment(db_session, profile_id, now - timedelta(days=100), status="completed")
    doc_date_14 = (appt_exactly_14.scheduled_date + timedelta(days=14)).strftime("%m/%d/%Y")
    await _make_document(db_session, profile_id, visit_date=doc_date_14)

    appt_15_days_late = await _make_appointment(db_session, profile_id, now - timedelta(days=200), status="completed")
    doc_date_15 = (appt_15_days_late.scheduled_date + timedelta(days=15)).strftime("%m/%d/%Y")
    await _make_document(db_session, profile_id, visit_date=doc_date_15)

    appt_no_doc = await _make_appointment(db_session, profile_id, now - timedelta(days=300), status="completed")

    appt_still_scheduled = await _make_appointment(db_session, profile_id, now + timedelta(days=5), status="scheduled")

    resp = await client.get(f"/api/profiles/{profile_id}/completed-without-avs")
    ids = {a["id"] for a in resp.json()}

    assert appt_exactly_14.id not in ids, "doc at exactly 14 days should count as near — false positive"
    assert appt_15_days_late.id in ids, "doc at 15 days is outside the window — should still fire, false negative if missing"
    assert appt_no_doc.id in ids, "no document at all — should fire"
    assert appt_still_scheduled.id not in ids, "not completed — should not be evaluated"


@pytest.mark.asyncio
async def test_completed_without_avs_cross_appointment_document_ambiguity(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
):
    """_doc_near_appointment matches ANY parsed document for the profile
    within 14 days of an appointment's date — it does not check the
    document's appointment_id. Two completed appointments close together
    in time can therefore contaminate each other's detection: uploading a
    document for one can incorrectly suppress the nudge for the other,
    which truly has no document of its own. This is a real detection gap,
    not a hypothetical — documented here as a known limitation rather than
    silently left for a future bug report.
    """
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)

    appt_with_doc = await _make_appointment(db_session, profile_id, now - timedelta(days=20), status="completed")
    appt_without_doc = await _make_appointment(db_session, profile_id, now - timedelta(days=22), status="completed")
    # Document uploaded for appt_with_doc only, not linked via appointment_id
    # to either appointment (matches how completed_appointments_without_avs
    # actually queries — by parse_status, not appointment_id).
    doc_date = appt_with_doc.scheduled_date.strftime("%m/%d/%Y")
    await _make_document(db_session, profile_id, visit_date=doc_date)

    resp = await client.get(f"/api/profiles/{profile_id}/completed-without-avs")
    ids = {a["id"] for a in resp.json()}

    assert appt_with_doc.id not in ids  # correctly suppressed — it has a real document
    # This assertion documents the actual (undesired) current behavior: the
    # nearby document for appt_with_doc also suppresses appt_without_doc's
    # nudge, a false negative, because proximity is checked profile-wide
    # rather than per-appointment. If this assertion starts failing, the
    # underlying gap has been fixed — update this test to assert the
    # correct behavior at that point.
    assert appt_without_doc.id not in ids, (
        "documents current false-negative behavior: a document 2 days apart "
        "from a doc-less appointment incorrectly suppresses that appointment's "
        "nudge too, since matching is profile-wide, not appointment-specific"
    )


# ── vitals_alert — threshold boundaries ────────────────────────────────────

@pytest.mark.asyncio
async def test_vitals_alert_weight_threshold_boundary(client: AsyncClient, db_session: AsyncSession, sample_profile_data):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    # Below threshold: 4.9 lb change should NOT alert (threshold is >=5).
    doc1 = await _make_document(db_session, profile_id, visit_date="01/01/2026")
    await _make_vitals(db_session, profile_id, doc1.id, weight="180 lbs", measured_date="2026-01-01")
    doc2 = await _make_document(db_session, profile_id, visit_date="02/01/2026")
    await _make_vitals(db_session, profile_id, doc2.id, weight="184.9 lbs", measured_date="2026-02-01")

    resp = await client.get(f"/api/profiles/{profile_id}/vitals-alerts")
    alerts = resp.json()
    weight_alerts = [a for a in alerts if a["metric"] == "Weight"]
    assert weight_alerts == [], f"4.9 lb change is below the 5 lb threshold — should not alert, got {weight_alerts}"


@pytest.mark.asyncio
async def test_vitals_alert_weight_at_threshold_fires(client: AsyncClient, db_session: AsyncSession, sample_profile_data):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    # At threshold: exactly 5.0 lb change SHOULD alert (>=5).
    doc1 = await _make_document(db_session, profile_id, visit_date="01/01/2026")
    await _make_vitals(db_session, profile_id, doc1.id, weight="180 lbs", measured_date="2026-01-01")
    doc2 = await _make_document(db_session, profile_id, visit_date="02/01/2026")
    await _make_vitals(db_session, profile_id, doc2.id, weight="185 lbs", measured_date="2026-02-01")

    resp = await client.get(f"/api/profiles/{profile_id}/vitals-alerts")
    alerts = resp.json()
    weight_alerts = [a for a in alerts if a["metric"] == "Weight"]
    assert len(weight_alerts) == 1, f"exactly 5 lb change should alert (>=5 threshold), got {weight_alerts}"


@pytest.mark.asyncio
async def test_vitals_alert_single_reading_never_fires(client: AsyncClient, db_session: AsyncSession, sample_profile_data):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    doc1 = await _make_document(db_session, profile_id, visit_date="01/01/2026")
    await _make_vitals(db_session, profile_id, doc1.id, weight="250 lbs", measured_date="2026-01-01")

    resp = await client.get(f"/api/profiles/{profile_id}/vitals-alerts")
    assert resp.json() == [], "a single vitals reading has no trend and should never alert, regardless of value"
