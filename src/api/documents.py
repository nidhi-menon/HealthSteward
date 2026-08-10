"""Document scanning, parsing, and review API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.health_profile import get_live_profile_or_404
from src.config import get_settings
from src.data.database import get_db
from src.data.models import (
    Appointment,
    Condition,
    Doctor,
    Document,
    FollowUp,
    LabOrder,
    Medication,
    Referral,
    Vitals,
)
from src.models.schemas import (
    ApplyItemsRequest,
    ApplyPlanEntry,
    ApplyPlanResponse,
    DocumentResponse,
    PlanFieldChange,
    ParsedAppointment,
    ParsedDiagnosis,
    ParsedFollowUp,
    ParsedItemsResponse,
    ParsedLabOrder,
    ParsedMedicationChange,
    ParsedReferral,
    ParsedVitals,
    ScannedFileResponse,
)
from src.services import settings_service

router = APIRouter(prefix="/api/profiles/{profile_id}/documents", tags=["documents"])


@router.get("/scan", response_model=list[ScannedFileResponse])
async def scan_documents(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Scan the profile's AVS subdirectory and return all PDF files with their status.

    Per-profile partitioning (issue #49, DEC-030): each profile's files live
    under `data/avs/<profile_id>/`, not a flat shared folder. This makes
    cross-profile visibility structurally impossible rather than merely
    filtered out in the response.
    """
    await get_live_profile_or_404(profile_id, db)
    settings = get_settings()
    scan_dir = Path(settings.avs_scan_path) / profile_id
    scan_dir.mkdir(parents=True, exist_ok=True)

    # Get all existing Document records for this profile
    result = await db.execute(
        select(Document).where(Document.profile_id == profile_id)
    )
    existing_docs = {
        (doc.original_filename, doc.file_size_bytes): doc
        for doc in result.scalars().all()
    }

    scanned: list[ScannedFileResponse] = []
    for entry in sorted(scan_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not entry.is_file() or not entry.name.lower().endswith(".pdf"):
            continue

        stat = entry.stat()
        file_size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        # Check if we have a matching Document record
        doc = existing_docs.get((entry.name, file_size))

        scanned.append(ScannedFileResponse(
            filename=entry.name,
            file_size_bytes=file_size,
            modified_date=modified,
            status=doc.parse_status if doc else "new",
            document_id=doc.id if doc else None,
        ))

    return scanned


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    profile_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get document metadata."""
    await get_live_profile_or_404(profile_id, db)
    doc = await db.get(Document, document_id)
    if not doc or doc.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/{document_id}/parsed", response_model=ParsedItemsResponse)
async def get_parsed_items(
    profile_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get parsed items from a document. Triggers parsing if pending."""
    await get_live_profile_or_404(profile_id, db)
    doc = await db.get(Document, document_id)
    if not doc or doc.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Return cached result if already parsed
    if doc.parse_status == "completed" and doc.raw_parse_result:
        return _build_parsed_response(doc.raw_parse_result)

    if doc.parse_status == "failed":
        raise HTTPException(
            status_code=422,
            detail=f"Parsing failed: {doc.parse_error or 'unknown error'}",
        )

    if doc.parse_status == "parsing":
        raise HTTPException(status_code=202, detail="Parsing in progress. Try again shortly.")

    # Trigger parse
    doc.parse_status = "parsing"
    await db.flush()
    await db.commit()

    try:
        from src.parsers import parse_avs_pdf

        # Resolve the parser model here rather than letting parse_avs_pdf fall
        # back to the env default: the DB overlay is only reachable from an
        # async session, and parse_avs_pdf runs in a thread executor. Without
        # this the Settings-page value would be stored but never applied.
        effective = await settings_service.get_effective_settings(db)

        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(
            None, parse_avs_pdf, doc.file_path, effective.avs_parser_model
        )

        doc.raw_parse_result = parsed
        doc.parse_status = "completed"

        # Extract visit metadata
        patient = parsed.get("patient", {})
        provider = parsed.get("provider", {})
        doc.visit_date = patient.get("visit_date")
        doc.provider_name = provider.get("name")
        doc.facility_name = provider.get("facility")

        await db.flush()
        await db.commit()

        logger.info(f"Successfully parsed document {doc.id}")
        return _build_parsed_response(parsed)

    except Exception as e:
        doc.parse_status = "failed"
        doc.parse_error = str(e)
        await db.flush()
        await db.commit()
        logger.error(f"Failed to parse document {doc.id}: {e}")
        raise HTTPException(status_code=422, detail=f"Parsing failed: {e}")


@router.post("/parse-file")
async def parse_file(
    profile_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    """Create a Document record for a scanned file and trigger parsing."""
    await get_live_profile_or_404(profile_id, db)
    settings = get_settings()
    file_path = Path(settings.avs_scan_path) / profile_id / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found in scan directory.")

    file_size = file_path.stat().st_size

    # Check if document record already exists
    result = await db.execute(
        select(Document).where(
            Document.profile_id == profile_id,
            Document.original_filename == filename,
            Document.file_size_bytes == file_size,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Re-parse if failed, otherwise return existing
        if existing.parse_status == "failed":
            existing.parse_status = "pending"
            existing.parse_error = None
            await db.flush()
            await db.commit()
            return {"document_id": existing.id, "status": "pending"}
        return {"document_id": existing.id, "status": existing.parse_status}

    # Create new Document record
    doc = Document(
        profile_id=profile_id,
        original_filename=filename,
        file_path=str(file_path),
        file_size_bytes=file_size,
        parse_status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.commit()

    logger.info(f"Created document record {doc.id} for {filename}")
    return {"document_id": doc.id, "status": "pending"}


@router.post("/{document_id}/apply/preview", response_model=ApplyPlanResponse)
async def preview_apply_items(
    profile_id: str,
    document_id: str,
    items: ApplyItemsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Show what applying these items would change, without committing anything.

    Issue #46: applying a parse used to overwrite fields in place with no way to
    see — let alone undo — what it replaced. This is the review step: the same
    plan the apply will execute, rendered as a per-field `old -> new` diff.

    Read-only. Takes the same body as `/apply`, so the preview reflects the
    user's actual selective-apply choices rather than a hypothetical full apply.
    """
    doc = await _get_parsed_document_or_404(profile_id, document_id, db)
    plan = await _build_apply_plan(db, profile_id, doc, items)
    return _plan_to_response(plan)


@router.post("/{document_id}/apply", status_code=200)
async def apply_items(
    profile_id: str,
    document_id: str,
    items: ApplyItemsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply user-selected parsed items to the profile with date-based comparison.

    The decisions themselves live in `_build_apply_plan`; this endpoint only
    executes them. Sharing that one code path with `/apply/preview` is what
    keeps the reviewed diff and the committed write from drifting apart.
    """
    doc = await _get_parsed_document_or_404(profile_id, document_id, db)

    plan = await _build_apply_plan(db, profile_id, doc, items)
    response = _plan_to_response(plan)

    # Stale-preview guard: if the profile changed between the user reviewing
    # the diff and confirming it, the plan they approved is no longer the plan
    # we would execute. Abort and hand back the re-derived plan for re-review.
    if items.expected_plan_fingerprint and (
        items.expected_plan_fingerprint != response.plan_fingerprint
    ):
        logger.info(
            f"Aborted apply for document {doc.id}: plan changed since preview "
            f"({items.expected_plan_fingerprint} -> {response.plan_fingerprint})"
        )
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "stale_plan",
                "message": (
                    "This profile changed since you reviewed these items. "
                    "Review the updated changes and confirm again."
                ),
                "plan": response.model_dump(),
            },
        )

    counts, skipped = await _execute_apply_plan(db, profile_id, document_id, plan)

    await db.flush()
    await db.commit()

    # Fetch newly created action items from this document for the post-AVS panel
    fu_result = await db.execute(
        select(FollowUp).where(FollowUp.document_id == document_id)
    )
    lab_result = await db.execute(
        select(LabOrder).where(LabOrder.document_id == document_id)
    )
    ref_result = await db.execute(
        select(Referral).where(Referral.document_id == document_id)
    )

    from src.models.schemas import FollowUpResponse, LabOrderResponse, ReferralResponse

    logger.info(f"Applied items from document {doc.id}: counts={counts}, skipped={skipped}")
    return {
        "status": "applied",
        "counts": counts,
        "skipped": skipped,
        "action_items": {
            "follow_ups": [FollowUpResponse.model_validate(fu).model_dump() for fu in fu_result.scalars().all()],
            "lab_orders": [LabOrderResponse.model_validate(lab).model_dump() for lab in lab_result.scalars().all()],
            "referrals": [ReferralResponse.model_validate(ref).model_dump() for ref in ref_result.scalars().all()],
        },
    }


async def _get_parsed_document_or_404(
    profile_id: str, document_id: str, db: AsyncSession
) -> Document:
    """Resolve a parsed document for this profile, or raise the right error."""
    await get_live_profile_or_404(profile_id, db)
    doc = await db.get(Document, document_id)
    if not doc or doc.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.parse_status != "completed":
        raise HTTPException(status_code=400, detail="Document must be parsed first.")
    return doc


@dataclass
class _PlanEntry:
    """One decision an apply would make, plus what it takes to carry it out.

    `changes` is for display only — it is the per-field diff the user reviews.
    The write itself comes from `update_values` (for `update`) or
    `create_values` (for `create`), so rendering can never move data.
    """

    entity_type: str
    action: str  # create | update | skip
    label: str
    entity_id: Optional[str] = None
    reason: Optional[str] = None
    changes: list[PlanFieldChange] = field(default_factory=list)
    # Which bucket of the apply response this entry moves, if any. A matched
    # medication start that only refreshes a dosage moves neither, which is
    # the behaviour apply has always had.
    count_key: Optional[str] = None
    skip_key: Optional[str] = None
    model: Any = None
    create_values: Optional[dict] = None
    update_values: Optional[dict] = None
    # (name, clinic) for rows whose doctor must be matched or created at
    # execution time. Never resolved during planning — a preview must not write.
    doctor_hint: Optional[tuple[str, Optional[str]]] = None


_SKIP_RECORD_IS_NEWER = "the existing record is newer than this visit"
_SKIP_ALREADY_IN_DOCUMENT = "already included earlier in this document"
_STOP_REASON = "marks this medication stopped"


def _stop_end_date(
    date_str: str | None, visit_dt: datetime | None
) -> tuple[date | None, str]:
    """Decide the `end_date` a medication stop should write, and say why.

    Issue #149: `_parse_date_string` returns `None` for anything outside its
    four formats, and `None` is exactly what an active medication's `end_date`
    already holds — so feeding it straight through made an unreadable stop date
    a silent no-op that still reported as applied.

    The rule this encodes: never report an applied change that didn't change
    anything (DEC-035). A stop the document clearly asserted still gets applied
    when there's an honest date to fall back on — the visit's own date, which
    the plan entry names as inferred — and is skipped visibly when there isn't.
    """
    parsed = _parse_date_string(date_str)
    if parsed is not None:
        return parsed, _STOP_REASON

    given = (date_str or "").strip()
    problem = (
        f'stop date "{given}" couldn\'t be read' if given
        else "no stop date in the document"
    )
    if visit_dt is None:
        return None, (
            f"can't mark this medication stopped — {problem}, and this "
            f"document has no readable visit date to fall back on"
        )
    fallback = visit_dt.date()
    return fallback, f"{_STOP_REASON} — {problem}, using the visit date {fallback}"


def _display_value(value: Any) -> str | None:
    """Render a stored or incoming value for the diff view."""
    if value is None or value == "":
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _change(field_name: str, old: Any, new: Any) -> PlanFieldChange:
    old_display = _display_value(old)
    new_display = _display_value(new)
    return PlanFieldChange(
        field=field_name,
        old_value=old_display,
        new_value=new_display,
        changed=old_display != new_display,
    )


def _creation_changes(values: dict, skip: tuple[str, ...] = ("profile_id", "document_id")) -> list[PlanFieldChange]:
    """Render a create as a diff from nothing, so the UI has one shape to draw."""
    return [
        _change(name, None, value)
        for name, value in values.items()
        if name not in skip and value is not None
    ]


def _condition_matches(cond: Condition, dx_clean: str, dx_icd: str | None) -> bool:
    """The fuzzy rule apply has always used to decide a diagnosis is not new."""
    cond_clean = cond.name.strip().lower()
    return (
        _fuzzy_text_match(cond_clean, dx_clean)
        or bool(dx_icd and cond.icd_10 and dx_icd == cond.icd_10)
    )


async def _plan_doctor(
    db: AsyncSession, profile_id: str, name: str, clinic: str | None
) -> _PlanEntry | None:
    """Read-only counterpart to `_find_or_create_doctor`, for the preview."""
    if not name or len(name.strip()) < 2:
        return None

    name_lower = name.strip().lower()
    result = await db.execute(select(Doctor).where(Doctor.profile_id == profile_id))
    for existing in result.scalars().all():
        if _fuzzy_text_match(existing.name.lower(), name_lower):
            if clinic and not existing.clinic:
                return _PlanEntry(
                    entity_type="doctor", action="update", label=existing.name,
                    entity_id=existing.id, reason="filling in a missing clinic",
                    changes=[_change("clinic", existing.clinic, clinic)],
                    doctor_hint=(name, clinic),
                )
            return _PlanEntry(
                entity_type="doctor", action="skip", label=existing.name,
                entity_id=existing.id, reason="already on file",
                doctor_hint=(name, clinic),
            )

    return _PlanEntry(
        entity_type="doctor", action="create", label=name.strip(),
        changes=_creation_changes({"name": name.strip(), "clinic": clinic}),
        doctor_hint=(name, clinic),
    )


async def _build_apply_plan(
    db: AsyncSession, profile_id: str, doc: Document, items: ApplyItemsRequest
) -> list[_PlanEntry]:
    """Decide what applying `items` would do, without doing any of it.

    Read-only by construction: every branch appends to the plan instead of
    mutating, so `/apply/preview` and `/apply` can share it (issue #46).
    """
    visit_dt = _parse_visit_datetime(doc.visit_date)
    plan: list[_PlanEntry] = []

    conditions = (await db.execute(
        select(Condition).where(Condition.profile_id == profile_id)
    )).scalars().all()
    medications = (await db.execute(
        select(Medication).where(Medication.profile_id == profile_id)
    )).scalars().all()
    active_medications = [m for m in medications if m.end_date is None]

    # What this plan will create, so two items in the same document can't each
    # create a row for the same thing. Apply used to depend on whether a flush
    # happened to have run mid-loop; this makes it deterministic.
    planned_conditions: list[str] = []
    planned_medications: list[str] = []
    planned_labs: set[tuple] = set()
    planned_referrals: set[str] = set()
    planned_follow_ups: set[str] = set()
    planned_appointments: set = set()

    # Diagnoses -> Condition records (fuzzy dedup by name, date-guarded)
    for dx in items.diagnoses:
        dx_clean = dx.condition.strip().lower()
        existing_cond = next(
            (c for c in conditions if _condition_matches(c, dx_clean, dx.icd_10)), None
        )
        if existing_cond:
            if not _is_newer(visit_dt, existing_cond.updated_at):
                plan.append(_PlanEntry(
                    entity_type="condition", action="skip", label=dx.condition,
                    entity_id=existing_cond.id, reason=_SKIP_RECORD_IS_NEWER,
                    skip_key="conditions",
                ))
                continue

            update_values: dict = {}
            changes: list[PlanFieldChange] = []
            if dx.icd_10:
                update_values["icd_10"] = dx.icd_10
                changes.append(_change("icd_10", existing_cond.icd_10, dx.icd_10))
            if dx.severity:
                update_values["severity"] = dx.severity
                changes.append(_change("severity", existing_cond.severity, dx.severity))
            if dx.status:
                update_values["status"] = dx.status
                changes.append(_change("status", existing_cond.status, dx.status))
            dx_date = _parse_date_string(dx.diagnosed_date)
            if dx_date:
                update_values["diagnosed_date"] = dx_date
                changes.append(
                    _change("diagnosed_date", existing_cond.diagnosed_date, dx_date)
                )
            elif not existing_cond.diagnosed_date and visit_dt:
                update_values["diagnosed_date"] = visit_dt.date()
                changes.append(_change("diagnosed_date", None, visit_dt.date()))

            plan.append(_PlanEntry(
                entity_type="condition", action="update", label=existing_cond.name,
                entity_id=existing_cond.id, reason="updates a condition already on file",
                changes=changes, count_key="conditions", model=Condition,
                update_values=update_values,
            ))
        elif any(_fuzzy_text_match(p, dx_clean) for p in planned_conditions):
            plan.append(_PlanEntry(
                entity_type="condition", action="skip", label=dx.condition,
                reason=_SKIP_ALREADY_IN_DOCUMENT, skip_key="conditions",
            ))
        else:
            values = {
                "profile_id": profile_id,
                "name": dx.condition,
                "icd_10": dx.icd_10,
                "severity": dx.severity,
                "diagnosed_date": (
                    _parse_date_string(dx.diagnosed_date)
                    or (visit_dt.date() if visit_dt else None)
                ),
                "status": dx.status or "active",
            }
            planned_conditions.append(dx_clean)
            plan.append(_PlanEntry(
                entity_type="condition", action="create", label=dx.condition,
                reason="new condition", changes=_creation_changes(values),
                count_key="conditions", model=Condition, create_values=values,
            ))

    # Medication starts -> new Medication records (dedup by name against all meds)
    for med in items.medication_starts:
        clean_name = _clean_med_name(med.name)
        existing_med = next(
            (m for m in medications
             if _fuzzy_med_match(_clean_med_name(m.name), clean_name)),
            None,
        )
        if existing_med:
            if existing_med.end_date is not None:
                plan.append(_PlanEntry(
                    entity_type="medication", action="skip", label=med.name,
                    entity_id=existing_med.id,
                    reason="already on file as a stopped medication",
                    skip_key="medications_started",
                ))
                continue
            if not _is_newer(visit_dt, existing_med.updated_at):
                plan.append(_PlanEntry(
                    entity_type="medication", action="skip", label=med.name,
                    entity_id=existing_med.id, reason=_SKIP_RECORD_IS_NEWER,
                    skip_key="medications_started",
                ))
                continue

            update_values = {}
            changes = []
            if med.strength and med.strength != existing_med.dosage:
                update_values["dosage"] = med.strength
                changes.append(_change("dosage", existing_med.dosage, med.strength))
            if med.instructions and med.instructions != existing_med.frequency:
                update_values["frequency"] = med.instructions
                changes.append(
                    _change("frequency", existing_med.frequency, med.instructions)
                )

            if not update_values:
                plan.append(_PlanEntry(
                    entity_type="medication", action="skip", label=med.name,
                    entity_id=existing_med.id,
                    reason="already recorded with these details",
                ))
                continue

            # Deliberately uncounted: refreshing an already-known medication is
            # not a new start, and apply has never counted it as one.
            plan.append(_PlanEntry(
                entity_type="medication", action="update", label=existing_med.name,
                entity_id=existing_med.id,
                reason="already on file — refreshing dosage/instructions",
                changes=changes, model=Medication, update_values=update_values,
            ))
        elif any(_fuzzy_med_match(p, clean_name) for p in planned_medications):
            plan.append(_PlanEntry(
                entity_type="medication", action="skip", label=med.name,
                reason=_SKIP_ALREADY_IN_DOCUMENT, skip_key="medications_started",
            ))
        else:
            values = {
                "profile_id": profile_id,
                "name": med.name,
                "dosage": med.strength,
                "frequency": med.instructions,
                "start_date": _parse_date_string(med.date),
            }
            planned_medications.append(clean_name)
            plan.append(_PlanEntry(
                entity_type="medication", action="create", label=med.name,
                reason="new medication", changes=_creation_changes(values),
                count_key="medications_started", model=Medication, create_values=values,
            ))

    # Medication stops -> set end_date on matching Medication (date-guarded)
    for med in items.medication_stops:
        clean_name = _clean_med_name(med.name)
        existing_med = next(
            (m for m in active_medications
             if _fuzzy_med_match(_clean_med_name(m.name), clean_name)),
            None,
        )
        if not existing_med:
            plan.append(_PlanEntry(
                entity_type="medication", action="skip", label=med.name,
                reason="no active medication matches this name",
            ))
        elif _is_newer(visit_dt, existing_med.updated_at):
            end_date, reason = _stop_end_date(med.date, visit_dt)
            if end_date is None:
                # Writing `None` here would be a no-op — an active medication's
                # `end_date` is already `None` — while still reporting the stop
                # as applied (issue #149). Skip visibly instead.
                plan.append(_PlanEntry(
                    entity_type="medication", action="skip", label=med.name,
                    entity_id=existing_med.id, reason=reason,
                    skip_key="medications_stopped",
                ))
                continue
            plan.append(_PlanEntry(
                entity_type="medication", action="update", label=existing_med.name,
                entity_id=existing_med.id, reason=reason,
                changes=[_change("end_date", existing_med.end_date, end_date)],
                count_key="medications_stopped", model=Medication,
                update_values={"end_date": end_date},
            ))
        else:
            plan.append(_PlanEntry(
                entity_type="medication", action="skip", label=med.name,
                entity_id=existing_med.id, reason=_SKIP_RECORD_IS_NEWER,
                skip_key="medications_stopped",
            ))

    # Medication updates -> find existing, update dosage/instructions (date-guarded)
    for med in items.medication_updates:
        clean_name = _clean_med_name(med.name)
        existing_med = next(
            (m for m in active_medications
             if _fuzzy_med_match(_clean_med_name(m.name), clean_name)),
            None,
        )
        if not existing_med:
            plan.append(_PlanEntry(
                entity_type="medication", action="skip", label=med.name,
                reason="no active medication matches this name",
            ))
            continue
        if not _is_newer(visit_dt, existing_med.updated_at):
            plan.append(_PlanEntry(
                entity_type="medication", action="skip", label=med.name,
                entity_id=existing_med.id, reason=_SKIP_RECORD_IS_NEWER,
                skip_key="medications_updated",
            ))
            continue

        update_values = {}
        changes = []
        if med.strength:
            update_values["dosage"] = med.strength
            changes.append(_change("dosage", existing_med.dosage, med.strength))
        if med.instructions:
            update_values["frequency"] = med.instructions
            changes.append(
                _change("frequency", existing_med.frequency, med.instructions)
            )
        plan.append(_PlanEntry(
            entity_type="medication", action="update", label=existing_med.name,
            entity_id=existing_med.id, reason="changes an existing medication",
            changes=changes, count_key="medications_updated", model=Medication,
            update_values=update_values,
        ))

    # Vitals -> new Vitals record for the document
    if items.vitals:
        v = items.vitals
        if any([v.weight, v.bmi, v.blood_pressure, v.heart_rate, v.temperature]):
            values = {
                "profile_id": profile_id,
                "document_id": doc.id,
                "weight": v.weight,
                "bmi": v.bmi,
                "blood_pressure": v.blood_pressure,
                "heart_rate": v.heart_rate,
                "temperature": v.temperature,
                "measured_date": doc.visit_date,
            }
            plan.append(_PlanEntry(
                entity_type="vitals", action="create",
                label="Vitals recorded at this visit",
                reason="new vitals reading", changes=_creation_changes(values),
                count_key="vitals", model=Vitals, create_values=values,
            ))

    # Lab orders (dedup by test_name + ordered_date)
    for lab in items.lab_orders:
        key = (lab.test, lab.ordered_date)
        existing = await db.execute(
            select(LabOrder).where(
                LabOrder.profile_id == profile_id,
                LabOrder.test_name == lab.test,
                LabOrder.ordered_date == lab.ordered_date,
            )
        )
        if existing.scalar_one_or_none():
            plan.append(_PlanEntry(
                entity_type="lab_order", action="skip", label=lab.test,
                reason="already recorded", skip_key="lab_orders",
            ))
        elif key in planned_labs:
            plan.append(_PlanEntry(
                entity_type="lab_order", action="skip", label=lab.test,
                reason=_SKIP_ALREADY_IN_DOCUMENT, skip_key="lab_orders",
            ))
        else:
            values = {
                "profile_id": profile_id,
                "document_id": doc.id,
                "test_name": lab.test,
                "ordered_date": lab.ordered_date,
            }
            planned_labs.add(key)
            plan.append(_PlanEntry(
                entity_type="lab_order", action="create", label=lab.test,
                reason="new lab order", changes=_creation_changes(values),
                count_key="lab_orders", model=LabOrder, create_values=values,
            ))

    # Referrals (dedup by specialty + document)
    for ref in items.referrals:
        existing = await db.execute(
            select(Referral).where(
                Referral.profile_id == profile_id,
                Referral.document_id == doc.id,
                Referral.specialty == ref.specialty,
            )
        )
        if existing.scalar_one_or_none():
            plan.append(_PlanEntry(
                entity_type="referral", action="skip", label=ref.specialty,
                reason="already recorded", skip_key="referrals",
            ))
        elif ref.specialty in planned_referrals:
            plan.append(_PlanEntry(
                entity_type="referral", action="skip", label=ref.specialty,
                reason=_SKIP_ALREADY_IN_DOCUMENT, skip_key="referrals",
            ))
        else:
            values = {
                "profile_id": profile_id,
                "document_id": doc.id,
                "specialty": ref.specialty,
                "provider_name": ref.provider,
                "reason": ref.reason,
            }
            planned_referrals.add(ref.specialty)
            plan.append(_PlanEntry(
                entity_type="referral", action="create", label=ref.specialty,
                reason="new referral", changes=_creation_changes(values),
                count_key="referrals", model=Referral, create_values=values,
            ))

    # Follow-ups (dedup by description)
    for fu in items.follow_ups:
        existing = await db.execute(
            select(FollowUp).where(
                FollowUp.profile_id == profile_id,
                FollowUp.description == fu.description,
            )
        )
        if existing.scalar_one_or_none():
            plan.append(_PlanEntry(
                entity_type="follow_up", action="skip", label=fu.description,
                reason="already recorded", skip_key="follow_ups",
            ))
        elif fu.description in planned_follow_ups:
            plan.append(_PlanEntry(
                entity_type="follow_up", action="skip", label=fu.description,
                reason=_SKIP_ALREADY_IN_DOCUMENT, skip_key="follow_ups",
            ))
        else:
            values = {
                "profile_id": profile_id,
                "document_id": doc.id,
                "description": fu.description,
                "timeframe": fu.timeframe,
                "target_date": fu.target_date,
            }
            planned_follow_ups.add(fu.description)
            plan.append(_PlanEntry(
                entity_type="follow_up", action="create", label=fu.description,
                reason="new follow-up", changes=_creation_changes(values),
                count_key="follow_ups", model=FollowUp, create_values=values,
            ))

    # Create/match doctor from AVS provider info
    if doc.provider_name:
        provider_entry = await _plan_doctor(
            db, profile_id, doc.provider_name, doc.facility_name
        )
        if provider_entry:
            plan.append(provider_entry)

    # Appointments (find/create doctors, dedup by date)
    from sqlalchemy import cast, Date

    for appt in items.appointments:
        appt_date = _parse_date_string(appt.date)
        label = appt.description or "Appointment"
        if not appt_date:
            plan.append(_PlanEntry(
                entity_type="appointment", action="skip", label=label,
                reason="no usable date on this appointment", skip_key="appointments",
            ))
            continue

        existing = await db.execute(
            select(Appointment).where(
                Appointment.profile_id == profile_id,
                cast(Appointment.scheduled_date, Date) == appt_date,
            )
        )
        if existing.scalar_one_or_none():
            plan.append(_PlanEntry(
                entity_type="appointment", action="skip", label=label,
                reason="an appointment already exists on this date",
                skip_key="appointments",
            ))
        elif appt_date in planned_appointments:
            plan.append(_PlanEntry(
                entity_type="appointment", action="skip", label=label,
                reason=_SKIP_ALREADY_IN_DOCUMENT, skip_key="appointments",
            ))
        else:
            doctor_name = (
                _extract_doctor_name(appt.description) if appt.description else None
            )
            values = {
                "profile_id": profile_id,
                "scheduled_date": datetime.combine(appt_date, datetime.min.time()),
                "purpose": appt.description,
                "status": "scheduled",
            }
            changes = _creation_changes(values)
            if doctor_name:
                changes.append(_change("doctor", None, doctor_name))
            planned_appointments.add(appt_date)
            plan.append(_PlanEntry(
                entity_type="appointment", action="create", label=label,
                reason="new appointment", changes=changes,
                count_key="appointments", model=Appointment, create_values=values,
                doctor_hint=(doctor_name, appt.location) if doctor_name else None,
            ))

    return plan


def _plan_totals(plan: list[_PlanEntry]) -> tuple[dict, dict]:
    """Project a plan onto the counts/skipped buckets the apply response uses.

    Both the preview and the real apply report from here, so the totals a user
    reviews are the totals they get.
    """
    counts = {
        "conditions": 0,
        "medications_started": 0,
        "medications_stopped": 0,
        "medications_updated": 0,
        "vitals": 0,
        "lab_orders": 0,
        "referrals": 0,
        "follow_ups": 0,
        "appointments": 0,
    }
    skipped = {
        "conditions": 0,
        "medications_started": 0,
        "medications_stopped": 0,
        "medications_updated": 0,
        "lab_orders": 0,
        "referrals": 0,
        "follow_ups": 0,
        "appointments": 0,
    }

    for entry in plan:
        if entry.entity_type == "doctor":
            # Matched or created, the provider always ends up on file.
            counts.setdefault("doctors", 0)
        elif entry.action == "skip":
            if entry.skip_key:
                skipped[entry.skip_key] += 1
        elif entry.count_key:
            counts[entry.count_key] += 1

    return counts, skipped


async def _execute_apply_plan(
    db: AsyncSession, profile_id: str, document_id: str, plan: list[_PlanEntry]
) -> tuple[dict, dict]:
    """Carry out a plan. All the decisions were made in `_build_apply_plan`."""
    for entry in plan:
        if entry.entity_type == "doctor":
            name, clinic = entry.doctor_hint
            await _find_or_create_doctor(db, profile_id, name, clinic)
            continue
        if entry.action == "skip":
            continue

        if entry.action == "update":
            row = await db.get(entry.model, entry.entity_id)
            if row is None:
                logger.warning(
                    f"Plan targeted a missing {entry.entity_type} {entry.entity_id}; "
                    f"skipping that write."
                )
                continue
            for field_name, value in (entry.update_values or {}).items():
                setattr(row, field_name, value)
        elif entry.action == "create":
            values = dict(entry.create_values or {})
            if entry.doctor_hint:
                name, clinic = entry.doctor_hint
                values["doctor_id"] = await _find_or_create_doctor(
                    db, profile_id, name, clinic
                )
            db.add(entry.model(**values))

    return _plan_totals(plan)


def _plan_fingerprint(entries: list[ApplyPlanEntry]) -> str:
    """A stable digest of a plan, used to detect that it changed under the user.

    Covers the stored values too, so an edit to a targeted record in another tab
    invalidates the preview even when the actions themselves are unchanged.
    """
    payload = json.dumps(
        [entry.model_dump() for entry in entries], sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _plan_to_response(plan: list[_PlanEntry]) -> ApplyPlanResponse:
    """Render the internal plan as the reviewable, serialisable version."""
    entries = [
        ApplyPlanEntry(
            entity_type=entry.entity_type,
            action=entry.action,
            label=entry.label,
            entity_id=entry.entity_id,
            reason=entry.reason,
            changes=entry.changes,
        )
        for entry in plan
    ]
    counts, skipped = _plan_totals(plan)
    return ApplyPlanResponse(
        plan_fingerprint=_plan_fingerprint(entries),
        entries=entries,
        counts=counts,
        skipped=skipped,
    )


def _extract_doctor_name(text: str) -> str | None:
    """Extract a doctor name from text like 'Video Visit with D.M. Antoniucci, MD'.

    Looks for patterns with MD, M.D., DO, D.O., NP, PA suffixes or
    'Dr.' / 'with' prefixes. Returns None if no doctor name found.
    """
    if not text:
        return None

    # Pattern: "with <Name>, MD" or "with <Name> MD" or "with Dr. <Name>"
    import re
    # Match "with <name>, MD/M.D./DO" etc
    m = re.search(r'(?:with|by)\s+(.+?(?:,?\s*(?:M\.?D\.?|D\.?O\.?|N\.?P\.?|P\.?A\.?))\s*)$', text, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(',')

    # Match "Dr. <name>" anywhere
    m = re.search(r'Dr\.?\s+(\S.+?)(?:\s*[-,]|$)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(',')

    # If the whole text looks like a doctor name (contains MD/DO suffix)
    if re.search(r'(?:M\.?D\.?|D\.?O\.?)\s*$', text.strip(), re.IGNORECASE):
        return text.strip()

    return None


async def _find_or_create_doctor(
    db: AsyncSession, profile_id: str, name: str, clinic: str | None = None
) -> str | None:
    """Find an existing doctor by name match, or create a new one.

    Returns the doctor's ID if found/created, or None if no meaningful name.
    """
    if not name or len(name.strip()) < 2:
        return None

    name_clean = name.strip()
    name_lower = name_clean.lower()

    # Check existing doctors for a fuzzy match
    result = await db.execute(
        select(Doctor).where(Doctor.profile_id == profile_id)
    )
    for doc_record in result.scalars().all():
        doc_name_lower = doc_record.name.lower()
        if doc_name_lower == name_lower or doc_name_lower in name_lower or name_lower in doc_name_lower:
            # Update clinic if missing
            if clinic and not doc_record.clinic:
                doc_record.clinic = clinic
            return doc_record.id

    # Create new doctor
    new_doctor = Doctor(
        profile_id=profile_id,
        name=name_clean,
        clinic=clinic,
    )
    db.add(new_doctor)
    await db.flush()
    return new_doctor.id


def _parse_visit_datetime(date_str: str | None) -> datetime | None:
    """Parse a visit date string into a timezone-naive datetime for comparison."""
    if not date_str:
        return None
    from datetime import datetime as dt
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y", "%B %d %Y"):
        try:
            return dt.strptime(date_str.strip().rstrip(","), fmt)
        except ValueError:
            continue
    return None


def _is_newer(visit_dt: datetime | None, record_updated_at: datetime) -> bool:
    """Check if the visit date is newer than a record's updated_at.

    If visit_dt is None (unparseable), treat as newer to avoid losing data.
    """
    if visit_dt is None:
        return True
    return visit_dt >= record_updated_at


def _clean_med_name(name: str) -> str:
    """Normalize medication name for comparison."""
    return re.sub(r"\s*\(.*?\)", "", name).strip().lower()


def _fuzzy_text_match(text_a: str, text_b: str) -> bool:
    """Bidirectional substring match, the repo's standing rule for name dedup."""
    return text_a == text_b or text_a in text_b or text_b in text_a


def _fuzzy_med_match(name_a: str, name_b: str) -> bool:
    """Bidirectional substring match for medication names."""
    return _fuzzy_text_match(name_a, name_b)


def _build_parsed_response(raw: dict) -> ParsedItemsResponse:
    """Convert raw parse result dict to ParsedItemsResponse."""
    vitals_raw = raw.get("vitals", {})
    bmi = vitals_raw.get("bmi")
    if isinstance(bmi, str):
        try:
            bmi = float(bmi)
        except (ValueError, TypeError):
            bmi = None

    return ParsedItemsResponse(
        patient=raw.get("patient", {}),
        provider=raw.get("provider", {}),
        vitals=ParsedVitals(
            weight=vitals_raw.get("weight"),
            bmi=bmi,
            blood_pressure=vitals_raw.get("blood_pressure"),
            heart_rate=vitals_raw.get("heart_rate"),
            temperature=vitals_raw.get("temperature"),
        ),
        diagnoses=[
            ParsedDiagnosis(**d) for d in (raw.get("diagnoses") or [])
        ],
        medication_changes=[
            ParsedMedicationChange(**m) for m in (raw.get("medication_changes") or [])
        ],
        lab_orders=[
            ParsedLabOrder(**o) for o in (raw.get("lab_orders") or [])
        ],
        referrals=[
            ParsedReferral(**r) for r in (raw.get("referrals") or [])
        ],
        follow_up_recommended=[
            ParsedFollowUp(**f) for f in (raw.get("follow_up_recommended") or [])
        ],
        upcoming_appointments=[
            ParsedAppointment(**a) for a in (raw.get("upcoming_appointments") or [])
        ],
        notes=raw.get("notes", []),
    )


def _parse_date_string(date_str: str | None):
    """Try to parse a date string into a date object, or return None."""
    if not date_str:
        return None
    from datetime import datetime as dt
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y", "%B %d %Y"):
        try:
            return dt.strptime(date_str.strip().rstrip(","), fmt).date()
        except ValueError:
            continue
    return None
