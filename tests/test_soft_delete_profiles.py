"""Tests for soft-deleted profiles with a 30-day recovery window (issue #50, DEC-027)."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.api.health_profile import SOFT_DELETE_RETENTION_DAYS
from src.data.models import Condition, HealthProfile


async def _set_deleted_at(db_session, profile_id: str, when: datetime) -> None:
    """Backdate a profile's deletion so the expiry window can be tested
    without waiting 30 days."""
    result = await db_session.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    profile = result.scalar_one()
    profile.deleted_at = when
    await db_session.commit()


# ============================================================================
# Soft delete
# ============================================================================


@pytest.mark.asyncio
async def test_delete_hides_profile_without_removing_the_row(
    client: AsyncClient, db_session, sample_profile_data
):
    """The core of issue #50: deletion becomes invisibility, not destruction."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    assert (await client.delete(f"/api/profiles/{profile_id}")).status_code == 204

    assert (await client.get(f"/api/profiles/{profile_id}")).status_code == 404
    assert (await client.get("/api/profiles/")).json() == []

    result = await db_session.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    row = result.scalar_one_or_none()
    assert row is not None, "row must survive a soft delete"
    assert row.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_leaves_child_data_untouched(
    client: AsyncClient, db_session, sample_profile_data, sample_condition_data
):
    """No cascade at soft-delete time — the caregiver-authored data that makes
    an accidental deletion unrecoverable has to still be there."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.post(f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data)

    await client.delete(f"/api/profiles/{profile_id}")

    result = await db_session.execute(
        select(Condition).where(Condition.profile_id == profile_id)
    )
    assert len(list(result.scalars().all())) == 1


@pytest.mark.asyncio
async def test_deleting_an_already_deleted_profile_is_404(
    client: AsyncClient, sample_profile_data
):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")

    assert (await client.delete(f"/api/profiles/{profile_id}")).status_code == 404


@pytest.mark.asyncio
async def test_soft_deleted_profile_cannot_be_updated(
    client: AsyncClient, sample_profile_data
):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")

    response = await client.patch(f"/api/profiles/{profile_id}", json={"name": "New Name"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_child_routes_404_for_a_soft_deleted_profile(
    client: AsyncClient, sample_profile_data, sample_condition_data, sample_doctor_data
):
    """A URL the user still had open after deleting must not keep working —
    otherwise the profile is only cosmetically gone."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")

    assert (await client.get(f"/api/profiles/{profile_id}/conditions/")).status_code == 404
    assert (
        await client.post(f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data)
    ).status_code == 404
    assert (
        await client.post(f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data)
    ).status_code == 404


# ============================================================================
# Recently deleted view + restore
# ============================================================================


@pytest.mark.asyncio
async def test_deleted_view_lists_profile_with_time_remaining(
    client: AsyncClient, sample_profile_data
):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")

    response = await client.get("/api/profiles/deleted")

    assert response.status_code == 200
    deleted = response.json()
    assert len(deleted) == 1
    assert deleted[0]["id"] == profile_id
    assert deleted[0]["name"] == sample_profile_data["name"]
    assert deleted[0]["deleted_at"] is not None
    # Just deleted, so the full window (minus the sub-second elapsed) remains.
    assert deleted[0]["days_remaining"] == SOFT_DELETE_RETENTION_DAYS - 1
    expires_at = datetime.fromisoformat(deleted[0]["expires_at"])
    deleted_at = datetime.fromisoformat(deleted[0]["deleted_at"])
    assert expires_at - deleted_at == timedelta(days=SOFT_DELETE_RETENTION_DAYS)


@pytest.mark.asyncio
async def test_deleted_view_excludes_live_profiles(client: AsyncClient, sample_profile_data):
    await client.post("/api/profiles/", json=sample_profile_data)

    assert (await client.get("/api/profiles/deleted")).json() == []


