# AI Infra Monitor

AI Infra Monitor is a local agent-based monitoring system for tracking infrastructure metrics.

## Architecture

- **Agent**: Local Python agent to collect metrics
- **Backend**: FastAPI backend to receive and process metrics
- **Dashboard**: React dashboard for visualization
- **Infra**: Docker/Compose setup for Redis, Postgres, etc.

## Prerequisites

- Python 3.10+
- Node.js
- Docker

## Project Structure

```
ai-infra-monitor/
├── agent/          # Monitoring agent
├── backend/        # API server
├── dashboard/      # Frontend application
├── infra/          # Infrastructure configuration
└── docs/           # Documentation
```

## Getting Started

### Backend Setup

The backend is built with FastAPI and provides health check endpoints.

**Install dependencies:**

```bash
pip install -e backend/
```

**Run development server:**

```powershell
.\backend\run-dev.ps1
```

Or directly with uvicorn:

```bash
python -m uvicorn backend.app.main:app --reload
```

**Run tests:**

```bash
pytest backend/tests/
```

**API Documentation:**

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Agent Setup

The agent collects system metrics and outputs them as JSON.

**Install dependencies:**

```bash
pip install -e agent/
```

**Run agent in dry-run mode:**

```bash
python -m agent run --dry-run
```

**View help:**

```bash
python -m agent --help
python -m agent run --help
```

**Run tests:**

```bash
pytest agent/tests/
```

## Development

Each component can be developed independently. Refer to the component directories for specific implementation details.

### Running Tests

```bash
# Backend tests
pytest backend/tests/

# Agent tests
pytest agent/tests/
```

## License

MIT
