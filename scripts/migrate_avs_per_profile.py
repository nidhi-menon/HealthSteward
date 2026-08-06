"""One-time migration: partition data/avs/ into per-profile subfolders.

Issue #49 / DEC-030 moved AVS storage from a single flat `data/avs/` folder
to `data/avs/<profile_id>/`. Existing installs need their already-scanned
files moved into the right subfolder once.

For each PDF directly under the scan root:
  - If a `Document` row references it (matched by original_filename +
    file_size_bytes, the same key `scan_documents`/`parse_file` already use),
    move it to `data/avs/<that document's profile_id>/` and update
    `Document.file_path` to match.
  - If no `Document` row references it (today's "unclaimed/new" files), move
    it to `data/avs/_unassigned/` instead of guessing which profile it
    belongs to.

Safe to re-run: files already under a subfolder (profile id or
`_unassigned`) are left alone, and a destination collision is skipped with a
warning rather than overwritten.

Usage:
    python -m scripts.migrate_avs_per_profile
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.data.models import Document

UNASSIGNED_DIRNAME = "_unassigned"


async def migrate(db: AsyncSession | None = None) -> None:
    """Run the migration.

    `db` is optional and exists so tests can pass a session bound to their
    in-memory test database — the default (`None`) opens a real session
    against the app's configured database, which is what running this as a
    script does.
    """
    settings = get_settings()
    scan_root = Path(settings.avs_scan_path)
    scan_root.mkdir(parents=True, exist_ok=True)

    # Only files directly under the root are "unmigrated" — anything already
    # inside a subfolder was either migrated by a previous run or written
    # there by the new per-profile scan/upload logic.
    top_level_pdfs = [
        p for p in scan_root.iterdir()
        if p.is_file() and p.name.lower().endswith(".pdf")
    ]

    if not top_level_pdfs:
        logger.info("No flat top-level AVS files found — nothing to migrate.")
        return

    owns_session = db is None
    if owns_session:
        from src.data.database import AsyncSessionLocal
        db = AsyncSessionLocal()

    try:
        result = await db.execute(select(Document))
        docs_by_key = {
            (doc.original_filename, doc.file_size_bytes): doc
            for doc in result.scalars().all()
        }

        moved, unassigned, skipped = 0, 0, 0
        for entry in top_level_pdfs:
            file_size = entry.stat().st_size
            doc = docs_by_key.get((entry.name, file_size))

            if doc:
                dest_dir = scan_root / doc.profile_id
            else:
                dest_dir = scan_root / UNASSIGNED_DIRNAME

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / entry.name

            if dest_path.exists():
                logger.warning(
                    f"Skipping {entry.name}: destination {dest_path} already exists."
                )
                skipped += 1
                continue

            shutil.move(str(entry), str(dest_path))

            if doc:
                doc.file_path = str(dest_path)
                moved += 1
            else:
                unassigned += 1

        await db.commit()
    finally:
        if owns_session:
            await db.close()

    logger.info(
        f"AVS migration complete: {moved} file(s) moved into profile "
        f"subfolders, {unassigned} unclaimed file(s) moved into "
        f"'{UNASSIGNED_DIRNAME}/', {skipped} skipped due to name collision."
    )


if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except Exception as exc:  # pragma: no cover - operator-facing script
        logger.error(f"AVS migration failed: {exc}")
        sys.exit(1)
