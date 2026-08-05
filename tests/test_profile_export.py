"""Tests for the per-profile JSON export (issue #93)."""

import pytest
from httpx import AsyncClient

from src.api.profile_export import EXPORT_FORMAT_VERSION, _export_filename


@pytest.mark.asyncio
async def test_export_includes_every_profile_scoped_table(
    client: AsyncClient,
    sample_profile_data,
    sample_condition_data,
    sample_medication_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """The point of a backup is that nothing is missing — so this asserts on
    the presence of every table key, not just the ones with data in them."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    await client.post(f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data)
    await client.post(f"/api/profiles/{profile_id}/medications/", json=sample_medication_data)
    doctor_id = (
        await client.post(f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data)
    ).json()["id"]
    await client.post(
        f"/api/profiles/{profile_id}/appointments/",
        json={**sample_appointment_data, "doctor_id": doctor_id},
    )

    response = await client.get(f"/api/profiles/{profile_id}/export")

    assert response.status_code == 200
    export = response.json()

    for key in (
        "conditions", "medications", "doctors", "appointments", "documents",
        "vitals", "lab_orders", "referrals", "follow_ups", "nudge_states",
        "visit_preps",
    ):
        assert key in export, f"export is missing the {key} table"

    assert export["export_format_version"] == EXPORT_FORMAT_VERSION
    assert export["exported_at"]
    assert export["profile"]["id"] == profile_id
    assert export["profile"]["name"] == sample_profile_data["name"]
    assert export["profile"]["allergies"] == sample_profile_data["allergies"]
    assert len(export["conditions"]) == 1
    assert export["conditions"][0]["name"] == sample_condition_data["name"]
    assert len(export["medications"]) == 1
    assert len(export["doctors"]) == 1
    assert len(export["appointments"]) == 1


@pytest.mark.asyncio
async def test_export_preserves_ids_and_foreign_keys(
    client: AsyncClient, sample_profile_data, sample_doctor_data, sample_appointment_data
):
    """Which appointment was with which doctor is part of the data — an export
    that drops the keys can't be restored into anything faithful."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    doctor_id = (
        await client.post(f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data)
    ).json()["id"]
    appointment_id = (
        await client.post(
            f"/api/profiles/{profile_id}/appointments/",
            json={**sample_appointment_data, "doctor_id": doctor_id},
        )
    ).json()["id"]

    export = (await client.get(f"/api/profiles/{profile_id}/export")).json()

    assert export["doctors"][0]["id"] == doctor_id
    assert export["appointments"][0]["id"] == appointment_id
    assert export["appointments"][0]["doctor_id"] == doctor_id
    assert export["appointments"][0]["profile_id"] == profile_id


@pytest.mark.asyncio
async def test_export_is_scoped_to_one_profile(
    client: AsyncClient, sample_profile_data, sample_condition_data
):
    """Per-profile, not everything — another profile's data must not leak in."""
    first_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    second_id = (
        await client.post("/api/profiles/", json={**sample_profile_data, "name": "Other Person"})
    ).json()["id"]
    await client.post(f"/api/profiles/{second_id}/conditions/", json=sample_condition_data)

    export = (await client.get(f"/api/profiles/{first_id}/export")).json()

    assert export["profile"]["id"] == first_id
    assert export["conditions"] == []


@pytest.mark.asyncio
async def test_export_is_served_as_a_file_download(client: AsyncClient, sample_profile_data):
    """The deliverable is a file the user puts somewhere safe, so the browser
    should save it rather than render it."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    response = await client.get(f"/api/profiles/{profile_id}/export")

    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=")
    assert disposition.endswith('.json"')
    assert "healthsteward-john-doe-" in disposition


@pytest.mark.asyncio
async def test_export_of_an_empty_profile_is_still_a_complete_document(
    client: AsyncClient, sample_profile_data
):
    """A profile with nothing under it exports empty lists, not missing keys —
    an importer shouldn't have to special-case it."""
    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]

    export = (await client.get(f"/api/profiles/{profile_id}/export")).json()

    assert export["conditions"] == []
    assert export["appointments"] == []
    assert export["visit_preps"] == []
    assert export["profile"]["id"] == profile_id


@pytest.mark.asyncio
async def test_export_of_unknown_profile_is_404(client: AsyncClient):
    assert (await client.get("/api/profiles/does-not-exist/export")).status_code == 404


@pytest.mark.asyncio
async def test_export_includes_a_hand_edited_visit_prep(
    client: AsyncClient, db_session, sample_profile_data, sample_doctor_data,
    sample_appointment_data,
):
    """A prep the patient edited by hand (issue #14) is authored content, not
    regenerable output, so it has to survive a backup."""
    from src.data.models import VisitPrep

    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    doctor_id = (
        await client.post(f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data)
    ).json()["id"]
    appointment_id = (
        await client.post(
            f"/api/profiles/{profile_id}/appointments/",
            json={**sample_appointment_data, "doctor_id": doctor_id},
        )
    ).json()["id"]

    db_session.add(
        VisitPrep(
            appointment_id=appointment_id,
            generated_questions={"Medication Review": ["A question I wrote myself"]},
            context_summary="My own summary",
        )
    )
    await db_session.commit()

    export = (await client.get(f"/api/profiles/{profile_id}/export")).json()

    assert len(export["visit_preps"]) == 1
    prep = export["visit_preps"][0]
    assert prep["appointment_id"] == appointment_id
    assert prep["generated_questions"] == {"Medication Review": ["A question I wrote myself"]}
    assert prep["context_summary"] == "My own summary"


@pytest.mark.asyncio
async def test_export_carries_document_metadata_and_says_files_are_excluded(
    client: AsyncClient, db_session, sample_profile_data
):
    """Documents export as metadata + parsed contents. The source PDFs aren't
    included, and the file says so rather than leaving it to be inferred."""
    from src.data.models import Document

    profile_id = (await client.post("/api/profiles/", json=sample_profile_data)).json()["id"]
    db_session.add(
        Document(
            profile_id=profile_id,
            original_filename="avs-2026-01-15.pdf",
            file_path="/data/avs/avs-2026-01-15.pdf",
            file_size_bytes=12345,
            parse_status="completed",
            raw_parse_result={"vitals": {"weight": "150 lb"}},
        )
    )
    await db_session.commit()

    export = (await client.get(f"/api/profiles/{profile_id}/export")).json()

    assert len(export["documents"]) == 1
    doc = export["documents"][0]
    assert doc["original_filename"] == "avs-2026-01-15.pdf"
    assert doc["file_path"] == "/data/avs/avs-2026-01-15.pdf"
    assert doc["raw_parse_result"] == {"vitals": {"weight": "150 lb"}}
    assert "not included" in export["documents_note"]


def test_export_filename_falls_back_to_the_profile_id():
    """A name with nothing filename-safe in it would otherwise produce
    "healthsteward--2026-08-04.json"."""
    assert _export_filename("!!!", "abc-123").startswith("healthsteward-abc-123-")


def test_export_filename_collapses_separator_runs():
    assert _export_filename("Ann   Marie O'Brien", "id").startswith(
        "healthsteward-ann-marie-o-brien-"
    )
