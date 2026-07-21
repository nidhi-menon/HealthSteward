"""Tests for action-item snoozing, including issue #44's currently-snoozed view."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Document, FollowUp, LabOrder, Referral


async def _make_document(db_session: AsyncSession, profile_id: str) -> str:
    doc = Document(
        profile_id=profile_id,
        original_filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_size_bytes=100,
        parse_status="completed",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc.id


@pytest.mark.asyncio
async def test_snoozed_follow_up_excluded_from_active_list_and_shown_in_snoozed_items(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
):
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]
    document_id = await _make_document(db_session, profile_id)

    follow_up = FollowUp(
        profile_id=profile_id, document_id=document_id, description="Recheck blood pressure",
    )
    db_session.add(follow_up)
    await db_session.commit()
    await db_session.refresh(follow_up)

    # Snooze it
    snoozed_until = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    resp = await client.patch(
        f"/api/profiles/{profile_id}/follow-ups/{follow_up.id}",
        json={"snoozed_until": snoozed_until},
    )
    assert resp.status_code == 200

    # Excluded from the active list
    active = await client.get(f"/api/profiles/{profile_id}/follow-ups")
    assert follow_up.id not in [f["id"] for f in active.json()]

    # Visible in the unified snoozed-items view
    snoozed_resp = await client.get(f"/api/profiles/{profile_id}/snoozed-items")
    assert snoozed_resp.status_code == 200
    snoozed_items = snoozed_resp.json()
    assert len(snoozed_items) == 1
    assert snoozed_items[0]["category"] == "follow_up"
    assert snoozed_items[0]["item_id"] == follow_up.id
    assert snoozed_items[0]["label"] == "Recheck blood pressure"

    # Un-snooze early via the existing null-out path (already supported per #44's scope)
    unsnooze_resp = await client.patch(
        f"/api/profiles/{profile_id}/follow-ups/{follow_up.id}",
        json={"snoozed_until": None},
    )
    assert unsnooze_resp.status_code == 200

    active_again = await client.get(f"/api/profiles/{profile_id}/follow-ups")
    assert follow_up.id in [f["id"] for f in active_again.json()]

    snoozed_again = await client.get(f"/api/profiles/{profile_id}/snoozed-items")
    assert snoozed_again.json() == []


@pytest.mark.asyncio
async def test_snoozed_lab_order_and_referral_appear_in_snoozed_items(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
):
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]
    document_id = await _make_document(db_session, profile_id)

    lab = LabOrder(profile_id=profile_id, document_id=document_id, test_name="A1C")
    referral = Referral(
        profile_id=profile_id, document_id=document_id, specialty="Cardiology", provider_name="Dr. Lee",
    )
    db_session.add_all([lab, referral])
    await db_session.commit()
    await db_session.refresh(lab)
    await db_session.refresh(referral)

    snoozed_until = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    await client.patch(f"/api/profiles/{profile_id}/lab-orders/{lab.id}", json={"snoozed_until": snoozed_until})
    await client.patch(f"/api/profiles/{profile_id}/referrals/{referral.id}", json={"snoozed_until": snoozed_until})

    snoozed_resp = await client.get(f"/api/profiles/{profile_id}/snoozed-items")
    items_by_category = {i["category"]: i for i in snoozed_resp.json()}
    assert items_by_category["lab_order"]["label"] == "A1C"
    assert items_by_category["referral"]["label"] == "Cardiology — Dr. Lee"


@pytest.mark.asyncio
async def test_snoozed_nudge_appears_in_snoozed_items_with_appointment_label_and_can_be_unsnoozed(
    client: AsyncClient, sample_profile_data, sample_doctor_data, sample_appointment_data,
):
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    doctor_response = await client.post(f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data)
    doctor_id = doctor_response.json()["id"]

    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appt_response = await client.post(f"/api/profiles/{profile_id}/appointments/", json=appointment_data)
    appointment_id = appt_response.json()["id"]

    snoozed_until = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    snooze_resp = await client.post(
        f"/api/profiles/{profile_id}/nudge-states",
        json={"nudge_type": "past_due", "item_id": appointment_id, "snoozed_until": snoozed_until},
    )
    assert snooze_resp.status_code == 200

    snoozed_resp = await client.get(f"/api/profiles/{profile_id}/snoozed-items")
    items = snoozed_resp.json()
    assert len(items) == 1
    assert items[0]["category"] == "past_due"
    assert sample_doctor_data["name"] in items[0]["label"]

    # Un-snooze early via the new DELETE endpoint (#44's "un-snooze now" action)
    delete_resp = await client.delete(f"/api/profiles/{profile_id}/nudge-states/past_due/{appointment_id}")
    assert delete_resp.status_code == 204

    snoozed_again = await client.get(f"/api/profiles/{profile_id}/snoozed-items")
    assert snoozed_again.json() == []


@pytest.mark.asyncio
async def test_unsnooze_nonexistent_nudge_returns_404(client: AsyncClient, sample_profile_data):
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    resp = await client.delete(f"/api/profiles/{profile_id}/nudge-states/past_due/nonexistent-id")
    assert resp.status_code == 404
