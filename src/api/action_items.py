"""API endpoints for pending action items: follow-ups, lab orders, referrals."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import FollowUp, LabOrder, Referral
from src.models.schemas import FollowUpResponse, LabOrderResponse, ReferralResponse

router = APIRouter(prefix="/api/profiles/{profile_id}", tags=["action-items"])


@router.get("/follow-ups", response_model=list[FollowUpResponse])
async def list_follow_ups(
    profile_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(FollowUp).where(FollowUp.profile_id == profile_id)
    if status:
        query = query.where(FollowUp.status == status)
    query = query.order_by(FollowUp.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/follow-ups/{follow_up_id}", response_model=FollowUpResponse)
async def update_follow_up_status(
    profile_id: str,
    follow_up_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowUp).where(FollowUp.id == follow_up_id, FollowUp.profile_id == profile_id)
    )
    follow_up = result.scalar_one_or_none()
    if not follow_up:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if "status" in body:
        follow_up.status = body["status"]
    await db.commit()
    await db.refresh(follow_up)
    return follow_up


@router.get("/lab-orders", response_model=list[LabOrderResponse])
async def list_lab_orders(
    profile_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(LabOrder).where(LabOrder.profile_id == profile_id)
    if status:
        query = query.where(LabOrder.status == status)
    query = query.order_by(LabOrder.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/lab-orders/{lab_order_id}", response_model=LabOrderResponse)
async def update_lab_order_status(
    profile_id: str,
    lab_order_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LabOrder).where(LabOrder.id == lab_order_id, LabOrder.profile_id == profile_id)
    )
    lab_order = result.scalar_one_or_none()
    if not lab_order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Lab order not found")
    if "status" in body:
        lab_order.status = body["status"]
    await db.commit()
    await db.refresh(lab_order)
    return lab_order


@router.get("/referrals", response_model=list[ReferralResponse])
async def list_referrals(
    profile_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Referral).where(Referral.profile_id == profile_id)
    if status:
        query = query.where(Referral.status == status)
    query = query.order_by(Referral.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/referrals/{referral_id}", response_model=ReferralResponse)
async def update_referral_status(
    profile_id: str,
    referral_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Referral).where(Referral.id == referral_id, Referral.profile_id == profile_id)
    )
    referral = result.scalar_one_or_none()
    if not referral:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Referral not found")
    if "status" in body:
        referral.status = body["status"]
    await db.commit()
    await db.refresh(referral)
    return referral
