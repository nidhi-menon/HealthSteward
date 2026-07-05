"""Document scanning, parsing, and review API endpoints."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    DocumentResponse,
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

router = APIRouter(prefix="/api/profiles/{profile_id}/documents", tags=["documents"])


@router.get("/scan", response_model=list[ScannedFileResponse])
async def scan_documents(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Scan the AVS directory and return all PDF files with their processing status."""
    settings = get_settings()
    scan_dir = Path(settings.avs_scan_path)
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

        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(None, parse_avs_pdf, doc.file_path)

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
    settings = get_settings()
    file_path = Path(settings.avs_scan_path) / filename

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


@router.post("/{document_id}/apply", status_code=200)
async def apply_items(
    profile_id: str,
    document_id: str,
    items: ApplyItemsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply user-selected parsed items to the profile with date-based comparison."""
    doc = await db.get(Document, document_id)
    if not doc or doc.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.parse_status != "completed":
        raise HTTPException(status_code=400, detail="Document must be parsed first.")

    # Parse visit date once for comparison
    visit_dt = _parse_visit_datetime(doc.visit_date)

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

    # Diagnoses -> Condition records (fuzzy dedup by name, date-guarded)
    for dx in items.diagnoses:
        # Fuzzy match: check all conditions for this profile
        result = await db.execute(
            select(Condition).where(Condition.profile_id == profile_id)
        )
        existing_cond = None
        dx_clean = dx.condition.strip().lower()
        for cond in result.scalars().all():
            cond_clean = cond.name.strip().lower()
            if (cond_clean == dx_clean
                    or cond_clean in dx_clean
                    or dx_clean in cond_clean
                    or (dx.icd_10 and cond.icd_10 and dx.icd_10 == cond.icd_10)):
                existing_cond = cond
                break
        if existing_cond:
            # Only update if visit is newer than last update
            if _is_newer(visit_dt, existing_cond.updated_at):
                if dx.icd_10:
                    existing_cond.icd_10 = dx.icd_10
                if dx.severity:
                    existing_cond.severity = dx.severity
                if dx.status:
                    existing_cond.status = dx.status
                dx_date = _parse_date_string(dx.diagnosed_date)
                if dx_date:
                    existing_cond.diagnosed_date = dx_date
                elif not existing_cond.diagnosed_date and visit_dt:
                    existing_cond.diagnosed_date = visit_dt.date()
                counts["conditions"] += 1
            else:
                skipped["conditions"] += 1
        else:
            cond = Condition(
                profile_id=profile_id,
                name=dx.condition,
                icd_10=dx.icd_10,
                severity=dx.severity,
                diagnosed_date=_parse_date_string(dx.diagnosed_date) or (visit_dt.date() if visit_dt else None),
                status=dx.status or "active",
            )
            db.add(cond)
            counts["conditions"] += 1

    # Medication starts -> new Medication records (dedup by name against all meds)
    for med in items.medication_starts:
        clean_name = _clean_med_name(med.name)
        result = await db.execute(
            select(Medication).where(
                Medication.profile_id == profile_id,
            )
        )
        found = False
        for existing_med in result.scalars().all():
            if _fuzzy_med_match(_clean_med_name(existing_med.name), clean_name):
                found = True
                # Update dosage/frequency if visit is newer and med is active
                if existing_med.end_date is None and _is_newer(visit_dt, existing_med.updated_at):
                    if med.strength and med.strength != existing_med.dosage:
                        existing_med.dosage = med.strength
                    if med.instructions and med.instructions != existing_med.frequency:
                        existing_med.frequency = med.instructions
                else:
                    skipped["medications_started"] += 1
                break
        if not found:
            medication = Medication(
                profile_id=profile_id,
                name=med.name,
                dosage=med.strength,
                frequency=med.instructions,
                start_date=_parse_date_string(med.date),
            )
            db.add(medication)
            counts["medications_started"] += 1

    # Medication stops -> set end_date on matching Medication (date-guarded)
    for med in items.medication_stops:
        clean_name = _clean_med_name(med.name)
        result = await db.execute(
            select(Medication).where(
                Medication.profile_id == profile_id,
                Medication.end_date.is_(None),
            )
        )
        for existing_med in result.scalars().all():
            if _fuzzy_med_match(_clean_med_name(existing_med.name), clean_name):
                if _is_newer(visit_dt, existing_med.updated_at):
                    existing_med.end_date = _parse_date_string(med.date)
                    counts["medications_stopped"] += 1
                else:
                    skipped["medications_stopped"] += 1
                break

    # Medication updates -> find existing, update dosage/instructions (date-guarded)
    for med in items.medication_updates:
        clean_name = _clean_med_name(med.name)
        result = await db.execute(
            select(Medication).where(
                Medication.profile_id == profile_id,
                Medication.end_date.is_(None),
            )
        )
        for existing_med in result.scalars().all():
            if _fuzzy_med_match(_clean_med_name(existing_med.name), clean_name):
                if _is_newer(visit_dt, existing_med.updated_at):
                    if med.strength:
                        existing_med.dosage = med.strength
                    if med.instructions:
                        existing_med.frequency = med.instructions
                    counts["medications_updated"] += 1
                else:
                    skipped["medications_updated"] += 1
                break

    # Vitals -> create/update Vitals record for the document
    if items.vitals:
        v = items.vitals
        if any([v.weight, v.bmi, v.blood_pressure, v.heart_rate, v.temperature]):
            vitals = Vitals(
                profile_id=profile_id,
                document_id=document_id,
                weight=v.weight,
                bmi=v.bmi,
                blood_pressure=v.blood_pressure,
                heart_rate=v.heart_rate,
                temperature=v.temperature,
                measured_date=doc.visit_date,
            )
            db.add(vitals)
            counts["vitals"] = 1

    # Lab orders (dedup by test_name + ordered_date)
    for lab in items.lab_orders:
        existing = await db.execute(
            select(LabOrder).where(
                LabOrder.profile_id == profile_id,
                LabOrder.test_name == lab.test,
                LabOrder.ordered_date == lab.ordered_date,
            )
        )
        if existing.scalar_one_or_none():
            skipped["lab_orders"] += 1
        else:
            order = LabOrder(
                profile_id=profile_id,
                document_id=document_id,
                test_name=lab.test,
                ordered_date=lab.ordered_date,
            )
            db.add(order)
            counts["lab_orders"] += 1

    # Referrals (dedup by specialty + document)
    for ref in items.referrals:
        existing = await db.execute(
            select(Referral).where(
                Referral.profile_id == profile_id,
                Referral.document_id == document_id,
                Referral.specialty == ref.specialty,
            )
        )
        if existing.scalar_one_or_none():
            skipped["referrals"] += 1
        else:
            referral = Referral(
                profile_id=profile_id,
                document_id=document_id,
                specialty=ref.specialty,
                provider_name=ref.provider,
                reason=ref.reason,
            )
            db.add(referral)
            counts["referrals"] += 1

    # Follow-ups (dedup by description)
    for fu in items.follow_ups:
        existing = await db.execute(
            select(FollowUp).where(
                FollowUp.profile_id == profile_id,
                FollowUp.description == fu.description,
            )
        )
        if existing.scalar_one_or_none():
            skipped["follow_ups"] += 1
        else:
            follow_up = FollowUp(
                profile_id=profile_id,
                document_id=document_id,
                description=fu.description,
                timeframe=fu.timeframe,
                target_date=fu.target_date,
            )
            db.add(follow_up)
            counts["follow_ups"] += 1

    # Create/match doctor from AVS provider info
    if doc.provider_name:
        provider_doctor_id = await _find_or_create_doctor(
            db, profile_id, doc.provider_name, doc.facility_name
        )
        if provider_doctor_id:
            counts.setdefault("doctors", 0)

    # Appointments (find/create doctors, dedup by date)
    for appt in items.appointments:
        appt_date = _parse_date_string(appt.date)
        if not appt_date:
            skipped["appointments"] += 1
            continue

        appt_datetime = datetime.combine(appt_date, datetime.min.time())

        # Try to find or create a doctor for this appointment
        matched_doctor_id = None
        doctor_name = _extract_doctor_name(appt.description) if appt.description else None
        if doctor_name:
            matched_doctor_id = await _find_or_create_doctor(
                db, profile_id, doctor_name, appt.location
            )

        # Check for existing appointment on the same date
        from sqlalchemy import cast, Date
        existing = await db.execute(
            select(Appointment).where(
                Appointment.profile_id == profile_id,
                cast(Appointment.scheduled_date, Date) == appt_date,
            )
        )
        if existing.scalar_one_or_none():
            skipped["appointments"] += 1
        else:
            appointment = Appointment(
                profile_id=profile_id,
                doctor_id=matched_doctor_id,
                scheduled_date=appt_datetime,
                purpose=appt.description,
                status="scheduled",
            )
            db.add(appointment)
            counts["appointments"] += 1

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


def _fuzzy_med_match(name_a: str, name_b: str) -> bool:
    """Bidirectional substring match for medication names."""
    return name_a == name_b or name_a in name_b or name_b in name_a


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
