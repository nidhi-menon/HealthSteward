"""API routes for doctor CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import Doctor, HealthProfile
from src.models.schemas import (
    DoctorCreate,
    DoctorResponse,
    DoctorUpdate,
)

router = APIRouter(prefix="/api/profiles/{profile_id}/doctors", tags=["Doctors"])


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


@router.post("/", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    profile_id: str,
    doctor: DoctorCreate,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """Create a new doctor for a health profile."""
    await verify_profile_exists(profile_id, db)

    db_doctor = Doctor(profile_id=profile_id, **doctor.model_dump())
    db.add(db_doctor)
    await db.flush()
    await db.refresh(db_doctor)
    return db_doctor


@router.get("/", response_model=list[DoctorResponse])
async def list_doctors(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Doctor]:
    """List all doctors for a health profile."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Doctor).where(Doctor.profile_id == profile_id)
    )
    return list(result.scalars().all())


@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(
    profile_id: str,
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """Get a doctor by ID."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Doctor).where(
            Doctor.id == doctor_id,
            Doctor.profile_id == profile_id,
        )
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )
    return doctor


@router.patch("/{doctor_id}", response_model=DoctorResponse)
async def update_doctor(
    profile_id: str,
    doctor_id: str,
    doctor_update: DoctorUpdate,
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    """Update a doctor."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Doctor).where(
            Doctor.id == doctor_id,
            Doctor.profile_id == profile_id,
        )
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    update_data = doctor_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doctor, field, value)

    await db.flush()
    await db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doctor(
    profile_id: str,
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a doctor."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Doctor).where(
            Doctor.id == doctor_id,
            Doctor.profile_id == profile_id,
        )
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with id {doctor_id} not found",
        )

    await db.delete(doctor)