@pytest.mark.asyncio
async def test_deleted_route_is_not_shadowed_by_the_profile_id_route(client: AsyncClient):
    """`/profiles/deleted` must not be matched as `/profiles/{profile_id}` —
    route declaration order is load-bearing here."""
    response = await client.get("/api/profiles/deleted")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_restore_brings_the_profile_and_its_data_back(
    client: AsyncClient, sample_profile_data, sample_condition_data
):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.post(f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data)
    await client.delete(f"/api/profiles/{profile_id}")

    response = await client.post(f"/api/profiles/{profile_id}/restore")

    assert response.status_code == 200
    assert response.json()["id"] == profile_id
    assert (await client.get(f"/api/profiles/{profile_id}")).status_code == 200
    assert len((await client.get("/api/profiles/")).json()) == 1
    assert (await client.get("/api/profiles/deleted")).json() == []

    conditions = (await client.get(f"/api/profiles/{profile_id}/conditions/")).json()
    assert len(conditions) == 1
    assert conditions[0]["name"] == sample_condition_data["name"]


@pytest.mark.asyncio
async def test_restoring_a_live_profile_is_404(client: AsyncClient, sample_profile_data):
    """Nothing to restore — succeeding silently would hide a client bug."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    assert (await client.post(f"/api/profiles/{profile_id}/restore")).status_code == 404


@pytest.mark.asyncio
async def test_restoring_an_unknown_profile_is_404(client: AsyncClient):
    assert (await client.post("/api/profiles/does-not-exist/restore")).status_code == 404


# ============================================================================
# Lazy expiry cleanup
# ============================================================================


@pytest.mark.asyncio
async def test_expired_profile_is_hard_deleted_on_next_list(
    client: AsyncClient, db_session, sample_profile_data, sample_condition_data
):
    """After the window, the deferred cascading delete finally happens."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.post(f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data)
    await client.delete(f"/api/profiles/{profile_id}")
    await _set_deleted_at(
        db_session,
        profile_id,
        datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS + 1),
    )

    assert (await client.get("/api/profiles/")).json() == []

    profile_rows = await db_session.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    assert profile_rows.scalar_one_or_none() is None
    condition_rows = await db_session.execute(
        select(Condition).where(Condition.profile_id == profile_id)
    )
    assert list(condition_rows.scalars().all()) == [], "cascade must reach child rows"


@pytest.mark.asyncio
async def test_profile_inside_its_window_is_not_purged(
    client: AsyncClient, db_session, sample_profile_data
):
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")
    await _set_deleted_at(
        db_session,
        profile_id,
        datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS - 1),
    )

    await client.get("/api/profiles/")

    deleted = (await client.get("/api/profiles/deleted")).json()
    assert len(deleted) == 1
    assert deleted[0]["days_remaining"] == 0  # under a day left, floored at 0


@pytest.mark.asyncio
async def test_expired_profile_is_purged_when_the_deleted_view_is_opened(
    client: AsyncClient, db_session, sample_profile_data
):
    """Cleanup runs on the "Recently deleted" view too — otherwise a user who
    only ever opens that page would see profiles linger past their window."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")
    await _set_deleted_at(
        db_session,
        profile_id,
        datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS + 1),
    )

    assert (await client.get("/api/profiles/deleted")).json() == []

    rows = await db_session.execute(
        select(HealthProfile).where(HealthProfile.id == profile_id)
    )
    assert rows.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_past_window_profile_is_still_restorable_until_purged(
    client: AsyncClient, db_session, sample_profile_data
):
    """Deliberate: restore doesn't purge first, so a restore click can never
    destroy the profile it was trying to bring back."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.delete(f"/api/profiles/{profile_id}")
    await _set_deleted_at(
        db_session,
        profile_id,
        datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS + 1),
    )

    assert (await client.post(f"/api/profiles/{profile_id}/restore")).status_code == 200
    assert (await client.get(f"/api/profiles/{profile_id}")).status_code == 200


@pytest.mark.asyncio
async def test_purge_leaves_live_profiles_alone(
    client: AsyncClient, db_session, sample_profile_data
):
    """A cleanup pass that can reach a live profile is the worst possible bug
    in this feature, so it gets its own test."""
    keep_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    drop_id = (
        await client.post("/api/profiles/", json={**sample_profile_data, "name": "Other"})
    ).json()["id"]
    await client.delete(f"/api/profiles/{drop_id}")
    await _set_deleted_at(
        db_session,
        drop_id,
        datetime.utcnow() - timedelta(days=SOFT_DELETE_RETENTION_DAYS + 1),
    )

    listed = (await client.get("/api/profiles/")).json()

    assert [p["id"] for p in listed] == [keep_id]
    rows = await db_session.execute(select(HealthProfile))
    assert [p.id for p in rows.scalars().all()] == [keep_id]
