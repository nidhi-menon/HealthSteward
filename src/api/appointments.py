"""API routes for appointment CRUD operations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.action_items import COMPLETED_STATUSES
from src.api.health_profile import get_live_profile_or_404
from src.data.database import get_db
from src.data.models import (
    Appointment,
    Doctor,
    LabOrder,
    Medication,
    Referral,
    VisitPrep,
)
from src.models.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    ChecklistItemResponse,
    VisitChecklistResponse,
)
from src.services.visit_checklist import build_checklist

router = APIRouter(prefix="/api/profiles/{profile_id}/appointments", tags=["Appointments"])


async def verify_profile_exists(profile_id: str, db: AsyncSession) -> None:
    """Verify that the profile exists and hasn't been soft-deleted.

    Thin wrapper around the shared `get_live_profile_or_404` (issue #119) so
    every child router keeps this name/signature at call sites while sharing
    one definition of "profile exists" (issue #50, DEC-027).
    """
    await get_live_profile_or_404(profile_id, db)


async def verify_doctor_exists(doctor_id: str, profile_id: str, db: AsyncSession) -> None:
    """Verify that the doctor exists and belongs to the profile."""
    result = await db.execute(
        select(Doctor).where(
            Doctor.id == doctor_id,
            Doctor.profile_id == profile_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found for this profile",
        )


async def _get_appointment_or_404(
    appointment_id: str, profile_id: str, db: AsyncSession
) -> Appointment:
    """Fetch one of this profile's appointments, or 404."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.profile_id == profile_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )
    return appointment


@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    profile_id: str,
    appointment: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    """Create a new appointment for a health profile."""
    await verify_profile_exists(profile_id, db)
    if not appointment.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="doctor_id is required when creating an appointment",
        )
    await verify_doctor_exists(appointment.doctor_id, profile_id, db)

    db_appointment = Appointment(profile_id=profile_id, **appointment.model_dump())
    db.add(db_appointment)
    await db.flush()
    await db.refresh(db_appointment)
    return db_appointment


@router.get("/", response_model=list[AppointmentResponse])
async def list_appointments(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Appointment]:
    """List all appointments for a health profile."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Appointment).where(Appointment.profile_id == profile_id)
    )
    return list(result.scalars().all())


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    profile_id: str,
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    """Get an appointment by ID."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.profile_id == profile_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )
    return appointment


@router.get("/{appointment_id}/checklist", response_model=VisitChecklistResponse)
async def get_visit_checklist(
    profile_id: str,
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
) -> VisitChecklistResponse:
    """What to bring to this visit (issue #110).

    Deterministic rules over data the profile already holds — no LLM call, no
    new table, nothing stored. Computed per request so it always reflects the
    profile as it is now (a referral closed this morning drops off the list).
    """
    profile = await get_live_profile_or_404(profile_id, db)

    appointment = await _get_appointment_or_404(appointment_id, profile_id, db)

    doctor = (
        await db.get(Doctor, appointment.doctor_id) if appointment.doctor_id else None
    )

    # "First visit with this doctor" means no earlier appointment with them has
    # been completed. Scheduled-but-not-yet-attended ones don't count: you can
    # book three visits before attending any of them, and the first one you
    # actually walk into is still a first visit for paperwork purposes.
    is_first_visit = True
    if appointment.doctor_id:
        prior = await db.execute(
            select(Appointment.id).where(
                Appointment.profile_id == profile_id,
                Appointment.doctor_id == appointment.doctor_id,
                Appointment.id != appointment.id,
                Appointment.status == "completed",
            ).limit(1)
        )
        is_first_visit = prior.scalar_one_or_none() is None

    medications = await db.execute(
        select(Medication.id).where(
            Medication.profile_id == profile_id,
            Medication.end_date.is_(None),
        ).limit(1)
    )

    referrals = await db.execute(
        select(Referral).where(Referral.profile_id == profile_id)
    )
    open_referrals = [
        r for r in referrals.scalars().all() if r.status not in COMPLETED_STATUSES
    ]

    lab_orders = await db.execute(
        select(LabOrder).where(LabOrder.profile_id == profile_id)
    )
    open_lab_orders = [
        lab for lab in lab_orders.scalars().all()
        if lab.status not in COMPLETED_STATUSES
    ]

    prep = await db.execute(
        select(VisitPrep).where(VisitPrep.appointment_id == appointment_id)
    )
    prep_record = prep.scalar_one_or_none()
    has_prep_questions = bool(prep_record and prep_record.generated_questions)

    items = build_checklist(
        specialty=doctor.specialty if doctor else None,
        purpose=appointment.purpose,
        is_first_visit_with_doctor=is_first_visit,
        has_medications=medications.scalar_one_or_none() is not None,
        has_allergies=bool(profile.allergies and profile.allergies.strip()),
        has_prep_questions=has_prep_questions,
        open_referral_count=len(open_referrals),
        open_lab_order_count=len(open_lab_orders),
    )

    return VisitChecklistResponse(
        appointment_id=appointment_id,
        items=[
            ChecklistItemResponse(
                id=item.id, label=item.label, why=item.why,
                category=item.category, sources=list(item.sources),
            )
            for item in items
        ],
    )


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    profile_id: str,
    appointment_id: str,
    appointment_update: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    """Update an appointment."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.profile_id == profile_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    update_data = appointment_update.model_dump(exclude_unset=True)

    # If updating doctor_id, verify the new doctor exists
    if "doctor_id" in update_data and update_data["doctor_id"]:
        await verify_doctor_exists(update_data["doctor_id"], profile_id, db)

    # Auto-update visit_notes_updated_at when visit_notes changes
    if "visit_notes" in update_data and update_data["visit_notes"] != appointment.visit_notes:
        update_data["visit_notes_updated_at"] = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(appointment, field, value)

    await db.flush()
    await db.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    profile_id: str,
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an appointment."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.profile_id == profile_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    await db.delete(appointment)
