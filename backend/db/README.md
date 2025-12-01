# Database Schema

This directory contains the database schema and related documentation for the AI Infra Monitor backend.

## Prerequisites

- PostgreSQL 12+ installed and running
- Database created: `ai_infra_monitor`
- Environment variables configured in `.env` file

## Database Setup

### 1. Create Database

Connect to PostgreSQL and create the database:

```bash
psql -U postgres
```

```sql
CREATE DATABASE ai_infra_monitor;
\q
```

### 2. Configure Environment Variables

Ensure your `.env` file contains:

```env
DB_NAME=ai_infra_monitor
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 3. Initialize Schema

Run the initialization script:

```bash
python backend/scripts/init_db.py
```

This will:

- Drop existing tables (if any)
- Create all required tables
- Set up indexes
- Verify the setup

## Schema Overview

### Tables

#### `hosts`

Stores information about monitored hosts.

- `id`: Primary key
- `hostname`: Unique hostname
- `created_at`: Timestamp of registration

#### `metrics`

Stores collected metrics from hosts.

- `id`: Primary key
- `host_id`: Foreign key to hosts
- `payload`: JSONB containing metric data
- `created_at`: Timestamp of collection

#### `alerts`

Stores alerts generated from metrics.

- `id`: Primary key
- `host_id`: Foreign key to hosts
- `level`: Alert level (e.g., warning, critical)
- `message`: Alert message
- `created_at`: Timestamp of alert

#### `analyses`

Stores AI analysis results.

- `id`: Primary key
- `host_id`: Foreign key to hosts
- `result`: JSONB containing analysis data
- `created_at`: Timestamp of analysis

## Verification

### Connect to Database

```bash
psql -U postgres -d ai_infra_monitor
```

### List Tables

```sql
\dt
```

### Check Table Structure

```sql
\d hosts
\d metrics
\d alerts
\d analyses
```

### Verify Empty Tables

```sql
SELECT count(*) FROM metrics;
SELECT count(*) FROM alerts;
SELECT count(*) FROM analyses;
```

All should return `0` after initialization.

## Re-initialization

The schema script is idempotent. You can run it multiple times:

```bash
python backend/scripts/init_db.py
```

This will drop and recreate all tables.
