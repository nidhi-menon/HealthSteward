"""Builds an EvalCase's fixture data into a real (in-memory/temp) DB and
returns the target Appointment, loaded exactly the way the API route loads
it before calling VisitPrepAgent.prepare_visit() — so the eval harness runs
the real pipeline, not a re-implementation of it.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from eval.fixtures import EvalCase
from src.data.models import (
    Appointment,
    Condition,
    Doctor,
    Document,
    HealthProfile,
    LabOrder,
    Medication,
    Vitals,
)

# Fixed DOB for every case — only affects the anonymized "age_description"
# text, not any check the harness runs, so one shared value keeps fixtures
# short.
_DEFAULT_DOB = date(1985, 6, 15)


async def build_case(db: AsyncSession, case: EvalCase) -> Appointment:
    """Persist an EvalCase's fixture data and return the loaded target Appointment."""
    profile = HealthProfile(name=case.profile_name, date_of_birth=_DEFAULT_DOB)
    db.add(profile)
    await db.flush()

    doctors_by_key: dict[str, Doctor] = {}
    for d in case.doctors:
        doctor = Doctor(
            profile_id=profile.id,
            name=d.name,
            specialty=d.specialty,
            clinic=d.clinic,
            exclude_from_prep_context=d.exclude_from_prep_context,
        )
        db.add(doctor)
        doctors_by_key[d.key] = doctor
    await db.flush()

    for c in case.conditions:
        db.add(Condition(
            profile_id=profile.id, name=c.name, icd_10=c.icd_10,
            status=c.status, severity=c.severity, notes=c.notes,
        ))

    for m in case.medications:
        prescribing_doctor_name = (
            doctors_by_key[m.prescribing_doctor_key].name if m.prescribing_doctor_key else None
        )
        db.add(Medication(
            profile_id=profile.id, name=m.name, dosage=m.dosage, frequency=m.frequency,
            prescribing_doctor=prescribing_doctor_name, purpose=m.purpose, side_effects=m.side_effects,
        ))

    for pv in case.past_visits:
        db.add(Appointment(
            profile_id=profile.id,
            doctor_id=doctors_by_key[pv.doctor_key].id,
            scheduled_date=datetime.fromisoformat(pv.scheduled_date),
            purpose=pv.purpose,
            visit_notes=pv.visit_notes,
            status=pv.status,
        ))

    def _new_document(suffix: str) -> Document:
        document = Document(
            profile_id=profile.id,
            original_filename=f"{case.id}-{suffix}.pdf",
            file_path=f"eval/{case.id}-{suffix}.pdf",
            file_size_bytes=1,
            parse_status="completed",
        )
        db.add(document)
        return document

    if case.lab_orders:
        # Document.lab_orders is one-to-many — safe to share one document.
        labs_document = _new_document("labs")
        await db.flush()
        for lab in case.lab_orders:
            db.add(LabOrder(
                profile_id=profile.id, document_id=labs_document.id,
                test_name=lab.test_name, ordered_date=lab.ordered_date,
            ))

    for i, v in enumerate(case.vitals):
        # Document.vitals is one-to-one (Optional["Vitals"], not a list) —
        # each vitals snapshot needs its own document, unlike lab orders.
        vitals_document = _new_document(f"vitals-{i}")
        await db.flush()
        db.add(Vitals(
            profile_id=profile.id, document_id=vitals_document.id,
            weight=v.weight, bmi=v.bmi, blood_pressure=v.blood_pressure,
            heart_rate=v.heart_rate, measured_date=v.measured_date,
        ))

    target_doctor = doctors_by_key[case.target_doctor_key]
    appointment = Appointment(
        profile_id=profile.id,
        doctor_id=target_doctor.id,
        scheduled_date=datetime.fromisoformat(case.appointment_scheduled_date),
        purpose=case.appointment_purpose,
        status="scheduled",
    )
    db.add(appointment)
    await db.flush()

    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.doctor),
            selectinload(Appointment.profile).selectinload(HealthProfile.conditions),
            selectinload(Appointment.profile).selectinload(HealthProfile.medications),
            selectinload(Appointment.profile).selectinload(HealthProfile.doctors),
        )
        .where(Appointment.id == appointment.id)
    )
    return result.scalar_one()
