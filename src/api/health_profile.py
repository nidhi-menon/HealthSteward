"""API routes for health profile CRUD operations.

Profile deletion is soft (issue #50, DEC-027): `DELETE` sets `deleted_at`
rather than removing the row, the profile stays recoverable for
`SOFT_DELETE_RETENTION_DAYS`, and the real cascading delete happens lazily
once that window has expired. Every read path here filters `deleted_at IS
NULL`, so a soft-deleted profile is invisible to the rest of the app.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import HealthProfile
from src.models.schemas import (
    DeletedHealthProfileResponse,
    HealthProfileCreate,
    HealthProfileResponse,
    HealthProfileUpdate,
)

router = APIRouter(prefix="/api/profiles", tags=["Health Profiles"])

# How long a soft-deleted profile stays recoverable before it is permanently
# deleted. 30 days per issue #50.
SOFT_DELETE_RETENTION_DAYS = 30


async def get_live_profile_or_404(profile_id: str, db: AsyncSession) -> HealthProfile:
    """Fetch a profile that hasn't been soft-deleted, or raise 404.

    Shared by the child-resource routers (conditions, medications, doctors,
    appointments) so "profile exists" means the same thing everywhere — a
    soft-deleted profile has to be a 404 to those routes too, or its data
    would still be reachable and writable through a URL the user kept open.
    """
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.id == profile_id,
            HealthProfile.deleted_at.is_(None),
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile with id {profile_id} not found",
        )
    return profile


async def purge_expired_profiles(db: AsyncSession) -> int:
    """Permanently delete soft-deleted profiles past their recovery window.

    Lazy cleanup rather than a scheduled job — the repo owner's call on issue
    #50, since this app has no job-scheduling infrastructure and building it
    speculatively for #25 (not scoped or started) would be premature. The
    tradeoff: expiry is only enforced when someone looks at a profile list, so
    a profile can outlive its 30 days on disk if the app goes unused. It is
    still invisible throughout, so this affects when data is destroyed, not
    when it stops being reachable.

    This is where issue #49's opt-in "also delete AVS files on disk" would
    hook in — by this point the user has had their full recovery window.

    Returns the number of profiles hard-deleted.
    """
    cutoff = datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS)
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.deleted_at.is_not(None),
            HealthProfile.deleted_at < cutoff,
        )
    )
    expired = list(result.scalars().all())

    for profile in expired:
        # Cascades through every related table, as a hard delete always has.
        await db.delete(profile)

    if expired:
        await db.flush()
        logger.info(
            f"Purged {len(expired)} profile(s) past the "
            f"{SOFT_DELETE_RETENTION_DAYS}-day recovery window"
        )

    return len(expired)


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
    """List all health profiles. Soft-deleted profiles are excluded."""
    await purge_expired_profiles(db)

    result = await db.execute(
        select(HealthProfile).where(HealthProfile.deleted_at.is_(None))
    )
    return list(result.scalars().all())


# Declared before /{profile_id} — FastAPI matches routes in declaration order,
# so the reverse would make "deleted" look like a profile id.
@router.get("/deleted", response_model=list[DeletedHealthProfileResponse])
async def list_deleted_profiles(
    db: AsyncSession = Depends(get_db),
) -> list[DeletedHealthProfileResponse]:
    """List soft-deleted profiles still inside their recovery window.

    The "Recently deleted" view — same shape as the snoozed-items view from
    issue #44: hidden but recoverable, not gone.
    """
    await purge_expired_profiles(db)

    result = await db.execute(
        select(HealthProfile)
        .where(HealthProfile.deleted_at.is_not(None))
        .order_by(HealthProfile.deleted_at.desc())
    )
    profiles = list(result.scalars().all())

    now = datetime.utcnow()
    responses: list[DeletedHealthProfileResponse] = []
    for profile in profiles:
        expires_at = profile.deleted_at + timedelta(days=SOFT_DELETE_RETENTION_DAYS)
        # Floored at 0 rather than allowed to go negative: a profile that is
        # past its window but not yet purged is "0 days left", not "-2 days".
        days_remaining = max(0, (expires_at - now).days)
        responses.append(
            DeletedHealthProfileResponse(
                **{
                    field: getattr(profile, field)
                    for field in (
                        "id", "name", "date_of_birth", "blood_type", "allergies",
                        "emergency_contact_name", "emergency_contact_phone",
                        "created_at", "updated_at", "deleted_at",
                    )
                },
                expires_at=expires_at,
                days_remaining=days_remaining,
            )
        )
    return responses


@router.get("/{profile_id}", response_model=HealthProfileResponse)
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    """Get a health profile by ID. Soft-deleted profiles are treated as absent."""
    return await get_live_profile_or_404(profile_id, db)


@router.patch("/{profile_id}", response_model=HealthProfileResponse)
async def update_profile(
    profile_id: str,
    profile_update: HealthProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    """Update a health profile."""
    profile = await get_live_profile_or_404(profile_id, db)

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
    """Soft-delete a health profile.

    Sets `deleted_at` instead of removing the row. Nothing under the profile
    is altered — conditions, medications, documents and the rest are left
    exactly as they are, just unreachable — so restoring is a single field
    write rather than an undo log.
    """
    profile = await get_live_profile_or_404(profile_id, db)

    profile.deleted_at = datetime.utcnow()
    await db.flush()


@router.post("/{profile_id}/restore", response_model=HealthProfileResponse)
async def restore_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> HealthProfile:
    """Restore a soft-deleted profile, clearing `deleted_at`.

    404s for a profile that isn't soft-deleted (including a live one) — there
    is nothing to restore, and silently succeeding would hide a client bug.

    Deliberately does *not* purge first, so a profile that is past its window
    but hasn't been cleaned up yet can still be restored. Erring toward
    recovery is the entire point of the feature, and purging here would mean a
    restore click could destroy the profile it was trying to bring back.
    """
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.id == profile_id,
            HealthProfile.deleted_at.is_not(None),
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No deleted profile with id {profile_id} found to restore",
        )

    profile.deleted_at = None
    await db.flush()
    await db.refresh(profile)
    return profile
