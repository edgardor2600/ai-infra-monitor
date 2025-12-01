"""
Tests for Ingest Endpoint

Tests for the metrics ingestion API endpoint.
"""

import os
import json
import pytest
import psycopg2
from fastapi.testclient import TestClient
from dotenv import load_dotenv
from backend.app.main import app

# Load environment variables
load_dotenv()


@pytest.fixture
def client():
    """
    Create a TestClient fixture for testing the FastAPI app.
    
    Returns:
        TestClient: FastAPI test client instance
    """
    return TestClient(app)


@pytest.fixture
def db_connection():
    """
    Create a database connection for testing.
    
    Yields:
        psycopg2.connection: Database connection
    """
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    yield conn
    conn.close()


@pytest.fixture
def test_host(db_connection):
    """
    Create a test host in the database.
    """
    cursor = db_connection.cursor()
    cursor.execute("INSERT INTO hosts (id, hostname) VALUES (1, 'test-host') ON CONFLICT (id) DO NOTHING;")
    db_connection.commit()
    cursor.close()
    return 1

@pytest.fixture
def sample_batch(test_host):
    """
    Create a sample IngestBatch payload.
    
    Returns:
        dict: Sample batch data
    """
    return {
        "host_id": test_host,
        "timestamp": "2025-12-01T14:00:00Z",
        "interval": 60,
        "samples": [
            {"metric": "cpu_usage", "value": 45.2},
            {"metric": "memory_used_mb", "value": 8192.0},
            {"metric": "disk_usage_percent", "value": 67.5}
        ]
    }


def test_ingest_metrics_success(client, db_connection, sample_batch):
    """
    Test successful metrics ingestion.
    
    Args:
        client: FastAPI test client
        db_connection: Database connection
        sample_batch: Sample batch data
    """
    # Get initial count
    cursor = db_connection.cursor()
    cursor.execute("SELECT count(*) FROM metrics_raw;")
    initial_count = cursor.fetchone()[0]
    cursor.close()
    
    # Send POST request
    response = client.post(
        "/api/v1/ingest/metrics",
        json=sample_batch
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["received"] == 3
    
    # Verify database insertion
    cursor = db_connection.cursor()
    cursor.execute("SELECT count(*) FROM metrics_raw;")
    final_count = cursor.fetchone()[0]
    cursor.close()
    
    assert final_count == initial_count + 1


def test_ingest_metrics_response_structure(client, sample_batch):
    """
    Test that the response has the correct structure.
    
    Args:
        client: FastAPI test client
        sample_batch: Sample batch data
    """
    response = client.post(
        "/api/v1/ingest/metrics",
        json=sample_batch
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "received" in data
    assert isinstance(data["ok"], bool)
    assert isinstance(data["received"], int)


def test_ingest_metrics_payload_stored(client, db_connection, sample_batch):
    """
    Test that the payload is correctly stored in the database.
    
    Args:
        client: FastAPI test client
        db_connection: Database connection
        sample_batch: Sample batch data
    """
    # Send POST request
    response = client.post(
        "/api/v1/ingest/metrics",
        json=sample_batch
    )
    
    assert response.status_code == 200
    
    # Verify payload in database
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT host_id, payload 
        FROM metrics_raw 
        ORDER BY created_at DESC 
        LIMIT 1;
    """)
    row = cursor.fetchone()
    cursor.close()
    
    assert row is not None
    assert row[0] == sample_batch["host_id"]
    
    # Verify payload structure
    payload = row[1]
    assert "samples" in payload
    assert len(payload["samples"]) == 3


def test_ingest_metrics_invalid_payload(client):
    """
    Test that invalid payloads are rejected.
    
    Args:
        client: FastAPI test client
    """
    invalid_batch = {
        "host_id": -1,  # Invalid: must be > 0
        "timestamp": "2025-12-01T14:00:00Z",
        "interval": 60,
        "samples": []  # Invalid: must have at least 1 sample
    }
    
    response = client.post(
        "/api/v1/ingest/metrics",
        json=invalid_batch
    )
    
    assert response.status_code == 422  # Validation error


def test_ingest_metrics_missing_fields(client):
    """
    Test that requests with missing fields are rejected.
    
    Args:
        client: FastAPI test client
    """
    incomplete_batch = {
        "host_id": 1,
        "timestamp": "2025-12-01T14:00:00Z"
        # Missing interval and samples
    }
    
    response = client.post(
        "/api/v1/ingest/metrics",
        json=incomplete_batch
    )
    
    assert response.status_code == 422  # Validation error
