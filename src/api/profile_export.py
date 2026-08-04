"""API route for exporting a profile's data as a structured JSON document (issue #93).

HealthSteward is the only copy of a user's health history, on a single machine
that probably isn't backed up — "your data never leaves your machine" cuts both
ways. This is the export half of that: one endpoint producing one file the user
saves wherever they keep backups.

Three scoping calls, all confirmed by the repo owner on issue #93:
per-profile rather than one-click-everything; plaintext rather than encrypted
(there is no encryption-at-rest mechanism to hang it off — #92 — and encrypting
the export alone would be a partial, misleading guarantee); and a local file the
user manages themselves, with no cloud destination.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
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
    HealthProfile,
    LabOrder,
    Medication,
    NudgeState,
    Referral,
    Vitals,
    VisitPrep,
)

router = APIRouter(prefix="/api/profiles", tags=["Health Profiles"])

# Bumped when the document's shape changes in a way an importer would need to
# know about. Present from v1 so a future importer never has to guess which
# shape it's looking at — the one thing that is genuinely expensive to add
# retroactively, since files already on disk won't have it.
EXPORT_FORMAT_VERSION = 1

# Every profile-scoped table, exported in full — including primary keys and
# foreign keys, since the relationships between records (which appointment was
# with which doctor, which lab order came from which document) are part of the
# data and can't be reconstructed once they're gone. Nothing is redacted:
# DEC-006's anonymization exists to protect data crossing a boundary to an
# external LLM, and this file never leaves the user's own machine.
_EXPORTED_TABLES = (
    ("conditions", Condition),
    ("medications", Medication),
    ("doctors", Doctor),
    ("appointments", Appointment),
    ("documents", Document),
    ("vitals", Vitals),
    ("lab_orders", LabOrder),
    ("referrals", Referral),
    ("follow_ups", FollowUp),
    ("nudge_states", NudgeState),
)


def _serialize(row: Any) -> dict[str, Any]:
    """Turn an ORM row into a plain dict of its own columns.

    Driven off the mapper rather than a hand-written field list so a column
    added to a model later is exported automatically. The failure mode of the
    alternative is silent and bad: a new field simply wouldn't be in anyone's
    backup, and nobody would find out until a restore.
    """
    return {
        column.key: getattr(row, column.key)
        for column in row.__mapper__.column_attrs
    }


@router.get("/{profile_id}/export")
async def export_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export everything under a profile as a single JSON document.

    Returned as a file download (`Content-Disposition: attachment`) rather than
    a plain JSON body — the point is a file the user puts somewhere safe, so
    the browser should save it, not render it.

    **Documents are exported as metadata only.** The uploaded AVS PDFs
    themselves stay on disk where they are; `file_path` records where they
    were. A backup restored on a different machine will have the parsed
    contents of every document (vitals, labs, referrals, follow-ups, and the
    raw parse result) but not the source PDFs. That is a real limitation of
    this export, called out in `documents_note` inside the file itself so
    someone reading a backup years later doesn't have to infer it.
    """
    settings = get_settings()

    profile_result = await db.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile with id {profile_id} not found",
        )

    document: dict[str, Any] = {
        "export_format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app_version": settings.app_version,
        "documents_note": (
            "Document records are metadata and parsed contents only — the "
            "uploaded PDF files themselves are not included in this export."
        ),
        "profile": _serialize(profile),
    }

    for key, model in _EXPORTED_TABLES:
        result = await db.execute(
            select(model).where(model.profile_id == profile_id)
        )
        document[key] = [_serialize(row) for row in result.scalars().all()]

    # VisitPrep hangs off appointments, not the profile, so it needs the
    # appointment ids rather than a profile_id filter. Included because a prep
    # may have been hand-edited by the patient (issue #14) — that's authored
    # content, not regenerable output.
    appointment_ids = [row["id"] for row in document["appointments"]]
    if appointment_ids:
        prep_result = await db.execute(
            select(VisitPrep).where(VisitPrep.appointment_id.in_(appointment_ids))
        )
        document["visit_preps"] = [_serialize(row) for row in prep_result.scalars().all()]
    else:
        document["visit_preps"] = []

    # JSONResponse rather than returning the dict directly, so the
    # Content-Disposition header can be attached. jsonable_encoder handles the
    # date/datetime values the ORM rows carry.
    filename = _export_filename(profile.name, profile_id)
    return JSONResponse(
        content=jsonable_encoder(document),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_filename(profile_name: str, profile_id: str) -> str:
    """Build a filename that's recognizable a year later and safe on any OS.

    Falls back to the profile id if the name has no characters that survive
    sanitizing (e.g. a name written entirely in a script this filter strips) —
    an unnamed download is worse than an opaque one.
    """
    safe_name = "".join(
        char if char.isalnum() or char in "-_" else "-" for char in profile_name
    ).strip("-")
    # Collapse runs of dashes left behind by stripped characters.
    while "--" in safe_name:
        safe_name = safe_name.replace("--", "-")
    stem = safe_name.lower() or profile_id
    today = datetime.now(timezone.utc).date().isoformat()
    return f"healthsteward-{stem}-{today}.json"
