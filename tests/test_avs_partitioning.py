"""Tests for per-profile AVS file partitioning (issue #49, DEC-030)."""

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.api.health_profile import SOFT_DELETE_RETENTION_DAYS, purge_expired_profiles
from src.data.models import Document, HealthProfile
from scripts.migrate_avs_per_profile import migrate


def _fake_settings(avs_dir: Path):
    return SimpleNamespace(avs_scan_path=str(avs_dir))


@pytest.fixture
def avs_dir(tmp_path, monkeypatch):
    """Point both documents.py and health_profile.py at an isolated AVS root."""
    d = tmp_path / "avs"
    d.mkdir()
    settings = _fake_settings(d)

    import src.api.documents as documents_mod
    import src.api.health_profile as health_profile_mod
    import scripts.migrate_avs_per_profile as migrate_mod

    monkeypatch.setattr(documents_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(health_profile_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(migrate_mod, "get_settings", lambda: settings)
    return d


async def _set_deleted_at(db_session, profile_id: str, when: datetime) -> None:
    result = await db_session.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    profile = result.scalar_one()
    profile.deleted_at = when
    await db_session.commit()


# ============================================================================
# Scan isolation
# ============================================================================


@pytest.mark.asyncio
async def test_scan_only_returns_files_in_the_requesting_profiles_subfolder(
    client: AsyncClient, avs_dir, sample_profile_data
):
    profile_a = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    profile_b = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    (avs_dir / profile_a).mkdir()
    (avs_dir / profile_a / "a-visit.pdf").write_bytes(b"%PDF-a")

    resp_a = await client.get(f"/api/profiles/{profile_a}/documents/scan")
    assert resp_a.status_code == 200
    filenames_a = [f["filename"] for f in resp_a.json()]
    assert "a-visit.pdf" in filenames_a

    resp_b = await client.get(f"/api/profiles/{profile_b}/documents/scan")
    assert resp_b.status_code == 200
    filenames_b = [f["filename"] for f in resp_b.json()]
    assert "a-visit.pdf" not in filenames_b
    assert filenames_b == []

    # Scanning also creates the requesting profile's own subfolder.
    assert (avs_dir / profile_b).is_dir()


# ============================================================================
# Migration script
# ============================================================================


@pytest.mark.asyncio
async def test_migration_partitions_claimed_and_unassigned_files(
    db_session, avs_dir, sample_profile_data
):
    profile = HealthProfile(**{
        **sample_profile_data,
        "date_of_birth": datetime.strptime(
            sample_profile_data["date_of_birth"], "%Y-%m-%d"
        ).date(),
    })
    db_session.add(profile)
    await db_session.flush()

    claimed_path = avs_dir / "claimed.pdf"
    claimed_path.write_bytes(b"%PDF-claimed")
    unclaimed_path = avs_dir / "unclaimed.pdf"
    unclaimed_path.write_bytes(b"%PDF-unclaimed")

    doc = Document(
        profile_id=profile.id,
        original_filename="claimed.pdf",
        file_path=str(claimed_path),
        file_size_bytes=claimed_path.stat().st_size,
        parse_status="completed",
    )
    db_session.add(doc)
    await db_session.commit()

    await migrate(db_session)

    assert not claimed_path.exists()
    assert not unclaimed_path.exists()
    assert (avs_dir / profile.id / "claimed.pdf").exists()
    assert (avs_dir / "_unassigned" / "unclaimed.pdf").exists()

    result = await db_session.execute(
        select(Document).where(Document.id == doc.id)
    )
    refreshed = result.scalar_one()
    assert refreshed.file_path == str(avs_dir / profile.id / "claimed.pdf")


@pytest.mark.asyncio
async def test_migration_is_idempotent(db_session, avs_dir, sample_profile_data):
    profile = HealthProfile(**{
        **sample_profile_data,
        "date_of_birth": datetime.strptime(
            sample_profile_data["date_of_birth"], "%Y-%m-%d"
        ).date(),
    })
    db_session.add(profile)
    await db_session.flush()

    path = avs_dir / "solo.pdf"
    path.write_bytes(b"%PDF-solo")
    await db_session.commit()

    await migrate(db_session)
    assert (avs_dir / "_unassigned" / "solo.pdf").exists()

    # Re-running must not error or move anything further — the file is no
    # longer at the top level, so there's nothing left to migrate.
    await migrate(db_session)
    assert (avs_dir / "_unassigned" / "solo.pdf").exists()


# ============================================================================
# Opt-in purge-time deletion
# ============================================================================


@pytest.mark.asyncio
async def test_avs_files_not_deleted_at_soft_delete_time(
    client: AsyncClient, avs_dir, sample_profile_data
):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    profile_dir = avs_dir / profile_id
    profile_dir.mkdir()
    (profile_dir / "visit.pdf").write_bytes(b"%PDF")

    resp = await client.delete(
        f"/api/profiles/{profile_id}?purge_avs_files_on_expiry=true"
    )
    assert resp.status_code == 204

    # Soft-delete only, not yet expired: files must still be there.
    assert (profile_dir / "visit.pdf").exists()


@pytest.mark.asyncio
async def test_purge_deletes_files_only_when_flag_set_and_profile_expires(
    client: AsyncClient, db_session, avs_dir, sample_profile_data
):
    # Profile with the opt-in flag set.
    purge_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    purge_dir = avs_dir / purge_id
    purge_dir.mkdir()
    (purge_dir / "visit.pdf").write_bytes(b"%PDF")
    await client.delete(f"/api/profiles/{purge_id}?purge_avs_files_on_expiry=true")

    # Profile without the opt-in flag (default).
    keep_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    keep_dir = avs_dir / keep_id
    keep_dir.mkdir()
    (keep_dir / "visit.pdf").write_bytes(b"%PDF")
    await client.delete(f"/api/profiles/{keep_id}")

    old_enough = datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS + 1)
    await _set_deleted_at(db_session, purge_id, old_enough)
    await _set_deleted_at(db_session, keep_id, old_enough)

    purged_count = await purge_expired_profiles(db_session)
    await db_session.commit()

    assert purged_count == 2
    assert not purge_dir.exists()
    assert keep_dir.exists()
    assert (keep_dir / "visit.pdf").exists()


@pytest.mark.asyncio
async def test_restored_profile_keeps_its_files_even_with_purge_flag_set(
    client: AsyncClient, db_session, avs_dir, sample_profile_data
):
    """A profile restored before expiry must find its files untouched,
    regardless of the opt-in flag it was soft-deleted with."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    profile_dir = avs_dir / profile_id
    profile_dir.mkdir()
    (profile_dir / "visit.pdf").write_bytes(b"%PDF")

    await client.delete(f"/api/profiles/{profile_id}?purge_avs_files_on_expiry=true")

    # Restore well before the recovery window would expire.
    restore_resp = await client.post(f"/api/profiles/{profile_id}/restore")
    assert restore_resp.status_code == 200

    # Even if purge_expired_profiles runs afterward, a live (restored)
    # profile is never in its query, so nothing should be touched.
    purged_count = await purge_expired_profiles(db_session)
    await db_session.commit()

    assert purged_count == 0
    assert (profile_dir / "visit.pdf").exists()
