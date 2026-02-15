"""Async SQLAlchemy database configuration."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.data.models import Base

settings = get_settings()

# Ensure data directory exists for SQLite
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database by creating all tables and run migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrations for existing tables (SQLite create_all doesn't ALTER)
        await _run_migrations(conn)


async def _run_migrations(conn) -> None:
    """Run schema migrations that create_all can't handle."""
    from sqlalchemy import text

    # Migration: make appointments.doctor_id nullable
    # SQLite doesn't support ALTER COLUMN, so we recreate the table
    try:
        result = await conn.execute(text("PRAGMA table_info(appointments)"))
        columns = result.fetchall()
        doctor_col = next((c for c in columns if c[1] == "doctor_id"), None)
        if doctor_col and doctor_col[3] == 1:  # notnull=1, needs migration
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS appointments_new (
                    id VARCHAR(36) PRIMARY KEY,
                    profile_id VARCHAR(36) NOT NULL REFERENCES health_profiles(id),
                    doctor_id VARCHAR(36) REFERENCES doctors(id),
                    scheduled_date DATETIME NOT NULL,
                    purpose TEXT,
                    status VARCHAR(50) NOT NULL DEFAULT 'scheduled',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    prep_notes TEXT,
                    visit_notes TEXT,
                    visit_notes_updated_at DATETIME
                )
            """))
            await conn.execute(text("""
                INSERT INTO appointments_new
                SELECT id, profile_id, doctor_id, scheduled_date, purpose,
                       status, created_at, updated_at, prep_notes,
                       visit_notes, visit_notes_updated_at
                FROM appointments
            """))
            await conn.execute(text("DROP TABLE appointments"))
            await conn.execute(text("ALTER TABLE appointments_new RENAME TO appointments"))
    except Exception:
        pass  # Table might not exist yet, that's fine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
