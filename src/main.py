"""HealthSteward main application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api import action_items, appointments, conditions, doctors, documents, health_profile, medications, settings as settings_api, visits
from src.config import get_settings
from src.data.database import init_db
from src.utils.logging import setup_logging

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    # Startup
    setup_logging()
    logger.info("Starting HealthSteward...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Ensure scan directories exist
    from pathlib import Path
    Path(settings.avs_scan_path).mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    logger.info("Shutting down HealthSteward...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Privacy-first AI health coordination system",
    version=settings.app_version,
    lifespan=lifespan,
)

# Add CORS middleware (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adjust for your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_profile.router)
app.include_router(conditions.router)
app.include_router(medications.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(documents.router)
app.include_router(visits.router)
app.include_router(action_items.router)
app.include_router(settings_api.router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "ok",
        "database": "connected",
        "ai_agent": "configured" if settings.anthropic_api_key else "not_configured",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
    )
