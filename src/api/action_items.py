"""API endpoints for pending action items: follow-ups, lab orders, referrals, prep nudges."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from pydantic import BaseModel

from src.data.models import Appointment, Document, FollowUp, LabOrder, Referral, VisitPrep, Vitals
from src.models.schemas import AppointmentResponse, FollowUpResponse, LabOrderResponse, ReferralResponse

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


@router.get("/upcoming-without-prep", response_model=list[AppointmentResponse])
async def upcoming_appointments_without_prep(
    profile_id: str,
    days_ahead: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Return upcoming scheduled appointments that have no visit prep generated."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days_ahead)

    appt_result = await db.execute(
        select(Appointment).where(
            Appointment.profile_id == profile_id,
            Appointment.status == "scheduled",
            Appointment.scheduled_date >= now,
            Appointment.scheduled_date <= cutoff,
        ).order_by(Appointment.scheduled_date)
    )
    upcoming = appt_result.scalars().all()

    without_prep = []
    for appt in upcoming:
        prep_result = await db.execute(
            select(VisitPrep).where(VisitPrep.appointment_id == appt.id)
        )
        if prep_result.scalar_one_or_none() is None:
            without_prep.append(appt)

    return without_prep


# ── Vitals alerts ─────────────────────────────────────────────────────────────

class VitalsAlert(BaseModel):
    metric: str
    message: str
    direction: str   # "up" | "down"
    oldest_value: str
    newest_value: str
    visit_count: int


def _parse_numeric(value: str | None) -> float | None:
    """Extract first numeric token from a string like '182 lbs' or '120/80'."""
    if not value:
        return None
    try:
        return float(value.split("/")[0].split()[0].replace(",", ""))
    except (ValueError, IndexError):
        return None


@router.get("/vitals-alerts", response_model=list[VitalsAlert])
async def vitals_alerts(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return alerts for meaningful trends in vitals across visits."""
    result = await db.execute(
        select(Vitals)
        .where(Vitals.profile_id == profile_id)
        .order_by(Vitals.measured_date)
    )
    all_vitals = result.scalars().all()
    if len(all_vitals) < 2:
        return []

    alerts: list[VitalsAlert] = []

    def check_metric(label: str, values: list[tuple[float, str]]) -> None:
        if len(values) < 2:
            return
        oldest_val, oldest_raw = values[0]
        newest_val, newest_raw = values[-1]
        change = newest_val - oldest_val
        pct = abs(change) / oldest_val * 100 if oldest_val else 0

        if label == "Weight" and abs(change) >= 5:
            direction = "up" if change > 0 else "down"
            alerts.append(VitalsAlert(
                metric=label,
                message=f"Weight has {'increased' if change > 0 else 'decreased'} by {abs(change):.1f} lbs across {len(values)} visits",
                direction=direction,
                oldest_value=oldest_raw,
                newest_value=newest_raw,
                visit_count=len(values),
            ))
        elif label == "BMI" and abs(change) >= 1.5:
            direction = "up" if change > 0 else "down"
            alerts.append(VitalsAlert(
                metric=label,
                message=f"BMI has {'increased' if change > 0 else 'decreased'} by {abs(change):.1f} across {len(values)} visits",
                direction=direction,
                oldest_value=oldest_raw,
                newest_value=newest_raw,
                visit_count=len(values),
            ))
        elif label == "Systolic BP" and abs(change) >= 10:
            direction = "up" if change > 0 else "down"
            alerts.append(VitalsAlert(
                metric=label,
                message=f"Blood pressure has {'risen' if change > 0 else 'dropped'} by {abs(change):.0f} mmHg across {len(values)} visits",
                direction=direction,
                oldest_value=oldest_raw,
                newest_value=newest_raw,
                visit_count=len(values),
            ))
        elif label == "Heart Rate" and abs(change) >= 10:
            direction = "up" if change > 0 else "down"
            alerts.append(VitalsAlert(
                metric=label,
                message=f"Resting heart rate has {'increased' if change > 0 else 'decreased'} by {abs(change):.0f} bpm across {len(values)} visits",
                direction=direction,
                oldest_value=oldest_raw,
                newest_value=newest_raw,
                visit_count=len(values),
            ))

    weight_vals = [(n, v.weight) for v in all_vitals if (n := _parse_numeric(v.weight)) is not None]
    bmi_vals = [(v.bmi, str(round(v.bmi, 1))) for v in all_vitals if v.bmi is not None]
    bp_vals = [(n, v.blood_pressure) for v in all_vitals if (n := _parse_numeric(v.blood_pressure)) is not None]
    hr_vals = [(n, v.heart_rate) for v in all_vitals if (n := _parse_numeric(v.heart_rate)) is not None]

    check_metric("Weight", weight_vals)
    check_metric("BMI", bmi_vals)
    check_metric("Systolic BP", bp_vals)
    check_metric("Heart Rate", hr_vals)

    return alerts


# ── Completed appointments without AVS ────────────────────────────────────────

@router.get("/completed-without-avs", response_model=list[AppointmentResponse])
async def completed_appointments_without_avs(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return completed appointments that have no parsed document near their visit date."""
    appt_result = await db.execute(
        select(Appointment).where(
            Appointment.profile_id == profile_id,
            Appointment.status == "completed",
        ).order_by(Appointment.scheduled_date.desc())
    )
    completed = appt_result.scalars().all()

    doc_result = await db.execute(
        select(Document).where(
            Document.profile_id == profile_id,
            Document.parse_status == "completed",
        )
    )
    parsed_docs = doc_result.scalars().all()

    without_avs = []
    for appt in completed:
        appt_date = appt.scheduled_date.date() if appt.scheduled_date else None
        if not appt_date:
            continue
        # Look for any parsed document within 14 days of the appointment
        has_doc = any(
            _doc_near_appointment(doc, appt_date)
            for doc in parsed_docs
        )
        if not has_doc:
            without_avs.append(appt)

    return without_avs


def _parse_date_flexible(date_str: str | None):
    """Try common date formats, return date or None."""
    if not date_str:
        return None
    from datetime import date as date_type
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _doc_near_appointment(doc: Document, appt_date) -> bool:
    """True if the document's visit_date is within 14 days of the appointment date."""
    doc_date = _parse_date_flexible(doc.visit_date)
    if not doc_date:
        return False
    return abs((doc_date - appt_date).days) <= 14
