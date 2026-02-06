"""API routes for medication CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import HealthProfile, Medication
from src.models.schemas import (
    MedicationCreate,
    MedicationResponse,
    MedicationUpdate,
)

router = APIRouter(prefix="/api/profiles/{profile_id}/medications", tags=["Medications"])


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


@router.post("/", response_model=MedicationResponse, status_code=status.HTTP_201_CREATED)
async def create_medication(
    profile_id: str,
    medication: MedicationCreate,
    db: AsyncSession = Depends(get_db),
) -> Medication:
    """Create a new medication for a health profile."""
    await verify_profile_exists(profile_id, db)

    db_medication = Medication(profile_id=profile_id, **medication.model_dump())
    db.add(db_medication)
    await db.flush()
    await db.refresh(db_medication)
    return db_medication


@router.get("/", response_model=list[MedicationResponse])
async def list_medications(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Medication]:
    """List all medications for a health profile."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Medication).where(Medication.profile_id == profile_id)
    )
    return list(result.scalars().all())


@router.get("/{medication_id}", response_model=MedicationResponse)
async def get_medication(
    profile_id: str,
    medication_id: str,
    db: AsyncSession = Depends(get_db),
) -> Medication:
    """Get a medication by ID."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Medication).where(
            Medication.id == medication_id,
            Medication.profile_id == profile_id,
        )
    )
    medication = result.scalar_one_or_none()
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found",
        )
    return medication


@router.patch("/{medication_id}", response_model=MedicationResponse)
async def update_medication(
    profile_id: str,
    medication_id: str,
    medication_update: MedicationUpdate,
    db: AsyncSession = Depends(get_db),
) -> Medication:
    """Update a medication."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Medication).where(
            Medication.id == medication_id,
            Medication.profile_id == profile_id,
        )
    )
    medication = result.scalar_one_or_none()
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found",
        )

    update_data = medication_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(medication, field, value)

    await db.flush()
    await db.refresh(medication)
    return medication


@router.delete("/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    profile_id: str,
    medication_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a medication."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Medication).where(
            Medication.id == medication_id,
            Medication.profile_id == profile_id,
        )
    )
    medication = result.scalar_one_or_none()
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication with id {medication_id} not found",
        )

    await db.delete(medication)
