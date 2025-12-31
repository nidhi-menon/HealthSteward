.PHONY: help setup conda-create conda-activate docker-build docker-up docker-down docker-logs test format lint clean

help:
	@echo "HealthSteward - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Initial setup (copy .env, create conda env)"
	@echo "  make conda-create   - Create conda environment"
	@echo "  make conda-update   - Update conda environment"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-up      - Start all services"
	@echo "  make docker-down    - Stop all services"
	@echo "  make docker-logs    - View logs"
	@echo "  make docker-clean   - Remove all containers and volumes"
	@echo ""
	@echo "Development:"
	@echo "  make run            - Run app locally"
	@echo "  make test           - Run tests"
	@echo "  make format         - Format code with black"
	@echo "  make lint           - Lint code with ruff"
	@echo "  make notebook       - Start Jupyter Lab"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Clean cache and temp files"

setup:
	@echo "Setting up HealthSteward..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file - please edit with your API keys"; \
	else \
		echo "✓ .env already exists"; \
	fi
	@$(MAKE) conda-create

conda-create:
	@echo "Creating conda environment..."
	conda env create -f environment.yml
	@echo "✓ Conda environment created"
	@echo "Activate with: conda activate healthsteward"

conda-update:
	@echo "Updating conda environment..."
	conda env update -f environment.yml --prune
	@echo "✓ Conda environment updated"

docker-build:
	@echo "Building Docker images..."
	docker-compose build
	@echo "✓ Docker images built"

docker-up:
	@echo "Starting Docker services..."
	docker-compose up -d
	@echo "✓ Services started"
	@echo "App: http://localhost:8000"
	@echo "ChromaDB: http://localhost:8001"

docker-down:
	@echo "Stopping Docker services..."
	docker-compose down
	@echo "✓ Services stopped"

docker-logs:
	docker-compose logs -f

docker-clean:
	@echo "Cleaning Docker resources..."
	docker-compose down -v
	@echo "✓ Containers and volumes removed"

run:
	@echo "Starting HealthSteward locally..."
	python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	@echo "Running tests..."
	pytest tests/ -v

format:
	@echo "Formatting code..."
	black src/ tests/
	@echo "✓ Code formatted"

lint:
	@echo "Linting code..."
	ruff check src/ tests/
	mypy src/
	@echo "✓ Lint complete"

notebook:
	@echo "Starting Jupyter Lab..."
	jupyter lab

clean:
	@echo "Cleaning cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf .mypy_cache .ruff_cache
	@echo "✓ Cleaned"
