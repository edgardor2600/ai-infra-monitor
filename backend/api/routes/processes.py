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


@router.get("/processes/top")
async def get_top_processes(
    host_id: int = Query(..., description="Host ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of top processes to return"),
    metric: str = Query("cpu", regex="^(cpu|memory)$", description="Metric to sort by: cpu or memory")
):
    """
    Get top processes by CPU or memory usage.
    
    Returns the most recent metrics for the top N processes sorted by the specified metric.
    
    Args:
        host_id: ID of the host
        limit: Number of processes to return (1-50, default 10)
        metric: Metric to sort by - "cpu" or "memory" (default "cpu")
    
    Returns:
        List of process metrics sorted by the specified metric
    
    Raises:
        HTTPException: If database query fails
    """
    logger.info(f"Getting top {limit} processes by {metric} for host_id={host_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Determine sort column
        sort_column = "cpu_percent" if metric == "cpu" else "memory_mb"
        
        # Get the most recent process metrics, sorted by the specified metric
        # We use DISTINCT ON to get the latest entry for each process
        cursor.execute(
            f"""
            SELECT DISTINCT ON (process_name, pid)
                process_name,
                pid,
                cpu_percent,
                memory_mb,
                status,
                created_at
            FROM process_metrics
            WHERE host_id = %s
                AND created_at > NOW() - INTERVAL '5 minutes'
            ORDER BY process_name, pid, created_at DESC
            """,
            (host_id,)
        )
        
        rows = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dictionaries
        processes = [
            {
                "process_name": row[0],
                "pid": row[1],
                "cpu_percent": float(row[2]) if row[2] else 0.0,
                "memory_mb": float(row[3]) if row[3] else 0.0,
                "status": row[4],
                "timestamp": row[5].isoformat() if row[5] else None
            }
            for row in rows
        ]
        
        # Sort by the specified metric and limit
        if metric == "cpu":
            processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        else:  # memory
            processes.sort(key=lambda x: x["memory_mb"], reverse=True)
        
        processes = processes[:limit]
        
        logger.info(f"Returning {len(processes)} top processes")
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
    
    Returns time-series data for the specified process over the requested time period.
    
    Args:
        process_name: Name of the process (e.g., "chrome.exe")
        host_id: ID of the host
        hours: Number of hours of history (1-24, default 1)
    
    Returns:
        List of historical metrics for the process
    
    Raises:
        HTTPException: If database query fails
    """
    logger.info(f"Getting {hours}h history for process '{process_name}' on host_id={host_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get historical data for the process
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
                AND process_name = %s
                AND created_at > NOW() - INTERVAL '%s hours'
            ORDER BY created_at ASC
            """,
            (host_id, process_name, hours)
        )
        
        rows = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dictionaries
        history = [
            {
                "process_name": row[0],
                "pid": row[1],
                "cpu_percent": float(row[2]) if row[2] else 0.0,
                "memory_mb": float(row[3]) if row[3] else 0.0,
                "status": row[4],
                "timestamp": row[5].isoformat() if row[5] else None
            }
            for row in rows
        ]
        
        logger.info(f"Returning {len(history)} historical records")
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
