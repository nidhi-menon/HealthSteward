"""Tests for health profile CRUD operations."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_profile(client: AsyncClient, sample_profile_data):
    """Test creating a new health profile."""
    response = await client.post("/api/profiles/", json=sample_profile_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_profile_data["name"]
    assert data["blood_type"] == sample_profile_data["blood_type"]
    assert data["allergies"] == sample_profile_data["allergies"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_profile(client: AsyncClient, sample_profile_data):
    """Test getting a health profile by ID."""
    # Create a profile first
    create_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = create_response.json()["id"]

    # Get the profile
    response = await client.get(f"/api/profiles/{profile_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == profile_id
    assert data["name"] == sample_profile_data["name"]


@pytest.mark.asyncio
async def test_get_profile_not_found(client: AsyncClient):
    """Test getting a non-existent profile."""
    response = await client.get("/api/profiles/non-existent-id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_profiles(client: AsyncClient, sample_profile_data):
    """Test listing all health profiles."""
    # Create two profiles
    await client.post("/api/profiles/", json=sample_profile_data)
    sample_profile_data["name"] = "Jane Smith"
    await client.post("/api/profiles/", json=sample_profile_data)

    # List all profiles
    response = await client.get("/api/profiles/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, sample_profile_data):
    """Test updating a health profile."""
    # Create a profile
    create_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = create_response.json()["id"]

    # Update the profile
    update_data = {"name": "John Updated", "blood_type": "A-"}
    response = await client.patch(f"/api/profiles/{profile_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Updated"
    assert data["blood_type"] == "A-"
    # Original allergies should be unchanged
    assert data["allergies"] == sample_profile_data["allergies"]


@pytest.mark.asyncio
async def test_delete_profile(client: AsyncClient, sample_profile_data):
    """Test deleting a health profile."""
    # Create a profile
    create_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = create_response.json()["id"]

    # Delete the profile
    response = await client.delete(f"/api/profiles/{profile_id}")
    assert response.status_code == 204

    # Verify it's deleted
    get_response = await client.get(f"/api/profiles/{profile_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_condition_for_profile(
    client: AsyncClient, sample_profile_data, sample_condition_data
):
    """Test creating a condition for a health profile."""
    # Create a profile
    create_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = create_response.json()["id"]

    # Create a condition
    response = await client.post(
        f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_condition_data["name"]
    assert data["profile_id"] == profile_id


@pytest.mark.asyncio
async def test_create_medication_for_profile(
    client: AsyncClient, sample_profile_data, sample_medication_data
):
    """Test creating a medication for a health profile."""
    # Create a profile
    create_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = create_response.json()["id"]

    # Create a medication
    response = await client.post(
        f"/api/profiles/{profile_id}/medications/", json=sample_medication_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_medication_data["name"]
    assert data["profile_id"] == profile_id


@pytest.mark.asyncio
async def test_create_doctor_for_profile(
    client: AsyncClient, sample_profile_data, sample_doctor_data
):
    """Test creating a doctor for a health profile."""
    # Create a profile
    create_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = create_response.json()["id"]

    # Create a doctor
    response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_doctor_data["name"]
    assert data["specialty"] == sample_doctor_data["specialty"]
    assert data["profile_id"] == profile_id


@pytest.mark.asyncio
async def test_create_appointment_for_profile(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test creating an appointment for a health profile."""
    # Create a profile
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Create a doctor
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    # Create an appointment
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["purpose"] == sample_appointment_data["purpose"]
    assert data["doctor_id"] == doctor_id
    assert data["profile_id"] == profile_id
