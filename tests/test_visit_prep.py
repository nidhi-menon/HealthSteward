"""Tests for visit preparation agent with mocked Claude API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response for visit preparation."""
    return {
        "questions": {
            "Medication Questions": [
                "How is Metformin working for blood sugar control?",
                "Should I be concerned about any side effects?",
            ],
            "Diabetes Management": [
                "What should my target blood sugar levels be?",
                "How often should I monitor my blood sugar?",
            ],
            "Lifestyle Questions": [
                "Are there dietary changes I should make?",
                "How much exercise is recommended for my condition?",
            ],
        },
        "context_summary": "Patient with Type 2 Diabetes, currently on Metformin, "
        "scheduled for a routine checkup with their endocrinologist.",
    }


@pytest.mark.asyncio
async def test_prepare_visit(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
    sample_condition_data,
    sample_medication_data,
    mock_claude_response,
):
    """Test visit preparation endpoint with mocked Claude API."""
    # Create a profile
    profile_response = await client.post("/api/profiles/", json=sample_profile_data)
    profile_id = profile_response.json()["id"]

    # Create condition and medication
    await client.post(
        f"/api/profiles/{profile_id}/conditions/", json=sample_condition_data
    )
    await client.post(
        f"/api/profiles/{profile_id}/medications/", json=sample_medication_data
    )

    # Create a doctor
    doctor_response = await client.post(
        f"/api/profiles/{profile_id}/doctors/", json=sample_doctor_data
    )
    doctor_id = doctor_response.json()["id"]

    # Create an appointment
    appointment_data = {**sample_appointment_data, "doctor_id": doctor_id}
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Mock the Claude API call
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"questions": {"General": ["Test question"]}, "context_summary": "Test summary"}')]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client

        # Request visit preparation
        response = await client.post(f"/api/visits/{appointment_id}/prepare")

    assert response.status_code == 200
    data = response.json()
    assert "generated_questions" in data
    assert "context_summary" in data
    assert data["appointment_id"] == appointment_id


@pytest.mark.asyncio
async def test_get_visit_prep(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test getting visit preparation after it's been generated."""
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
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Mock the Claude API call
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"questions": {"Test": ["Question 1"]}, "context_summary": "Summary"}')]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client

        # Generate visit preparation
        await client.post(f"/api/visits/{appointment_id}/prepare")

    # Get the visit preparation
    response = await client.get(f"/api/visits/{appointment_id}/prep")

    assert response.status_code == 200
    data = response.json()
    assert data["appointment_id"] == appointment_id
    assert "generated_questions" in data


@pytest.mark.asyncio
async def test_get_visit_prep_not_found(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test getting visit prep when it hasn't been generated yet."""
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
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Try to get visit prep without generating it first
    response = await client.get(f"/api/visits/{appointment_id}/prep")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_prepare_visit_with_additional_concerns(
    client: AsyncClient,
    sample_profile_data,
    sample_doctor_data,
    sample_appointment_data,
):
    """Test visit preparation with additional patient concerns."""
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
    appointment_response = await client.post(
        f"/api/profiles/{profile_id}/appointments/", json=appointment_data
    )
    appointment_id = appointment_response.json()["id"]

    # Mock the Claude API call
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"questions": {"Concerns": ["About fatigue"]}, "context_summary": "Patient concerned about fatigue"}')]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)

    with patch("src.agents.base.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client

        # Request visit preparation with additional concerns
        response = await client.post(
            f"/api/visits/{appointment_id}/prepare",
            json={"additional_concerns": "I've been feeling very tired lately"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "generated_questions" in data


@pytest.mark.asyncio
async def test_prepare_visit_appointment_not_found(client: AsyncClient):
    """Test visit preparation for non-existent appointment."""
    response = await client.post("/api/visits/non-existent-id/prepare")

    assert response.status_code == 404
