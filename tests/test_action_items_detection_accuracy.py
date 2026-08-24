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

    # Ground truth: exact-date matching, not proximity. A document dated
    # exactly on an appointment's date covers it; a document even 1 day off
    # does not — there is no tolerance window, since a wide window is what
    # caused the cross-appointment false negative documented below.
    appt_exact_match = await _make_appointment(db_session, profile_id, now - timedelta(days=100), status="completed")
    doc_date_exact = appt_exact_match.scheduled_date.strftime("%m/%d/%Y")
    await _make_document(db_session, profile_id, visit_date=doc_date_exact)

    appt_1_day_off = await _make_appointment(db_session, profile_id, now - timedelta(days=200), status="completed")
    doc_date_1_off = (appt_1_day_off.scheduled_date + timedelta(days=1)).strftime("%m/%d/%Y")
    await _make_document(db_session, profile_id, visit_date=doc_date_1_off)

    appt_no_doc = await _make_appointment(db_session, profile_id, now - timedelta(days=300), status="completed")

    appt_still_scheduled = await _make_appointment(db_session, profile_id, now + timedelta(days=5), status="scheduled")

    resp = await client.get(f"/api/profiles/{profile_id}/completed-without-avs")
    ids = {a["id"] for a in resp.json()}

    assert appt_exact_match.id not in ids, "doc dated exactly on the appointment date should count as covered"
    assert appt_1_day_off.id in ids, "doc dated 1 day off is not an exact match — should still fire, no tolerance window"
    assert appt_no_doc.id in ids, "no document at all — should fire"
    assert appt_still_scheduled.id not in ids, "not completed — should not be evaluated"


@pytest.mark.asyncio
async def test_completed_without_avs_cross_appointment_false_negative_fixed(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
):
    """Regression test for the false negative this module previously had:
    a document uploaded for one completed appointment used to be able to
    silently suppress the missing-AVS nudge for a different completed
    appointment within ~28 days of it, because matching was by date
    proximity across the whole profile rather than by exact date. Fixed by
    matching on exact visit-date equality — two appointments on different
    dates can no longer share a document.
    """
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)

    appt_with_doc = await _make_appointment(db_session, profile_id, now - timedelta(days=20), status="completed")
    appt_without_doc = await _make_appointment(db_session, profile_id, now - timedelta(days=22), status="completed")
    doc_date = appt_with_doc.scheduled_date.strftime("%m/%d/%Y")
    await _make_document(db_session, profile_id, visit_date=doc_date)

    resp = await client.get(f"/api/profiles/{profile_id}/completed-without-avs")
    ids = {a["id"] for a in resp.json()}

    assert appt_with_doc.id not in ids  # correctly suppressed — it has a real, exact-date-matched document
    assert appt_without_doc.id in ids, (
        "fixed behavior: a document dated for a different appointment, even one "
        "only 2 days apart, must not suppress this appointment's own missing-AVS nudge"
    )


@pytest.mark.asyncio
async def test_completed_without_avs_same_day_disambiguated_by_provider(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
):
    """Two completed appointments on the exact same date (different
    specialists seen same day) is the one case exact-date matching alone
    cannot resolve. A document should only cover the appointment whose
    doctor's name/clinic plausibly matches the document's parsed
    provider/facility — not either same-date appointment interchangeably.
    """
    from src.data.models import Doctor

    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)
    same_date = now - timedelta(days=20)

    dermatologist = Doctor(profile_id=profile_id, name="Eliana Krulig, MD", clinic="Sutter Dermatology")
    endocrinologist = Doctor(profile_id=profile_id, name="D.M. Antoniucci, MD", clinic="Sutter Endocrinology")
    db_session.add_all([dermatologist, endocrinologist])
    await db_session.commit()
    await db_session.refresh(dermatologist)
    await db_session.refresh(endocrinologist)

    derm_appt = Appointment(profile_id=profile_id, doctor_id=dermatologist.id, scheduled_date=same_date, status="completed")
    endo_appt = Appointment(profile_id=profile_id, doctor_id=endocrinologist.id, scheduled_date=same_date, status="completed")
    db_session.add_all([derm_appt, endo_appt])
    await db_session.commit()
    await db_session.refresh(derm_appt)
    await db_session.refresh(endo_appt)

    # Document's parsed provider matches the dermatologist, not the endocrinologist.
    doc = Document(
        profile_id=profile_id,
        original_filename="derm_avs.pdf",
        file_path="/tmp/derm_avs.pdf",
        file_size_bytes=100,
        visit_date=same_date.strftime("%m/%d/%Y"),
        provider_name="Eliana Krulig, MD",
        facility_name="Sutter Dermatology",
        parse_status="completed",
    )
    db_session.add(doc)
    await db_session.commit()

    resp = await client.get(f"/api/profiles/{profile_id}/completed-without-avs")
    ids = {a["id"] for a in resp.json()}

    assert derm_appt.id not in ids, "document's provider matches the dermatologist — should be covered"
    assert endo_appt.id in ids, "document's provider does not match the endocrinologist — should still fire"


@pytest.mark.asyncio
async def test_completed_without_avs_same_day_no_provider_match_stays_ambiguous(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
):
    """When two same-date completed appointments exist and the document has
    no parseable provider information (or neither appointment has a linked
    doctor), the ambiguity cannot be resolved. Fail-safe direction: neither
    appointment is marked covered, rather than guessing — a false
    "still needs attention" nudge is preferable to silently clearing a
    genuine gap.
    """
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    now = datetime.now(timezone.utc)
    same_date = now - timedelta(days=20)

    appt_a = await _make_appointment(db_session, profile_id, same_date, status="completed")
    appt_b = await _make_appointment(db_session, profile_id, same_date, status="completed")
    # No doctor_id on either appointment, no provider_name on the document —
    # nothing to disambiguate with.
    await _make_document(db_session, profile_id, visit_date=same_date.strftime("%m/%d/%Y"))

    resp = await client.get(f"/api/profiles/{profile_id}/completed-without-avs")
    ids = {a["id"] for a in resp.json()}

    assert appt_a.id in ids, "no provider info to disambiguate — should not silently mark as covered"
    assert appt_b.id in ids, "no provider info to disambiguate — should not silently mark as covered"


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
