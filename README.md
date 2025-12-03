# AI Infrastructure Monitor

A comprehensive infrastructure monitoring solution with intelligent alerting and AI-powered analysis. The system consists of a lightweight agent for metric collection, a robust backend API for data processing, and a modern web dashboard for visualization and management.

## Overview

AI Infrastructure Monitor provides real-time monitoring of system resources, process-level metrics, and intelligent alerting capabilities. The platform leverages AI to analyze alerts and provide actionable insights for infrastructure management.

## Key Features

- **Real-time System Monitoring**: Track CPU, memory, disk, and network metrics
- **Process-Level Monitoring**: Monitor top resource-consuming processes with detailed metrics
- **Intelligent Alerting**: Rule-based alert system with configurable thresholds
- **AI-Powered Analysis**: Automated alert analysis using Google Gemini AI
- **Modern Dashboard**: Interactive web interface for visualization and management
- **RESTful API**: Comprehensive API for metric ingestion and data retrieval
- **Scalable Architecture**: Agent-based design supporting multiple hosts

## Architecture

The system follows a distributed architecture with three main components:

### Agent

Lightweight Python agent deployed on monitored hosts to collect system and process metrics. Supports configurable collection intervals and automatic retry mechanisms.

### Backend

FastAPI-based REST API server responsible for:

- Metric ingestion and storage
- Alert rule evaluation
- AI-powered alert analysis
- Data aggregation and querying

### Dashboard

React-based web application providing:

- Real-time metric visualization
- Host management interface
- Alert monitoring and analysis
- Process monitoring dashboard

### Infrastructure

PostgreSQL database for persistent storage with optimized indexes for time-series queries.

## Technology Stack

**Backend:**

- Python 3.10+
- FastAPI
- PostgreSQL
- psycopg2
- Google Generative AI (Gemini)

**Frontend:**

- React 18
- React Router
- Axios
- Modern CSS3

**Agent:**

- Python 3.10+
- psutil
- requests

## Prerequisites

- Python 3.10 or higher
- Node.js 16 or higher
- PostgreSQL 13 or higher
- Google AI API key (for analysis features)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/edgardor2600/ai-infra-monitor.git
cd ai-infra-monitor
```

### 2. Database Setup

Create a PostgreSQL database and initialize the schema:

```bash
psql -U postgres -c "CREATE DATABASE ai_infra_monitor;"
python backend/scripts/init_db.py
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_infra_monitor
GEMINI_API_KEY=your_google_ai_api_key
BACKEND_URL=http://localhost:8000
```

### 4. Backend Setup

Install dependencies and start the API server:

```bash
pip install -e backend/
python -m uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

API Documentation:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 5. Agent Setup

Install dependencies and start the monitoring agent:

```bash
pip install -e agent/
python -m agent run
```

For dry-run mode (no data transmission):

```bash
python -m agent run --dry-run
```

### 6. Worker Setup

Start the background worker for alert processing:

```bash
python backend/worker/run_worker.py
```

### 7. Dashboard Setup

Install dependencies and start the development server:

```bash
cd dashboard
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173`

## Project Structure

```
ai-infra-monitor/
├── agent/                      # Monitoring agent
│   ├── collector.py           # Metric collection logic
│   ├── run.py                 # Agent entry point
│   └── tests/                 # Agent tests
├── backend/                    # API server
│   ├── api/                   # API routes and models
│   │   ├── models/           # Pydantic models
│   │   └── routes/           # API endpoints
│   ├── app/                   # Application core
│   │   ├── main.py           # FastAPI application
│   │   └── llm_adapter.py    # AI integration
│   ├── db/                    # Database
│   │   └── schema.sql        # Database schema
│   ├── worker/                # Background workers
│   │   ├── rules.py          # Alert rules
│   │   ├── worker.py         # Alert worker
│   │   └── analysis_worker.py # AI analysis worker
│   ├── scripts/               # Utility scripts
│   └── tests/                 # Backend tests
├── dashboard/                  # Web dashboard
│   ├── src/
│   │   ├── pages/            # React pages
│   │   ├── api.js            # API client
│   │   └── App.jsx           # Main application
│   └── public/               # Static assets
├── docs/                       # Documentation
└── infra/                      # Infrastructure config
```

## API Endpoints

### Metrics

- `POST /api/v1/ingest/metrics` - Ingest metric batches
- `GET /api/v1/metrics/{host_id}` - Retrieve host metrics

### Processes

- `GET /api/v1/processes/{host_id}` - Get process metrics for a host

### Alerts

- `GET /api/v1/alerts` - List all alerts
- `GET /api/v1/alerts/{alert_id}` - Get alert details
- `POST /api/v1/alerts/{alert_id}/analyze` - Trigger AI analysis

### Hosts

- `GET /api/v1/hosts` - List all monitored hosts
- `GET /api/v1/hosts/{host_id}` - Get host details

## Configuration

### Agent Configuration

The agent can be configured via command-line arguments:

```bash
python -m agent run --help
```

Key options:

- `--dry-run`: Run without sending data to backend
- `--interval`: Collection interval in seconds (default: 60)

### Alert Rules

Alert rules are defined in `backend/worker/rules.py`:

- **CPU Over 90**: Triggers HIGH severity alert when CPU exceeds 90%
- **CPU Delta**: Triggers MEDIUM severity alert on significant CPU changes

Custom rules can be added by implementing the rule interface.

## Development

### Running Tests

```bash
# Backend tests
pytest backend/tests/

# Agent tests
pytest agent/tests/
```

### Database Migrations

To add new tables or modify schema:

1. Update `backend/db/schema.sql`
2. Create migration script in `backend/scripts/`
3. Run migration: `python backend/scripts/your_migration.py`

### Adding New Metrics

1. Update collector in `agent/collector.py`
2. Update Pydantic models in `backend/api/models/ingest.py`
3. Update database schema if needed
4. Update dashboard components

## Monitoring Features

### System Metrics

- CPU utilization percentage
- Memory usage (total, available, percent)
- Disk usage per partition
- Network I/O statistics

### Process Metrics

- Top 10 resource-consuming processes
- Per-process CPU and memory usage
- Process status and PID tracking
- Historical process data

### Alert System

- Real-time alert generation
- Severity levels: HIGH, MEDIUM, LOW
- Alert status tracking (open, acknowledged, resolved)
- Automated alert analysis with AI

## Troubleshooting

### Agent Not Sending Data

Check backend connectivity:

```bash
curl http://localhost:8000/health
```

Verify agent logs and ensure `BACKEND_URL` is correctly configured.

### Database Connection Issues

Verify PostgreSQL is running and credentials are correct:

```bash
python test_db.py
```

### Missing Process Data

Ensure the agent has sufficient permissions to read process information. On Windows, run as Administrator if needed.

## Contributing

Contributions are welcome. Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes with appropriate tests
4. Submit a pull request with a clear description
