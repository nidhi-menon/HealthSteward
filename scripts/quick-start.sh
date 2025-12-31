#!/bin/bash
set -e

echo "=========================================="
echo "HealthSteward Quick Start"
echo "=========================================="
echo ""

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "Error: Conda is not installed"
    echo "Please install Miniconda from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Warning: Docker is not installed"
    echo "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    echo "You can still use conda for local development"
    echo ""
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "IMPORTANT: Edit .env and add your Anthropic API key!"
    echo "  Get your key from: https://console.anthropic.com/"
    echo ""
    read -p "Press Enter after you've added your API key to .env..."
else
    echo "✓ .env file already exists"
fi

# Check if environment exists
if conda env list | grep -q "^healthsteward "; then
    echo "✓ Conda environment 'healthsteward' already exists"
else
    echo "Creating conda environment..."
    conda env create -f environment.yml
    echo "✓ Conda environment created"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To start developing:"
echo "  1. Activate the environment:"
echo "     conda activate healthsteward"
echo ""
echo "  2. Run the development server:"
echo "     make run"
echo "     (or: python -m uvicorn src.main:app --reload)"
echo ""
echo "  3. Visit: http://localhost:8000/health"
echo ""
echo "To use Docker instead:"
echo "  make docker-up"
echo ""
echo "For more commands:"
echo "  make help"
echo ""
