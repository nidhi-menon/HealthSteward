"""Tests for applying parsed AVS items, and for the pre-apply diff preview (issue #46).

The preview tests lean on one invariant above all others: preview and apply must
derive their plan from the same code path, so what the user reviews is exactly
what gets written. The `test_preview_and_apply_agree_*` cases exist to catch
drift between the two endpoints if either is ever edited in isolation.
"""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import (
    Appointment,
    Condition,
    Document,
    FollowUp,
    LabOrder,
    Medication,
    Referral,
    Vitals,
)

# A visit date far enough in the future that `_is_newer` always treats the AVS
# as newer than a record's `updated_at`; and one far enough in the past that it
# never does. Both avoid wall-clock flakiness.
FUTURE_VISIT = "12/31/2099"
PAST_VISIT = "01/01/2000"


async def _make_document(
    db_session: AsyncSession,
    profile_id: str,
    visit_date: str | None = FUTURE_VISIT,
    provider_name: str | None = None,
) -> str:
    doc = Document(
        profile_id=profile_id,
        original_filename="avs.pdf",
        file_path="/tmp/avs.pdf",
        file_size_bytes=100,
        parse_status="completed",
        visit_date=visit_date,
        provider_name=provider_name,
        raw_parse_result={},
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc.id


def _payload(**overrides) -> dict:
    """An empty apply request, with only the keys under test filled in."""
    body = {
        "diagnoses": [],
        "medication_starts": [],
        "medication_stops": [],
        "medication_updates": [],
        "vitals": None,
        "lab_orders": [],
        "referrals": [],
        "follow_ups": [],
        "appointments": [],
    }
    body.update(overrides)
    return body


async def _profile(client: AsyncClient, sample_profile_data) -> str:
    resp = await client.post("/api/profiles/", json=sample_profile_data)
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Apply behaviour (characterisation: these describe what apply has always done)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_diagnosis_creates_a_condition(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(diagnoses=[{
            "condition": "Hypertension",
            "icd_10": "I10",
            "severity": "moderate",
            "status": "active",
        }]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["conditions"] == 1

    result = await db_session.execute(
        select(Condition).where(Condition.profile_id == profile_id)
    )
    conditions = result.scalars().all()
    assert [c.name for c in conditions] == ["Hypertension"]
    assert conditions[0].icd_10 == "I10"


@pytest.mark.asyncio
async def test_matching_diagnosis_overwrites_fields_when_the_visit_is_newer(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    existing = Condition(
        profile_id=profile_id, name="Hypertension", icd_10=None,
        severity="mild", status="active",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(diagnoses=[{
            "condition": "Hypertension",
            "icd_10": "I10",
            "severity": "severe",
            "status": "chronic",
        }]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["conditions"] == 1
    assert resp.json()["skipped"]["conditions"] == 0

    await db_session.refresh(existing)
    assert existing.icd_10 == "I10"
    assert existing.severity == "severe"
    assert existing.status == "chronic"


@pytest.mark.asyncio
async def test_matching_diagnosis_is_skipped_when_the_record_is_newer(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id, visit_date=PAST_VISIT)

    existing = Condition(
        profile_id=profile_id, name="Hypertension", icd_10="I10",
        severity="mild", status="active",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(diagnoses=[{
            "condition": "Hypertension", "icd_10": "I11", "severity": "severe",
        }]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["conditions"] == 0
    assert resp.json()["skipped"]["conditions"] == 1

    await db_session.refresh(existing)
    assert existing.severity == "mild"
    assert existing.icd_10 == "I10"


@pytest.mark.asyncio
async def test_medication_start_creates_when_unmatched_and_updates_when_matched(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    existing = Medication(
        profile_id=profile_id, name="Metformin", dosage="500mg", frequency="daily",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(medication_starts=[
            {"name": "Metformin", "action": "start", "strength": "1000mg",
             "instructions": "twice daily"},
            {"name": "Lisinopril", "action": "start", "strength": "10mg"},
        ]),
    )
    assert resp.status_code == 200
    # A matched-and-updated start is not counted as "started" — only the
    # genuinely new medication is.
    assert resp.json()["counts"]["medications_started"] == 1

    await db_session.refresh(existing)
    assert existing.dosage == "1000mg"
    assert existing.frequency == "twice daily"

    result = await db_session.execute(
        select(Medication).where(Medication.profile_id == profile_id)
    )
    assert sorted(m.name for m in result.scalars().all()) == ["Lisinopril", "Metformin"]


@pytest.mark.asyncio
async def test_medication_stop_sets_end_date(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    existing = Medication(profile_id=profile_id, name="Metformin", dosage="500mg")
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(medication_stops=[
            {"name": "Metformin", "action": "stop", "date": "06/01/2026"},
        ]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["medications_stopped"] == 1

    await db_session.refresh(existing)
    assert existing.end_date == date(2026, 6, 1)


@pytest.mark.asyncio
async def test_medication_update_changes_dosage_and_frequency(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    existing = Medication(
        profile_id=profile_id, name="Metformin", dosage="500mg", frequency="daily",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(medication_updates=[
            {"name": "Metformin", "action": "changed", "strength": "850mg",
             "instructions": "three times daily"},
        ]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["medications_updated"] == 1

    await db_session.refresh(existing)
    assert existing.dosage == "850mg"
    assert existing.frequency == "three times daily"


@pytest.mark.asyncio
async def test_duplicate_lab_orders_referrals_and_follow_ups_are_skipped(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    db_session.add_all([
        LabOrder(profile_id=profile_id, document_id=document_id,
                 test_name="CBC", ordered_date="06/01/2026"),
        Referral(profile_id=profile_id, document_id=document_id, specialty="Cardiology"),
        FollowUp(profile_id=profile_id, document_id=document_id,
                 description="Recheck BP in 3 months"),
    ])
    await db_session.commit()

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(
            lab_orders=[{"test": "CBC", "ordered_date": "06/01/2026"}],
            referrals=[{"specialty": "Cardiology"}],
            follow_ups=[{"description": "Recheck BP in 3 months"}],
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"]["lab_orders"] == 1
    assert body["skipped"]["referrals"] == 1
    assert body["skipped"]["follow_ups"] == 1
    assert body["counts"]["lab_orders"] == 0


@pytest.mark.asyncio
async def test_vitals_are_recorded_and_undated_appointments_are_skipped(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(
            vitals={"weight": "180 lb", "blood_pressure": "128/82"},
            appointments=[{"description": "Follow-up visit", "date": None}],
        ),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["vitals"] == 1
    assert resp.json()["skipped"]["appointments"] == 1

    result = await db_session.execute(
        select(Vitals).where(Vitals.profile_id == profile_id)
    )
    vitals = result.scalars().all()
    assert len(vitals) == 1
    assert vitals[0].blood_pressure == "128/82"


@pytest.mark.asyncio
async def test_dated_appointment_is_created_with_a_matched_doctor(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(appointments=[
            {"description": "Video Visit with D.M. Antoniucci, MD",
             "date": "09/15/2026", "location": "City Medical"},
        ]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["appointments"] == 1

    result = await db_session.execute(
        select(Appointment).where(Appointment.profile_id == profile_id)
    )
    appointments = result.scalars().all()
    assert len(appointments) == 1
    assert appointments[0].scheduled_date.date() == date(2026, 9, 15)
    assert appointments[0].doctor_id is not None


# ---------------------------------------------------------------------------
# Pre-apply diff preview (issue #46)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_reports_field_level_changes_without_writing(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    existing = Condition(
        profile_id=profile_id, name="Hypertension", icd_10="I10",
        severity="mild", status="active",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply/preview",
        json=_payload(diagnoses=[{
            "condition": "Hypertension", "icd_10": "I10", "severity": "severe",
        }]),
    )
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["plan_fingerprint"]

    entry = next(e for e in plan["entries"] if e["entity_type"] == "condition")
    assert entry["action"] == "update"
    assert entry["entity_id"] == existing.id

    changes = {c["field"]: c for c in entry["changes"]}
    assert changes["severity"]["old_value"] == "mild"
    assert changes["severity"]["new_value"] == "severe"
    assert changes["severity"]["changed"] is True
    # Same value in and out — surfaced, but flagged as a no-op so the UI can
    # collapse it rather than showing it as an edit.
    assert changes["icd_10"]["changed"] is False

    # Nothing was written.
    await db_session.refresh(existing)
    assert existing.severity == "mild"


@pytest.mark.asyncio
async def test_preview_explains_why_an_item_will_be_skipped(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id, visit_date=PAST_VISIT)

    existing = Condition(
        profile_id=profile_id, name="Hypertension", severity="mild", status="active",
    )
    db_session.add(existing)
    await db_session.commit()

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply/preview",
        json=_payload(diagnoses=[{"condition": "Hypertension", "severity": "severe"}]),
    )
    assert resp.status_code == 200

    entry = next(e for e in resp.json()["entries"] if e["entity_type"] == "condition")
    assert entry["action"] == "skip"
    assert "newer" in (entry["reason"] or "")


@pytest.mark.asyncio
async def test_preview_and_apply_agree_on_the_same_input(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    """The guard against preview/apply drift: same input, same derived plan."""
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    db_session.add_all([
        Condition(profile_id=profile_id, name="Hypertension", severity="mild"),
        Medication(profile_id=profile_id, name="Metformin", dosage="500mg"),
    ])
    await db_session.commit()

    body = _payload(
        diagnoses=[{"condition": "Hypertension", "severity": "severe"}],
        medication_starts=[{"name": "Lisinopril", "action": "start", "strength": "10mg"}],
        medication_updates=[{"name": "Metformin", "action": "changed", "strength": "850mg"}],
        follow_ups=[{"description": "Recheck BP"}],
    )

    preview = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply/preview", json=body
    )
    assert preview.status_code == 200
    projected = preview.json()

    applied = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply", json=body
    )
    assert applied.status_code == 200

    assert projected["counts"] == applied.json()["counts"]
    assert projected["skipped"] == applied.json()["skipped"]


@pytest.mark.asyncio
async def test_apply_aborts_when_the_profile_changed_since_the_preview(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    existing = Condition(
        profile_id=profile_id, name="Hypertension", severity="mild", status="active",
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    body = _payload(diagnoses=[{"condition": "Hypertension", "severity": "severe"}])
    preview = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply/preview", json=body
    )
    fingerprint = preview.json()["plan_fingerprint"]

    # Someone edits the same record in another tab between review and confirm.
    existing.severity = "moderate"
    await db_session.commit()

    stale = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json={**body, "expected_plan_fingerprint": fingerprint},
    )
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["reason"] == "stale_plan"
    assert detail["plan"]["plan_fingerprint"] != fingerprint

    # The aborted apply wrote nothing.
    await db_session.refresh(existing)
    assert existing.severity == "moderate"

    # Re-previewing and confirming with the fresh fingerprint succeeds.
    fresh = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply/preview", json=body
    )
    confirmed = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json={**body, "expected_plan_fingerprint": fresh.json()["plan_fingerprint"]},
    )
    assert confirmed.status_code == 200
    await db_session.refresh(existing)
    assert existing.severity == "severe"


@pytest.mark.asyncio
async def test_apply_without_a_fingerprint_still_works(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    """The guard is opt-in at the API layer so existing callers keep working."""
    profile_id = await _profile(client, sample_profile_data)
    document_id = await _make_document(db_session, profile_id)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{document_id}/apply",
        json=_payload(diagnoses=[{"condition": "Asthma"}]),
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["conditions"] == 1


@pytest.mark.asyncio
async def test_preview_requires_a_parsed_document(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id = await _profile(client, sample_profile_data)
    doc = Document(
        profile_id=profile_id, original_filename="avs.pdf", file_path="/tmp/avs.pdf",
        file_size_bytes=100, parse_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.post(
        f"/api/profiles/{profile_id}/documents/{doc.id}/apply/preview", json=_payload()
    )
    assert resp.status_code == 400

    missing = await client.post(
        f"/api/profiles/{profile_id}/documents/does-not-exist/apply/preview",
        json=_payload(),
    )
    assert missing.status_code == 404
