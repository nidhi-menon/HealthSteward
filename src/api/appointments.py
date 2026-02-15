"""API routes for appointment CRUD operations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import Appointment, Doctor, HealthProfile
from src.models.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)

router = APIRouter(prefix="/api/profiles/{profile_id}/appointments", tags=["Appointments"])


async def verify_profile_exists(profile_id: str, db: AsyncSession) -> None:
    """Verify that the profile exists."""
    result = await db.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile with id {profile_id} not found",
        )


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
