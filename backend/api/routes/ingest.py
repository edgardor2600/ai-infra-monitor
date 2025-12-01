"""
Ingest API Routes

This module provides the metrics ingestion endpoint.
"""

import os
import json
import logging
import psycopg2
from fastapi import APIRouter, HTTPException, status
from dotenv import load_dotenv
from backend.api.models.ingest import IngestBatch

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["ingest"])


def get_db_connection():
    """
    Create a database connection using environment variables.
    
    Returns:
        psycopg2.connection: Database connection object
    
    Raises:
        HTTPException: If connection fails
    """
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )


@router.post("/metrics")
async def ingest_metrics(batch: IngestBatch):
    """
    Ingest a batch of metrics from a host.
    
    This endpoint receives metric samples, validates them, and stores
    the complete payload in the metrics_raw table.
    
    Args:
        batch: IngestBatch containing host_id, timestamp, interval, and samples
    
    Returns:
        dict: Response with ok status and number of samples received
    
    Raises:
        HTTPException: If database operation fails
    """
    logger.info(f"Receiving metrics batch from host_id={batch.host_id}")
    
    # Convert batch to JSON for storage
    payload = batch.model_dump(mode='json')
    
    # Store in database
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert into metrics_raw table
        cursor.execute(
            """
            INSERT INTO metrics_raw (host_id, payload, created_at)
            VALUES (%s, %s, NOW())
            RETURNING id
            """,
            (batch.host_id, json.dumps(payload))
        )
        
        row_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        
        samples_count = len(batch.samples)
        logger.info(f"Stored batch (id={row_id}) with {samples_count} samples")
        
        return {
            "ok": True,
            "received": samples_count
        }
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store metrics"
        )
    finally:
        if conn:
            conn.close()
