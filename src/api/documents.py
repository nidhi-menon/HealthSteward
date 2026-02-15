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
    Condition,
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
    """Apply user-selected parsed items to the profile."""
    doc = await db.get(Document, document_id)
    if not doc or doc.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.parse_status != "completed":
        raise HTTPException(status_code=400, detail="Document must be parsed first.")

    counts = {
        "conditions": 0,
        "medications_started": 0,
        "medications_stopped": 0,
        "medications_updated": 0,
        "vitals": 0,
        "lab_orders": 0,
        "referrals": 0,
        "follow_ups": 0,
    }

    # Diagnoses -> Condition records (deduplicate by name)
    for dx in items.diagnoses:
        existing = await db.execute(
            select(Condition).where(
                Condition.profile_id == profile_id,
                Condition.name == dx.condition,
            )
        )
        existing_cond = existing.scalar_one_or_none()
        if existing_cond:
            # Update ICD-10 if missing
            if dx.icd_10 and not existing_cond.icd_10:
                existing_cond.icd_10 = dx.icd_10
        else:
            cond = Condition(
                profile_id=profile_id,
                name=dx.condition,
                icd_10=dx.icd_10,
                status="active",
            )
            db.add(cond)
            counts["conditions"] += 1

    # Medication starts -> new Medication records
    for med in items.medication_starts:
        medication = Medication(
            profile_id=profile_id,
            name=med.name,
            dosage=med.strength,
            frequency=med.instructions,
            start_date=_parse_date_string(med.date),
        )
        db.add(medication)
        counts["medications_started"] += 1

    # Medication stops -> set end_date on matching Medication
    for med in items.medication_stops:
        clean_name = re.sub(r"\s*\(.*?\)", "", med.name).strip().lower()
        result = await db.execute(
            select(Medication).where(
                Medication.profile_id == profile_id,
                Medication.end_date.is_(None),
            )
        )
        for existing_med in result.scalars().all():
            existing_clean = re.sub(r"\s*\(.*?\)", "", existing_med.name).strip().lower()
            if existing_clean == clean_name or clean_name in existing_clean or existing_clean in clean_name:
                existing_med.end_date = _parse_date_string(med.date)
                counts["medications_stopped"] += 1
                break

    # Medication updates -> find existing, update dosage/instructions
    for med in items.medication_updates:
        clean_name = re.sub(r"\s*\(.*?\)", "", med.name).strip().lower()
        result = await db.execute(
            select(Medication).where(
                Medication.profile_id == profile_id,
                Medication.end_date.is_(None),
            )
        )
        for existing_med in result.scalars().all():
            existing_clean = re.sub(r"\s*\(.*?\)", "", existing_med.name).strip().lower()
            if existing_clean == clean_name or clean_name in existing_clean or existing_clean in clean_name:
                if med.strength:
                    existing_med.dosage = med.strength
                if med.instructions:
                    existing_med.frequency = med.instructions
                counts["medications_updated"] += 1
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

    # Lab orders
    for lab in items.lab_orders:
        order = LabOrder(
            profile_id=profile_id,
            document_id=document_id,
            test_name=lab.test,
            ordered_date=lab.ordered_date,
        )
        db.add(order)
        counts["lab_orders"] += 1

    # Referrals
    for ref in items.referrals:
        referral = Referral(
            profile_id=profile_id,
            document_id=document_id,
            specialty=ref.specialty,
            provider_name=ref.provider,
            reason=ref.reason,
        )
        db.add(referral)
        counts["referrals"] += 1

    # Follow-ups
    for fu in items.follow_ups:
        follow_up = FollowUp(
            profile_id=profile_id,
            document_id=document_id,
            description=fu.description,
            timeframe=fu.timeframe,
            target_date=fu.target_date,
        )
        db.add(follow_up)
        counts["follow_ups"] += 1

    await db.flush()

    logger.info(f"Applied items from document {doc.id}: {counts}")
    return {"status": "applied", "counts": counts}


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
