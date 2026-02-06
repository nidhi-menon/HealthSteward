"""Pytest fixtures and configuration for HealthSteward tests."""

import os
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.data.database import get_db
from src.data.models import Base

# Override database URL for tests (in-memory SQLite)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with fresh session per request."""
    from src.main import app

    async_session = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_profile_data():
    """Sample health profile data for testing."""
    return {
        "name": "John Doe",
        "date_of_birth": "1985-06-15",
        "blood_type": "O+",
        "allergies": "Penicillin, Peanuts",
        "emergency_contact_name": "Jane Doe",
        "emergency_contact_phone": "+1-555-123-4567",
    }


@pytest.fixture
def sample_condition_data():
    """Sample condition data for testing."""
    return {
        "name": "Type 2 Diabetes",
        "diagnosed_date": "2020-03-10",
        "severity": "moderate",
        "status": "active",
        "notes": "Managing with diet and medication",
    }


@pytest.fixture
def sample_medication_data():
    """Sample medication data for testing."""
    return {
        "name": "Metformin",
        "dosage": "500mg",
        "frequency": "twice daily",
        "prescribing_doctor": "Dr. Smith",
        "start_date": "2020-04-01",
        "purpose": "Blood sugar control",
        "side_effects": "Occasional nausea",
    }


@pytest.fixture
def sample_doctor_data():
    """Sample doctor data for testing."""
    return {
        "name": "Dr. Sarah Johnson",
        "specialty": "Endocrinology",
        "clinic": "City Medical Center",
        "phone": "+1-555-987-6543",
        "email": "dr.johnson@citymedical.com",
        "notes": "Excellent with diabetes management",
    }


@pytest.fixture
def sample_appointment_data():
    """Sample appointment data for testing (requires doctor_id)."""
    return {
        "scheduled_date": "2025-03-15T10:00:00",
        "purpose": "Quarterly diabetes checkup",
        "status": "scheduled",
        "notes": "Bring blood sugar logs",
    }
