# HealthSteward

Privacy-first AI agent system that centralizes your fragmented health information across multiple doctors and chronic conditions on your local machine.

## Features

- Autonomous doctor visit preparation with personalized question lists
- Periodic health check-ins based on your conditions
- Medication and test tracking with automatic reminders
- Multi-provider information coordination to flag contradictions
- Calendar sync for appointments and reminders
- Complete privacy - all health data stays on your local machine

## Technology Evolution Path

### Phase 1: Claude API (Months 0-2)
- Agentic AI powered by Claude API
- Rapid prototyping and data collection

### Phase 2: Model Distillation (Months 2-3)
- Train 7B parameter model from Claude examples
- Reduce costs from $0.05/visit to essentially free

### Phase 3: Quantization (Month 3)
- Compress model from 14GB to 4GB
- Enable fast local inference

### Phase 4: Fine-tuning (Months 3-4)
- Domain-specific fine-tuning with LoRA
- Customize for health domain

### Phase 5: RAG Integration (Months 4-5)
- Ground model in medical guidelines
- Drug interaction databases
- Build evaluation benchmarks

### Phase 6: RLHF (Months 6-7, Optional)
- Collect feedback on visit preparations
- Train model to match personal preferences

## Setup

### Prerequisites

- macOS (tested on macOS 14+)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/)
- [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- [Anthropic API Key](https://console.anthropic.com/)

### Option 1: Local Development with Conda (Recommended for Development)

1. **Clone and navigate to the project:**
   ```bash
   cd /Users/menon/workspace/HealthSteward
   ```

2. **Create the conda environment:**
   ```bash
   conda env create -f environment.yml
   ```

3. **Activate the environment:**
   ```bash
   conda activate healthsteward
   ```

4. **Create your environment file:**
   ```bash
   cp .env.example .env
   ```

5. **Edit .env and add your API keys:**
   ```bash
   nano .env  # or use your preferred editor
   ```

   At minimum, set:
   - `ANTHROPIC_API_KEY=your_actual_api_key_here`

6. **Run the development server:**
   ```bash
   python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Verify it's working:**
   ```bash
   curl http://localhost:8000/health
   ```

### Option 2: Docker with Docker Compose (Recommended for Production)

1. **Create your environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env and add your API keys:**
   ```bash
   nano .env
   ```

3. **Build and start all services:**
   ```bash
   docker-compose up -d
   ```

   This starts:
   - HealthSteward app (port 8000)
   - PostgreSQL database (port 5432)
   - Redis cache (port 6379)
   - ChromaDB vector database (port 8001)

4. **Check service status:**
   ```bash
   docker-compose ps
   ```

5. **View logs:**
   ```bash
   docker-compose logs -f app
   ```

6. **Stop all services:**
   ```bash
   docker-compose down
   ```

### Option 3: Hybrid (Local Development + Docker Services)

Best of both worlds - develop with conda but use Docker for databases:

1. **Start only the database services:**
   ```bash
   docker-compose up -d db redis chromadb
   ```

2. **Activate conda environment:**
   ```bash
   conda activate healthsteward
   ```

3. **Run the app locally:**
   ```bash
   python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Project Structure

```
HealthSteward/
├── src/
│   ├── agents/          # AI agent logic
│   ├── api/             # FastAPI endpoints
│   ├── data/            # Data processing
│   ├── models/          # ML model definitions
│   └── utils/           # Utility functions
├── data/
│   ├── health_records/  # YOUR HEALTH DATA (never committed!)
│   ├── models/          # Downloaded/trained models
│   └── cache/           # Temporary cache
├── config/              # Configuration files
├── logs/                # Application logs
├── tests/               # Unit and integration tests
├── notebooks/           # Jupyter notebooks for experiments
├── scripts/             # Utility scripts
├── environment.yml      # Conda dependencies
├── Dockerfile           # Docker image definition
└── docker-compose.yml   # Multi-service orchestration
```

## Development Workflow

### Running Tests
```bash
pytest tests/
```

### Jupyter Notebooks
```bash
jupyter lab
```

### Code Formatting
```bash
black src/
ruff check src/
```

### Type Checking
```bash
mypy src/
```

## Updating Dependencies

### Conda Environment
```bash
# Update environment.yml with new packages, then:
conda env update -f environment.yml --prune
```

### Docker Image
```bash
# Rebuild after changing environment.yml:
docker-compose build
```

## Data Privacy

**CRITICAL**: All health data stays local. Never commit:
- `data/health_records/`
- `.env` files
- Database files
- Model checkpoints (unless you want to share them)

The `.gitignore` is configured to protect your data, but always double-check before committing.

## GPU Support

### For Local Development (Mac with Apple Silicon)
PyTorch with MPS (Metal Performance Shaders) is included in `environment.yml`.

### For Docker with NVIDIA GPU
Uncomment the GPU configuration in `docker-compose.yml`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Troubleshooting

### Conda environment issues
```bash
# Remove and recreate
conda env remove -n healthsteward
conda env create -f environment.yml
```

### Docker build fails
```bash
# Clean rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Port already in use
```bash
# Find what's using port 8000
lsof -i :8000

# Change port in docker-compose.yml or .env
```

### Database connection issues
```bash
# Check if database is running
docker-compose ps db

# View database logs
docker-compose logs db
```

## Next Steps

1. Set up your health data schema in `src/data/`
2. Implement the Claude agent in `src/agents/`
3. Create API endpoints for doctor visit prep
4. Build the interview system
5. Add calendar integration
6. Start collecting training data for distillation

## License

Private project - All rights reserved

## Contributing

This is a personal health project. Not accepting contributions at this time.
