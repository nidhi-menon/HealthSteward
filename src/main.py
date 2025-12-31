"""
HealthSteward main application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="HealthSteward",
    description="Privacy-first AI health coordination system",
    version="0.1.0"
)

# Add CORS middleware (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adjust for your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "HealthSteward",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "ok",
        "services": {
            "api": "running",
            "database": "not_configured",
            "ai_agent": "not_configured"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
