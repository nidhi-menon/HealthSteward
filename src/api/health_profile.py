"""API routes for health profile CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import HealthProfile
from src.models.schemas import (
    HealthProfileCreate,
    HealthProfileResponse,
    HealthProfileUpdate,
)

router = APIRouter(prefix="/api/profiles", tags=["Health Profiles"])


@router.post("/", response_model=HealthProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile: HealthProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    """Create a new health profile."""
    db_profile = HealthProfile(**profile.model_dump())
    db.add(db_profile)
    await db.flush()
    await db.refresh(db_profile)
    return db_profile


@router.get("/", response_model=list[HealthProfileResponse])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
) -> list[HealthProfile]:
    """List all health profiles."""
    result = await db.execute(select(HealthProfile))
    return list(result.scalars().all())


@router.get("/{profile_id}", response_model=HealthProfileResponse)
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    """Get a health profile by ID."""
    result = await db.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile with id {profile_id} not found",
        )
    return profile


@router.patch("/{profile_id}", response_model=HealthProfileResponse)
async def update_profile(
    profile_id: str,
    profile_update: HealthProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    """Update a health profile."""
    result = await db.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile with id {profile_id} not found",
        )

    update_data = profile_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a health profile."""
    result = await db.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile with id {profile_id} not found",
        )

    await db.delete(profile)
