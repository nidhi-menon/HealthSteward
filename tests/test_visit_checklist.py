"""Tests for the deterministic pre-visit "what to bring" checklist (issue #110).

Split deliberately: the rule tests call `build_checklist` directly, because the
rules are the thing worth pinning and they are pure. The endpoint tests only
check that the right facts are read out of the database and handed to it.
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Appointment, Doctor, LabOrder, Medication, Referral, VisitPrep
from src.services.visit_checklist import build_checklist


def _ids(**overrides) -> list[str]:
    """Run the rules with everything off unless a test turns it on."""
    kwargs = {
        "specialty": None,
        "purpose": None,
        "is_first_visit_with_doctor": False,
        "has_medications": False,
        "has_allergies": False,
        "has_prep_questions": False,
        "open_referral_count": 0,
        "open_lab_order_count": 0,
    }
    kwargs.update(overrides)
    return [item.id for item in build_checklist(**kwargs)]


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def test_an_empty_profile_produces_an_empty_checklist():
    """No invented advice: with nothing known, the list stays empty."""
    assert _ids() == []


def test_baseline_items_track_what_the_profile_actually_holds():
    assert _ids(has_medications=True) == ["medication_list"]
    assert _ids(has_allergies=True) == ["allergy_list"]
    assert _ids(has_prep_questions=True) == ["prep_questions"]


def test_a_first_visit_adds_the_new_patient_paperwork():
    ids = _ids(is_first_visit_with_doctor=True)
    assert ids == ["photo_id_and_insurance", "pharmacy_details", "past_medical_history"]


def test_specialty_is_matched_as_a_substring_of_free_text():
    # `Doctor.specialty` is free text, so the rule has to survive a qualifier.
    assert "home_bp_readings" in _ids(specialty="Interventional Cardiology")
    assert "home_bp_readings" in _ids(specialty="cardiology")
    assert "home_bp_readings" not in _ids(specialty="Dermatology")


def test_purpose_keywords_drive_visit_shape_items():
    assert "referral_paperwork" in _ids(purpose="Specialist referral visit")
    assert "symptom_changes" in _ids(purpose="3 month follow-up")
    assert "symptom_changes" in _ids(purpose="Follow up on knee")
    assert "fasting_instructions" in _ids(purpose="Fasting lipid panel")
    assert "ride_home" in _ids(purpose="Pre-op consult before surgery")
    assert "vaccination_records" in _ids(purpose="Annual physical")


def test_an_unrecognised_purpose_adds_nothing():
    """The known weak spot of keyword matching, pinned rather than hidden (#144)."""
    assert _ids(purpose="come back in 3mo to recheck the thyroid") == ["symptom_changes"]
    assert _ids(purpose="chat about the thing we discussed") == []


def test_outstanding_paperwork_is_called_out_with_a_count():
    items = build_checklist(
        specialty=None, purpose=None, is_first_visit_with_doctor=False,
        has_medications=False, has_allergies=False, has_prep_questions=False,
        open_referral_count=2, open_lab_order_count=1,
    )
    by_id = {item.id: item for item in items}
    assert "2 referrals" in by_id["referral_paperwork"].why
    assert "1 lab order" in by_id["lab_order_slip"].why


def test_an_item_produced_by_two_rules_appears_once_with_both_sources():
    items = build_checklist(
        specialty="Orthopedics", purpose="Follow-up on MRI results",
        is_first_visit_with_doctor=False, has_medications=False,
        has_allergies=False, has_prep_questions=False,
        open_referral_count=0, open_lab_order_count=0,
    )
    imaging = [item for item in items if item.id == "prior_imaging"]
    assert len(imaging) == 1
    assert imaging[0].sources == ("specialty:orthoped", "purpose:mri")


def test_the_same_inputs_always_produce_the_same_list():
    kwargs = dict(
        specialty="Cardiology", purpose="Annual physical and blood work",
        is_first_visit_with_doctor=True, has_medications=True,
        has_allergies=True, has_prep_questions=True,
        open_referral_count=1, open_lab_order_count=1,
    )
    first = build_checklist(**kwargs)
    assert first == build_checklist(**kwargs)
    assert len({item.id for item in first}) == len(first)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


async def _profile_with_appointment(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data,
    specialty: str | None = None, purpose: str | None = None,
    with_doctor: bool = True,
) -> tuple[str, str, str | None]:
    resp = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = resp.json()["id"]

    doctor_id = None
    if with_doctor:
        doctor = Doctor(profile_id=profile_id, name="Dr. Ada Reyes", specialty=specialty)
        db_session.add(doctor)
        await db_session.commit()
        await db_session.refresh(doctor)
        doctor_id = doctor.id

    appointment = Appointment(
        profile_id=profile_id,
        doctor_id=doctor_id,
        scheduled_date=datetime.utcnow() + timedelta(days=7),
        purpose=purpose,
        status="scheduled",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return profile_id, appointment.id, doctor_id


@pytest.mark.asyncio
async def test_checklist_endpoint_reads_specialty_and_purpose(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id, appointment_id, _ = await _profile_with_appointment(
        client, db_session, sample_profile_data,
        specialty="Cardiology", purpose="Fasting lipid panel",
    )

    resp = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["appointment_id"] == appointment_id

    ids = [item["id"] for item in body["items"]]
    assert "home_bp_readings" in ids
    assert "fasting_instructions" in ids
    # sample_profile_data carries allergies, so the baseline item is there too.
    assert "allergy_list" in ids
    assert all(item["why"] for item in body["items"])


@pytest.mark.asyncio
async def test_a_completed_earlier_visit_stops_it_being_a_first_visit(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id, appointment_id, doctor_id = await _profile_with_appointment(
        client, db_session, sample_profile_data
    )

    first = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    assert "photo_id_and_insurance" in [i["id"] for i in first.json()["items"]]

    # A *scheduled* earlier visit is not enough — you can book three and attend
    # none of them, and the first one you walk into is still a first visit.
    db_session.add(Appointment(
        profile_id=profile_id, doctor_id=doctor_id,
        scheduled_date=datetime.utcnow() - timedelta(days=30), status="scheduled",
    ))
    await db_session.commit()
    still_first = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    assert "photo_id_and_insurance" in [i["id"] for i in still_first.json()["items"]]

    db_session.add(Appointment(
        profile_id=profile_id, doctor_id=doctor_id,
        scheduled_date=datetime.utcnow() - timedelta(days=60), status="completed",
    ))
    await db_session.commit()
    returning = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    assert "photo_id_and_insurance" not in [i["id"] for i in returning.json()["items"]]


@pytest.mark.asyncio
async def test_only_unresolved_referrals_and_lab_orders_are_counted(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id, appointment_id, _ = await _profile_with_appointment(
        client, db_session, sample_profile_data
    )

    from src.data.models import Document
    doc = Document(
        profile_id=profile_id, original_filename="avs.pdf", file_path="/tmp/avs.pdf",
        file_size_bytes=10, parse_status="completed",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    db_session.add_all([
        Referral(profile_id=profile_id, document_id=doc.id,
                 specialty="Cardiology", status="pending"),
        Referral(profile_id=profile_id, document_id=doc.id,
                 specialty="Neurology", status="completed"),
        LabOrder(profile_id=profile_id, document_id=doc.id,
                 test_name="CBC", status="completed"),
    ])
    await db_session.commit()

    resp = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    items = {item["id"]: item for item in resp.json()["items"]}
    assert "1 referral" in items["referral_paperwork"]["why"]
    assert "lab_order_slip" not in items


@pytest.mark.asyncio
async def test_prepared_questions_and_active_medications_reach_the_checklist(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id, appointment_id, _ = await _profile_with_appointment(
        client, db_session, sample_profile_data
    )

    # A stopped medication shouldn't put "bring your medication list" on there
    # on its own.
    db_session.add(Medication(
        profile_id=profile_id, name="Metformin",
        end_date=(datetime.utcnow() - timedelta(days=1)).date(),
    ))
    await db_session.commit()

    resp = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    assert "medication_list" not in [i["id"] for i in resp.json()["items"]]

    db_session.add(Medication(profile_id=profile_id, name="Lisinopril"))
    db_session.add(VisitPrep(
        appointment_id=appointment_id,
        generated_questions={"questions": ["How is my blood pressure trending?"]},
    ))
    await db_session.commit()

    resp = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    ids = [i["id"] for i in resp.json()["items"]]
    assert "medication_list" in ids
    assert "prep_questions" in ids


@pytest.mark.asyncio
async def test_an_appointment_with_no_doctor_still_returns_a_checklist(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id, appointment_id, _ = await _profile_with_appointment(
        client, db_session, sample_profile_data,
        purpose="Annual physical", with_doctor=False,
    )

    resp = await client.get(
        f"/api/profiles/{profile_id}/appointments/{appointment_id}/checklist"
    )
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert "vaccination_records" in ids
    # No doctor means no prior completed visit with them, so it reads as a first visit.
    assert "photo_id_and_insurance" in ids


@pytest.mark.asyncio
async def test_checklist_404s_for_unknown_appointments_and_profiles(
    client: AsyncClient, db_session: AsyncSession, sample_profile_data
):
    profile_id, appointment_id, _ = await _profile_with_appointment(
        client, db_session, sample_profile_data
    )

    assert (await client.get(
        f"/api/profiles/{profile_id}/appointments/does-not-exist/checklist"
    )).status_code == 404
    assert (await client.get(
        f"/api/profiles/does-not-exist/appointments/{appointment_id}/checklist"
    )).status_code == 404
