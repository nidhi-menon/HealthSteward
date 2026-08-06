"""API routes for condition CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.health_profile import get_live_profile_or_404
from src.data.database import get_db
from src.data.models import Condition
from src.models.schemas import (
    ConditionCreate,
    ConditionResponse,
    ConditionUpdate,
)

router = APIRouter(prefix="/api/profiles/{profile_id}/conditions", tags=["Conditions"])


async def verify_profile_exists(profile_id: str, db: AsyncSession) -> None:
    """Verify that the profile exists and hasn't been soft-deleted.

    Thin wrapper around the shared `get_live_profile_or_404` (issue #119) so
    every child router keeps this name/signature at call sites while sharing
    one definition of "profile exists" (issue #50, DEC-027).
    """
    await get_live_profile_or_404(profile_id, db)


@router.post("/", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    profile_id: str,
    condition: ConditionCreate,
    db: AsyncSession = Depends(get_db),
) -> Condition:
    """Create a new condition for a health profile."""
    await verify_profile_exists(profile_id, db)

    db_condition = Condition(profile_id=profile_id, **condition.model_dump())
    db.add(db_condition)
    await db.flush()
    await db.refresh(db_condition)
    return db_condition


@router.get("/", response_model=list[ConditionResponse])
async def list_conditions(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Condition]:
    """List all conditions for a health profile."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Condition).where(Condition.profile_id == profile_id)
    )
    return list(result.scalars().all())


@router.get("/{condition_id}", response_model=ConditionResponse)
async def get_condition(
    profile_id: str,
    condition_id: str,
    db: AsyncSession = Depends(get_db),
) -> Condition:
    """Get a condition by ID."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Condition).where(
            Condition.id == condition_id,
            Condition.profile_id == profile_id,
        )
    )
    condition = result.scalar_one_or_none()
    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Condition with id {condition_id} not found",
        )
    return condition


@router.patch("/{condition_id}", response_model=ConditionResponse)
async def update_condition(
    profile_id: str,
    condition_id: str,
    condition_update: ConditionUpdate,
    db: AsyncSession = Depends(get_db),
) -> Condition:
    """Update a condition."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Condition).where(
            Condition.id == condition_id,
            Condition.profile_id == profile_id,
        )
    )
    condition = result.scalar_one_or_none()
    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Condition with id {condition_id} not found",
        )

    update_data = condition_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(condition, field, value)

    await db.flush()
    await db.refresh(condition)
    return condition


@router.delete("/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    profile_id: str,
    condition_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a condition."""
    await verify_profile_exists(profile_id, db)

    result = await db.execute(
        select(Condition).where(
            Condition.id == condition_id,
            Condition.profile_id == profile_id,
        )
    )
    condition = result.scalar_one_or_none()
    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Condition with id {condition_id} not found",
        )

    await db.delete(condition)
