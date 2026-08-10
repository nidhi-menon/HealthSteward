"""API routes for visit preparation operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.database import get_db
from src.data.models import Appointment, HealthProfile, VisitPrep, VisitPrepVersion
from src.models.schemas import (
    VisitPrepRequest,
    VisitPrepResponse,
    VisitPrepUpdate,
    VisitPrepVersionResponse,
)

router = APIRouter(prefix="/api/visits", tags=["Visit Preparation"])


async def _snapshot_prep_version(db: AsyncSession, prep: VisitPrep) -> None:
    """Archive a VisitPrep's current content before something overwrites it.

    Issue #54: regeneration reassigns generated_questions/context_summary in
    place, which permanently destroyed the previous run's output — including
    any hand-edits made to it (issue #14). Called immediately before the
    reassignment, so the row captures exactly what is about to be lost.

    Does nothing when there is no content to preserve. A prep row with
    neither questions nor a summary has nothing worth archiving, and writing
    an empty version for it would put a "Previous versions (1)" affordance in
    front of the user that opens onto nothing.
    """
    if not prep.generated_questions and not prep.context_summary:
        return

    # max + 1 rather than count + 1: equivalent today, but count would start
    # renumbering from a gap if versions ever become individually deletable,
    # and a version number that changes meaning after the fact is worse than
    # one that skips.
    highest = await db.scalar(
        select(func.max(VisitPrepVersion.version_number)).where(
            VisitPrepVersion.visit_prep_id == prep.id
        )
    )

    db.add(
        VisitPrepVersion(
            visit_prep_id=prep.id,
            version_number=(highest or 0) + 1,
            generated_questions=prep.generated_questions,
            context_summary=prep.context_summary,
            used_fallback=prep.used_fallback,
            content_updated_at=prep.updated_at,
        )
    )


@router.post("/{appointment_id}/prepare", response_model=VisitPrepResponse)
async def prepare_visit(
    appointment_id: str,
    request: VisitPrepRequest = None,
    db: AsyncSession = Depends(get_db),
) -> VisitPrep:
    """Generate AI-powered visit preparation for an appointment."""
    # Import here to avoid circular imports
    from src.agents.visit_prep import VisitPrepAgent

    # Load appointment with all related data
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.doctor),
            selectinload(Appointment.profile).selectinload(HealthProfile.conditions),
            selectinload(Appointment.profile).selectinload(HealthProfile.medications),
            selectinload(Appointment.profile).selectinload(HealthProfile.doctors),
        )
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    # Check if visit prep already exists
    existing_result = await db.execute(
        select(VisitPrep).where(VisitPrep.appointment_id == appointment_id)
    )
    existing_prep = existing_result.scalar_one_or_none()

    # Generate new visit prep using Claude agent
    agent = VisitPrepAgent(db)
    additional_concerns = request.additional_concerns if request else None
    prep_data = await agent.prepare_visit(appointment, additional_concerns)

    if existing_prep:
        # Preserve what's about to be overwritten before overwriting it
        # (issue #54). Ordered after prepare_visit deliberately: a generation
        # that raises leaves the existing prep untouched, so there is nothing
        # displaced and nothing to archive.
        await _snapshot_prep_version(db, existing_prep)

        # Update existing prep
        existing_prep.generated_questions = prep_data["questions"]
        existing_prep.context_summary = prep_data["context_summary"]
        existing_prep.used_fallback = prep_data.get("used_fallback", False)
        await db.flush()
        await db.refresh(existing_prep)
        return existing_prep
    else:
        # Create new prep
        visit_prep = VisitPrep(
            appointment_id=appointment_id,
            generated_questions=prep_data["questions"],
            context_summary=prep_data["context_summary"],
            used_fallback=prep_data.get("used_fallback", False),
        )
        db.add(visit_prep)
        await db.flush()
        await db.refresh(visit_prep)
        return visit_prep


@router.get("/{appointment_id}/prep", response_model=VisitPrepResponse)
async def get_visit_prep(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
) -> VisitPrep:
    """Get the visit preparation for an appointment."""
    # Verify appointment exists
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    if not appt_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    # Get visit prep
    result = await db.execute(
        select(VisitPrep).where(VisitPrep.appointment_id == appointment_id)
    )
    visit_prep = result.scalar_one_or_none()

    if not visit_prep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit preparation for appointment {appointment_id} not found. "
            f"Use POST /api/visits/{appointment_id}/prepare to generate one.",
        )

    return visit_prep


@router.get("/{appointment_id}/prep/versions", response_model=list[VisitPrepVersionResponse])
async def list_visit_prep_versions(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[VisitPrepVersion]:
    """Prior generations of this appointment's visit prep, newest first (issue #54).

    Read-only by design. A "restore" action would re-raise the same overwrite
    question one level up — does restoring clobber the current prep, or
    snapshot it first? — and the data-loss harm is already gone once the old
    content is visible and copyable. Cheap to add later; hard to un-ship if
    the semantics turn out wrong.

    Returns `[]` rather than 404 when the appointment has a prep that has
    never been regenerated: no history is a normal state for a prep, not a
    missing resource. A missing appointment is still a 404, matching the
    other routes here.
    """
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    if not appt_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    result = await db.execute(
        select(VisitPrepVersion)
        .join(VisitPrep, VisitPrep.id == VisitPrepVersion.visit_prep_id)
        .where(VisitPrep.appointment_id == appointment_id)
        .order_by(VisitPrepVersion.version_number.desc())
    )
    return list(result.scalars().all())


@router.patch("/{appointment_id}/prep", response_model=VisitPrepResponse)
async def update_visit_prep(
    appointment_id: str,
    updates: VisitPrepUpdate,
    db: AsyncSession = Depends(get_db),
) -> VisitPrep:
    """Edit an existing visit prep's questions or context summary (issue #14).

    Generation is wholesale — POST /prepare re-runs the agent and replaces the
    output entirely. This lets the patient fix a question's wording, add one of
    their own, or drop one that doesn't apply, without discarding the rest.

    Deliberately edit-only: it will not create a prep for an appointment that
    doesn't have one, since there'd be nothing to edit and silently creating one
    would hide a client bug.
    """
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    if not appt_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with id {appointment_id} not found",
        )

    result = await db.execute(
        select(VisitPrep).where(VisitPrep.appointment_id == appointment_id)
    )
    visit_prep = result.scalar_one_or_none()

    if not visit_prep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visit preparation for appointment {appointment_id} not found. "
            f"Use POST /api/visits/{appointment_id}/prepare to generate one first.",
        )

    # exclude_unset, not exclude_none: an omitted field means "leave it alone",
    # while an explicit null means "clear it" — both are legitimate here, and
    # collapsing them would make it impossible to clear a context summary.
    payload = updates.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in payload.items():
        setattr(visit_prep, field, value)

    # Clear used_fallback on any edit. It exists to drive the "these are
    # generic default questions, not personalized — regenerate" warning
    # (issue #47); once the patient has hand-edited the content, that warning
    # is no longer true and reads as wrong over text they just wrote.
    visit_prep.used_fallback = False

    await db.flush()
    await db.refresh(visit_prep)
    return visit_prep
