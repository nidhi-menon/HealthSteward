"""API routes for visit preparation operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.database import get_db
from src.data.models import Appointment, HealthProfile, VisitPrep
from src.models.schemas import VisitPrepRequest, VisitPrepResponse

router = APIRouter(prefix="/api/visits", tags=["Visit Preparation"])


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
        # Update existing prep
        existing_prep.generated_questions = prep_data["questions"]
        existing_prep.context_summary = prep_data["context_summary"]
        await db.flush()
        await db.refresh(existing_prep)
        return existing_prep
    else:
        # Create new prep
        visit_prep = VisitPrep(
            appointment_id=appointment_id,
            generated_questions=prep_data["questions"],
            context_summary=prep_data["context_summary"],
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
