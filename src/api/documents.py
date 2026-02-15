"""Document upload, parsing, and review API endpoints."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
)

router = APIRouter(prefix="/api/profiles/{profile_id}/documents", tags=["documents"])

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/", response_model=DocumentResponse, status_code=201)
async def upload_document(
    profile_id: str,
    file: UploadFile = File(...),
    appointment_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF document for a profile."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Read file content
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # Create document record to get ID
    doc = Document(
        profile_id=profile_id,
        appointment_id=appointment_id,
        original_filename=file.filename,
        file_path="",  # will update after save
        file_size_bytes=len(content),
        parse_status="pending",
    )
    db.add(doc)
    await db.flush()  # get the ID

    # Save file to disk
    settings = get_settings()
    doc_dir = Path(settings.documents_base_path) / profile_id / doc.id
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / file.filename
    file_path.write_bytes(content)

    doc.file_path = str(file_path)
    await db.flush()

    logger.info(f"Uploaded document {doc.id}: {file.filename} ({len(content)} bytes)")
    return doc


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all documents for a profile."""
    result = await db.execute(
        select(Document)
        .where(Document.profile_id == profile_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


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


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    profile_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its file on disk."""
    doc = await db.get(Document, document_id)
    if not doc or doc.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete file from disk
    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()
        # Clean up empty directories
        parent = file_path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

    await db.delete(doc)


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
