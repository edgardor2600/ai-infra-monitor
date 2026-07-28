"""
Process Metrics API Routes

This module provides endpoints for querying process-level metrics.
"""

import os
import logging
import psycopg2
from fastapi import APIRouter, HTTPException, Query, status
from dotenv import load_dotenv
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["processes"])


from backend.db.connection import get_db_connection


@router.get("/processes/top")
async def get_top_processes(
    host_id: int = Query(..., description="Host ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of top processes to return"),
    metric: str = Query("cpu", pattern="^(cpu|memory)$", description="Metric to sort by: cpu or memory")
):
    """
    Get top processes by CPU or memory usage.

    Reads process data directly from the JSONB payload in metrics_raw
    (where the agent stores real-time process snapshots), then falls back
    to the process_metrics table if no payload data exists.
    """
    logger.info(f"Getting top {limit} processes by {metric} for host_id={host_id}")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ── Strategy 1: Read from the latest metrics_raw JSONB payload ────────
        # The agent sends processes inside payload['processes'] every cycle.
        # This is the most up-to-date source.
        cursor.execute(
            """
            SELECT payload->'processes'
            FROM metrics_raw
            WHERE host_id = %s
              AND payload->'processes' IS NOT NULL
              AND jsonb_array_length(payload->'processes') > 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (host_id,)
        )
        row = cursor.fetchone()

        processes = []
        if row and row[0]:
            raw_processes = row[0]  # Already a Python list via psycopg2 JSONB
            if isinstance(raw_processes, list):
                for p in raw_processes:
                    processes.append({
                        "process_name": p.get("name", "unknown"),
                        "pid":          p.get("pid", 0),
                        "cpu_percent":  float(p.get("cpu_percent", 0.0)),
                        "memory_mb":    float(p.get("memory_mb", 0.0)),
                        "status":       p.get("status", "running"),
                        "timestamp":    None,
                    })

        # ── Strategy 2: Fallback to process_metrics table (extended window) ──
        if not processes:
            logger.info(f"No payload processes found — falling back to process_metrics table")
            cursor.execute(
                """
                SELECT DISTINCT ON (process_name, pid)
                    process_name, pid, cpu_percent, memory_mb, status, created_at
                FROM process_metrics
                WHERE host_id = %s
                  AND created_at > NOW() - INTERVAL '48 hours'
                ORDER BY process_name, pid, created_at DESC
                """,
                (host_id,)
            )
            rows = cursor.fetchall()
            processes = [
                {
                    "process_name": r[0],
                    "pid":          r[1],
                    "cpu_percent":  float(r[2]) if r[2] else 0.0,
                    "memory_mb":    float(r[3]) if r[3] else 0.0,
                    "status":       r[4],
                    "timestamp":    r[5].isoformat() if r[5] else None,
                }
                for r in rows
            ]

        cursor.close()

        # Sort and limit
        sort_key = "cpu_percent" if metric == "cpu" else "memory_mb"
        processes.sort(key=lambda x: x[sort_key], reverse=True)
        processes = processes[:limit]

        logger.info(f"Returning {len(processes)} top processes for host {host_id}")
        return processes

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch process metrics"
        )
    finally:
        if conn:
            conn.close()



@router.get("/processes/{process_name}/history")
async def get_process_history(
    process_name: str,
    host_id: int = Query(..., description="Host ID"),
    hours: int = Query(1, ge=1, le=24, description="Number of hours of history to return")
):
    """
    Get historical metrics for a specific process.
    
    Reads process time-series metrics from metrics_raw JSONB payload,
    falling back to the process_metrics table.
    """
    logger.info(f"Getting {hours}h history for process '{process_name}' on host_id={host_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ── Strategy 1: Query history from metrics_raw JSONB payload ─────────
        cursor.execute(
            """
            SELECT
                created_at,
                p->>'name' as process_name,
                (p->>'pid')::int as pid,
                (p->>'cpu_percent')::float as cpu_percent,
                (p->>'memory_mb')::float as memory_mb,
                p->>'status' as status
            FROM metrics_raw,
                 jsonb_array_elements(payload->'processes') as p
            WHERE host_id = %s
              AND LOWER(p->>'name') = LOWER(%s)
              AND created_at >= NOW() - (%s || ' hours')::INTERVAL
            ORDER BY created_at ASC
            """,
            (host_id, process_name, hours)
        )
        
        rows = cursor.fetchall()
        
        # Fallback 1a: If last N hours yielded no rows, query last 48 hours for metrics_raw
        if not rows:
            cursor.execute(
                """
                SELECT
                    created_at,
                    p->>'name' as process_name,
                    (p->>'pid')::int as pid,
                    (p->>'cpu_percent')::float as cpu_percent,
                    (p->>'memory_mb')::float as memory_mb,
                    p->>'status' as status
                FROM metrics_raw,
                     jsonb_array_elements(payload->'processes') as p
                WHERE host_id = %s
                  AND LOWER(p->>'name') = LOWER(%s)
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (host_id, process_name)
            )
            rows = cursor.fetchall()
            rows.reverse()  # Reorder chronologically

        history = [
            {
                "timestamp":    row[0].isoformat() if row[0] else None,
                "process_name": row[1],
                "pid":          row[2],
                "cpu_percent":  float(row[3]) if row[3] else 0.0,
                "memory_mb":    float(row[4]) if row[4] else 0.0,
                "status":       row[5] or "running",
            }
            for row in rows
        ]

        # ── Strategy 2: Fallback to process_metrics table if JSONB yields 0 ──
        if not history:
            cursor.execute(
                """
                SELECT
                    process_name,
                    pid,
                    cpu_percent,
                    memory_mb,
                    status,
                    created_at
                FROM process_metrics
                WHERE host_id = %s
                  AND LOWER(process_name) = LOWER(%s)
                  AND created_at >= NOW() - (%s || ' hours')::INTERVAL
                ORDER BY created_at ASC
                """,
                (host_id, process_name, hours)
            )
            rows = cursor.fetchall()
            history = [
                {
                    "process_name": r[0],
                    "pid":          r[1],
                    "cpu_percent":  float(r[2]) if r[2] else 0.0,
                    "memory_mb":    float(r[3]) if r[3] else 0.0,
                    "status":       r[4] or "running",
                    "timestamp":    r[5].isoformat() if r[5] else None,
                }
                for r in rows
            ]
        
        cursor.close()
        logger.info(f"Returning {len(history)} historical records for process '{process_name}'")
        return history
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch process history"
        )
    finally:
        if conn:
            conn.close()


@router.get("/processes/list")
async def get_process_list(
    host_id: int = Query(..., description="Host ID")
):
    """
    Get list of all unique processes that have been monitored.
    
    Returns a list of unique process names that have metrics in the database.
    
    Args:
        host_id: ID of the host
    
    Returns:
        List of unique process names
    
    Raises:
        HTTPException: If database query fails
    """
    logger.info(f"Getting process list for host_id={host_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get distinct process names from the last 24 hours
        cursor.execute(
            """
            SELECT DISTINCT process_name
            FROM process_metrics
            WHERE host_id = %s
                AND created_at > NOW() - INTERVAL '24 hours'
            ORDER BY process_name
            """,
            (host_id,)
        )
        
        rows = cursor.fetchall()
        cursor.close()
        
        # Extract process names
        processes = [row[0] for row in rows]
        
        logger.info(f"Returning {len(processes)} unique processes")
        return {"processes": processes}
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch process list"
        )
    finally:
        if conn:
            conn.close()
