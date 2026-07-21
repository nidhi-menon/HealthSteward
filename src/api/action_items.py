"""API endpoints for pending action items: follow-ups, lab orders, referrals, prep nudges."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, nullslast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.database import get_db
from pydantic import BaseModel

from src.data.models import Appointment, Doctor, Document, FollowUp, LabOrder, NudgeState, Referral, VisitPrep, Vitals
from src.models.schemas import (
    AppointmentResponse,
    FollowUpResponse,
    LabOrderResponse,
    NudgeStateCreate,
    NudgeStateResponse,
    ReferralResponse,
)

router = APIRouter(prefix="/api/profiles/{profile_id}", tags=["action-items"])

# Statuses that mean the item is resolved (exclude from active lists)
_COMPLETED_STATUSES = {"completed", "booked", "scheduled", "done", "cancelled"}


def _is_active(item) -> bool:
    """True if item should appear in the action items list."""
    if item.status in _COMPLETED_STATUSES:
        return False
    now = datetime.now(timezone.utc)
    if item.snoozed_until:
        snoozed = item.snoozed_until
        if snoozed.tzinfo is None:
            snoozed = snoozed.replace(tzinfo=timezone.utc)
        if snoozed > now:
            return False
    return True


# ── Follow-ups ────────────────────────────────────────────────────────────────

@router.get("/follow-ups", response_model=list[FollowUpResponse])
async def list_follow_ups(
    profile_id: str,
    status: str | None = None,
    include_resolved: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(FollowUp).where(FollowUp.profile_id == profile_id)
    if include_resolved:
        query = query.where(FollowUp.status.in_(list(_COMPLETED_STATUSES))).order_by(nullslast(FollowUp.completed_at.desc())).limit(20)
    else:
        if status:
            query = query.where(FollowUp.status == status)
        query = query.order_by(FollowUp.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()
    if not status and not include_resolved:
        items = [i for i in items if _is_active(i)]
    return items


@router.patch("/follow-ups/{follow_up_id}", response_model=FollowUpResponse)
async def update_follow_up(
    profile_id: str,
    follow_up_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowUp).where(FollowUp.id == follow_up_id, FollowUp.profile_id == profile_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    if "status" in body:
        item.status = body["status"]
        if body["status"] in _COMPLETED_STATUSES and item.completed_at is None:
            item.completed_at = datetime.now(timezone.utc)
    if "snoozed_until" in body:
        item.snoozed_until = datetime.fromisoformat(body["snoozed_until"].replace("Z", "+00:00")) if body["snoozed_until"] else None

    await db.commit()
    await db.refresh(item)
    return item


# ── Lab orders ────────────────────────────────────────────────────────────────

@router.get("/lab-orders", response_model=list[LabOrderResponse])
async def list_lab_orders(
    profile_id: str,
    status: str | None = None,
    include_resolved: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(LabOrder).where(LabOrder.profile_id == profile_id)
    if include_resolved:
        query = query.where(LabOrder.status.in_(list(_COMPLETED_STATUSES))).order_by(nullslast(LabOrder.completed_at.desc())).limit(20)
    else:
        if status:
            query = query.where(LabOrder.status == status)
        query = query.order_by(LabOrder.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()
    if not status and not include_resolved:
        items = [i for i in items if _is_active(i)]
    return items


@router.patch("/lab-orders/{lab_order_id}", response_model=LabOrderResponse)
async def update_lab_order(
    profile_id: str,
    lab_order_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LabOrder).where(LabOrder.id == lab_order_id, LabOrder.profile_id == profile_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Lab order not found")

    if "status" in body:
        item.status = body["status"]
        if body["status"] in _COMPLETED_STATUSES and item.completed_at is None:
            item.completed_at = datetime.now(timezone.utc)
    if "snoozed_until" in body:
        item.snoozed_until = datetime.fromisoformat(body["snoozed_until"].replace("Z", "+00:00")) if body["snoozed_until"] else None

    await db.commit()
    await db.refresh(item)
    return item


# ── Referrals ─────────────────────────────────────────────────────────────────

@router.get("/referrals", response_model=list[ReferralResponse])
async def list_referrals(
    profile_id: str,
    status: str | None = None,
    include_resolved: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(Referral).where(Referral.profile_id == profile_id)
    if include_resolved:
        query = query.where(Referral.status.in_(list(_COMPLETED_STATUSES))).order_by(nullslast(Referral.completed_at.desc())).limit(20)
    else:
        if status:
            query = query.where(Referral.status == status)
        query = query.order_by(Referral.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()
    if not status and not include_resolved:
        items = [i for i in items if _is_active(i)]
    return items


@router.patch("/referrals/{referral_id}", response_model=ReferralResponse)
async def update_referral(
    profile_id: str,
    referral_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Referral).where(Referral.id == referral_id, Referral.profile_id == profile_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Referral not found")

    if "status" in body:
        item.status = body["status"]
        if body["status"] in _COMPLETED_STATUSES and item.completed_at is None:
            item.completed_at = datetime.now(timezone.utc)
    if "snoozed_until" in body:
        item.snoozed_until = datetime.fromisoformat(body["snoozed_until"].replace("Z", "+00:00")) if body["snoozed_until"] else None

    await db.commit()
    await db.refresh(item)
    return item


# ── Nudge states (snooze for computed nudges) ─────────────────────────────────

@router.post("/nudge-states", response_model=NudgeStateResponse, status_code=200)
async def upsert_nudge_state(
    profile_id: str,
    body: NudgeStateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Upsert a snooze record for a computed nudge (appointment-based, vitals alerts)."""
    result = await db.execute(
        select(NudgeState).where(
            NudgeState.profile_id == profile_id,
            NudgeState.nudge_type == body.nudge_type,
            NudgeState.item_id == body.item_id,
        )
    )
    state = result.scalar_one_or_none()
    if state:
        state.snoozed_until = body.snoozed_until
    else:
        state = NudgeState(
            profile_id=profile_id,
            nudge_type=body.nudge_type,
            item_id=body.item_id,
            snoozed_until=body.snoozed_until,
        )
        db.add(state)
    await db.commit()
    await db.refresh(state)
    return state


