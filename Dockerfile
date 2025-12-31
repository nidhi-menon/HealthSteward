# Multi-stage build for HealthSteward
# Stage 1: Base image with Miniconda
FROM continuumio/miniconda3:latest AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy environment file
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml && \
    conda clean -afy

# Make RUN commands use the new environment
SHELL ["conda", "run", "-n", "healthsteward", "/bin/bash", "-c"]

# Stage 2: Development image
FROM base AS development

# Copy application code
COPY . .

# Expose ports for FastAPI (8000) and Jupyter (8888)
EXPOSE 8000 8888

# Default command for development (can be overridden)
CMD ["conda", "run", "--no-capture-output", "-n", "healthsteward", "python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Production image (optimized)
FROM base AS production

# Copy only necessary application files
COPY src/ ./src/
COPY models/ ./models/
COPY config/ ./config/

# Create data directories with proper permissions
RUN mkdir -p /app/data/health_records /app/data/models /app/logs && \
    chmod 700 /app/data/health_records

# Run as non-root user for security
RUN useradd -m -u 1000 healthsteward && \
    chown -R healthsteward:healthsteward /app
USER healthsteward

EXPOSE 8000

# Production command
CMD ["conda", "run", "--no-capture-output", "-n", "healthsteward", "python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
