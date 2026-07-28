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


from backend.db.connection import get_db_connection


@router.post("/metrics")
async def ingest_metrics(batch: IngestBatch):
    """
    Ingest a batch of metrics from a host.
    
    This endpoint receives metric samples, validates them, and stores
    the complete payload in the metrics_raw table. If process metrics
    are included, they are also stored in the process_metrics table.
    
    Args:
        batch: IngestBatch containing host_id, timestamp, interval, samples, and optional processes
    
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
        
        # Insert process metrics if present
        # Two sources: typed ProcessSample list OR raw processes from payload JSONB
        processes_count = 0
        raw_processes = []

        if batch.processes:
            # Typed structured list (preferred)
            raw_processes = [
                {
                    "name":        p.name,
                    "pid":         p.pid,
                    "cpu_percent": p.cpu_percent,
                    "memory_mb":   p.memory_mb,
                    "status":      p.status,
                }
                for p in batch.processes
            ]
        elif payload.get("processes"):
            # Fallback: processes sent inside the JSONB payload dict
            raw_processes = payload["processes"]

        for proc in raw_processes:
            try:
                cursor.execute(
                    """
                    INSERT INTO process_metrics
                    (host_id, process_name, pid, cpu_percent, memory_mb, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        batch.host_id,
                        proc.get("name", "unknown"),
                        proc.get("pid", 0),
                        proc.get("cpu_percent", 0.0),
                        proc.get("memory_mb", 0.0),
                        proc.get("status", "running"),
                    ),
                )
                processes_count += 1
            except Exception as pe:
                logger.warning(f"Failed to insert process {proc.get('name')}: {pe}")
        
        conn.commit()
        cursor.close()
        
        samples_count = len(batch.samples)
        logger.info(
            f"Stored batch (id={row_id}) with {samples_count} samples "
            f"and {processes_count} process metrics"
        )
        
        return {
            "ok": True,
            "received": samples_count,
            "processes": processes_count
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
