"""
Ingest API Routes

This module provides the metrics ingestion endpoint.
"""

import os
import json
import logging
import psycopg2
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Header
from dotenv import load_dotenv
from backend.api.models.ingest import IngestBatch
from backend.api.routes.hosts import get_current_org_id

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["ingest"])


from backend.db.connection import get_db_connection


@router.post("/metrics")
async def ingest_metrics(batch: IngestBatch, authorization: Optional[str] = Header(None)):
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
        
        # Resolve the correct host_id and org_id from DB
        resolved_host_id = batch.host_id
        target_org_id = None

        if batch.host_id:
            cursor.execute("SELECT id, org_id FROM hosts WHERE id = %s", (batch.host_id,))
            hrow = cursor.fetchone()
            if hrow:
                resolved_host_id = hrow[0]
                target_org_id = hrow[1]

        if not target_org_id and batch.hostname:
            cursor.execute("SELECT id, org_id FROM hosts WHERE hostname = %s ORDER BY id DESC LIMIT 1", (batch.hostname,))
            hrow = cursor.fetchone()
            if hrow:
                resolved_host_id = hrow[0]
                target_org_id = hrow[1]

        if not target_org_id:
            org_id_to_use = get_current_org_id(authorization)
            cursor.execute(
                """
                INSERT INTO hosts (hostname, org_id)
                VALUES (%s, %s)
                ON CONFLICT (hostname, org_id) DO UPDATE SET hostname = EXCLUDED.hostname
                RETURNING id, org_id
                """,
                (batch.hostname or f"host-{batch.host_id}", org_id_to_use)
            )
            hrow = cursor.fetchone()
            resolved_host_id = hrow[0]
            target_org_id = hrow[1]
            logger.info(f"Auto-registered hostname '{batch.hostname}' as host_id={resolved_host_id} (org_id={target_org_id})")
        else:
            logger.info(f"Resolved metrics to host_id={resolved_host_id} (org_id={target_org_id})")
        
        # Insert into metrics_raw table using resolved host_id
        cursor.execute(
            """
            INSERT INTO metrics_raw (host_id, payload, created_at)
            VALUES (%s, %s, NOW())
            RETURNING id
            """,
            (resolved_host_id, json.dumps(payload))
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