async def _snoozed_item_ids(db: AsyncSession, profile_id: str, nudge_type: str) -> set[str]:
    """Return item_ids that are currently snoozed for this nudge_type."""
    # Use naive UTC so SQLite string comparison is consistent (stored values are naive)
    now = datetime.utcnow()
    result = await db.execute(
        select(NudgeState).where(
            NudgeState.profile_id == profile_id,
            NudgeState.nudge_type == nudge_type,
            NudgeState.snoozed_until > now,
        )
    )
    return {s.item_id for s in result.scalars().all()}


# ── Past-due appointments (scheduled but date has passed) ─────────────────────

@router.get("/past-due-appointments", response_model=list[AppointmentResponse])
async def past_due_appointments(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return scheduled appointments whose date has passed and haven't been marked complete."""
    now = datetime.now(timezone.utc)
    appt_result = await db.execute(
        select(Appointment).where(
            Appointment.profile_id == profile_id,
            Appointment.status == "scheduled",
            Appointment.scheduled_date < now,
        ).order_by(Appointment.scheduled_date.desc())
    )
    past_due = appt_result.scalars().all()
    snoozed = await _snoozed_item_ids(db, profile_id, "past_due")
    return [a for a in past_due if a.id not in snoozed]


# ── Upcoming appointments without prep ────────────────────────────────────────

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

    snoozed = await _snoozed_item_ids(db, profile_id, "upcoming_without_prep")

    without_prep = []
    for appt in upcoming:
        if appt.id in snoozed:
            continue
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


async def _compute_all_vitals_alerts(db: AsyncSession, profile_id: str) -> list["VitalsAlert"]:
    """Compute every metric trend alert, regardless of snooze status.

    Split out so both the active list (excludes snoozed) and the
    currently-snoozed list (issue #44 — needs the same trend message, not
    just the bare metric name) can filter this one computation differently
    instead of duplicating the trend logic.
    """
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


@router.get("/vitals-alerts", response_model=list[VitalsAlert])
async def vitals_alerts(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return alerts for meaningful trends in vitals across visits."""
    snoozed = await _snoozed_item_ids(db, profile_id, "vitals_alert")
    all_alerts = await _compute_all_vitals_alerts(db, profile_id)
    return [a for a in all_alerts if a.metric not in snoozed]


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
    snoozed = await _snoozed_item_ids(db, profile_id, "completed_without_avs")

    without_avs = []
    for appt in completed:
        if appt.id in snoozed:
            continue
        appt_date = appt.scheduled_date.date() if appt.scheduled_date else None
        if not appt_date:
            continue
        has_doc = any(_doc_near_appointment(doc, appt_date) for doc in parsed_docs)
        if not has_doc:
            without_avs.append(appt)

    return without_avs


def _parse_date_flexible(date_str: str | None):
    """Try common date formats, return date or None."""
    if not date_str:
        return None
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


# ── Currently-snoozed items (issue #44) ───────────────────────────────────────
#
# Every other endpoint above excludes snoozed items entirely, so once
# something is snoozed there was no way to see it, confirm what's snoozed and
# until when, or reverse it early — "snooze" behaved like a silent, permanent
# delete. This section inverts that filter into a single unified view instead
# of adding a parallel "snoozed_only" mode to every endpoint above.

_NUDGE_TYPE_LABELS = {
    "past_due": "Appointment to close out",
    "upcoming_without_prep": "Visit prep needed",
    "completed_without_avs": "Missing after-visit summary",
    "vitals_alert": "Vitals trend",
}


class SnoozedItem(BaseModel):
    category: str  # nudge_type, or "follow_up" | "lab_order" | "referral"
    category_label: str
    item_id: str
    label: str
    snoozed_until: datetime


async def _appointment_label(db: AsyncSession, appointment_id: str) -> str:
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.doctor))
        .where(Appointment.id == appointment_id)
    )
    appt = result.scalar_one_or_none()
    if not appt:
        return "Appointment (deleted)"
    who = appt.doctor.name if appt.doctor else (appt.purpose or "Appointment")
    when = appt.scheduled_date.strftime("%b %d, %Y") if appt.scheduled_date else ""
    return f"{who} — {when}" if when else who


@router.get("/snoozed-items", response_model=list[SnoozedItem])
async def list_snoozed_items(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return every currently-snoozed item across all nudge types and models."""
    now = datetime.utcnow()
    items: list[SnoozedItem] = []

    # Computed nudges (NudgeState-backed)
    nudge_result = await db.execute(
        select(NudgeState).where(
            NudgeState.profile_id == profile_id,
            NudgeState.snoozed_until > now,
        )
    )
    all_alerts_by_metric = None
    for state in nudge_result.scalars().all():
        if state.nudge_type == "vitals_alert":
            if all_alerts_by_metric is None:
                all_alerts = await _compute_all_vitals_alerts(db, profile_id)
                all_alerts_by_metric = {a.metric: a.message for a in all_alerts}
            label = all_alerts_by_metric.get(state.item_id, f"{state.item_id} trend")
        elif state.nudge_type in ("past_due", "upcoming_without_prep", "completed_without_avs"):
            label = await _appointment_label(db, state.item_id)
        else:
            label = state.item_id
        items.append(SnoozedItem(
            category=state.nudge_type,
            category_label=_NUDGE_TYPE_LABELS.get(state.nudge_type, state.nudge_type),
            item_id=state.item_id,
            label=label,
            snoozed_until=state.snoozed_until,
        ))

    # Model-backed items (FollowUp, LabOrder, Referral) — snoozed_until lives
    # directly on the row, not in NudgeState.
    fu_result = await db.execute(
        select(FollowUp).where(FollowUp.profile_id == profile_id, FollowUp.snoozed_until > now)
    )
    for fu in fu_result.scalars().all():
        items.append(SnoozedItem(
            category="follow_up", category_label="Follow-up appointment",
            item_id=fu.id, label=fu.description, snoozed_until=fu.snoozed_until,
        ))

    lab_result = await db.execute(
        select(LabOrder).where(LabOrder.profile_id == profile_id, LabOrder.snoozed_until > now)
    )
    for lab in lab_result.scalars().all():
        items.append(SnoozedItem(
            category="lab_order", category_label="Lab test ordered",
            item_id=lab.id, label=lab.test_name, snoozed_until=lab.snoozed_until,
        ))

    ref_result = await db.execute(
        select(Referral).where(Referral.profile_id == profile_id, Referral.snoozed_until > now)
    )
    for ref in ref_result.scalars().all():
        label = f"{ref.specialty} — {ref.provider_name}" if ref.provider_name else ref.specialty
        items.append(SnoozedItem(
            category="referral", category_label="Referral to schedule",
            item_id=ref.id, label=label, snoozed_until=ref.snoozed_until,
        ))

    items.sort(key=lambda i: i.snoozed_until)
    return items


@router.delete("/nudge-states/{nudge_type}/{item_id}", status_code=204)
async def unsnooze_nudge(
    profile_id: str,
    nudge_type: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Un-snooze a computed nudge early (issue #44).

    NudgeState.snoozed_until is NOT NULL, unlike FollowUp/LabOrder/Referral's
    snoozed_until — so "un-snoozed" for a computed nudge means deleting the
    row entirely, not nulling a field. `_snoozed_item_ids` already treats a
    missing row as "not snoozed", so this is enough to make the item
    reappear in its normal (unsnoozed) list on the next fetch.
    """
    result = await db.execute(
        select(NudgeState).where(
            NudgeState.profile_id == profile_id,
            NudgeState.nudge_type == nudge_type,
            NudgeState.item_id == item_id,
        )
    )
    state = result.scalar_one_or_none()
    if not state:
        raise HTTPException(status_code=404, detail="Snooze not found")
    await db.delete(state)
    await db.commit()
