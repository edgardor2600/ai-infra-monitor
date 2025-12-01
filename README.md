# AI Infra Monitor

AI Infra Monitor is a local agent-based monitoring system.

## Architecture

- **Agent**: Local Python agent to collect metrics.
- **Backend**: FastAPI backend to receive and process metrics.
- **Dashboard**: React dashboard for visualization.
- **Infra**: Docker/Compose setup for Redis, Postgres, etc.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js
- Docker

### Structure

- `agent/`: Monitoring agent code.
- `backend/`: API server code.
- `dashboard/`: Frontend application.
- `infra/`: Infrastructure configuration.
- `docs/`: Documentation.

## Development

Please refer to individual directories for specific setup instructions.
