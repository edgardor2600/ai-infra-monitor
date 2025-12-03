"""
AI Infra Monitor - Metrics API Routes

This module defines API endpoints for metrics retrieval.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

router = APIRouter()

def get_db_connection():
    """Create a database connection."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

@router.get("/metrics")
async def get_metrics(
    host_id: int = Query(..., description="Host ID to filter metrics"),
    limit: int = Query(100, description="Maximum number of metrics to return", le=1000)
) -> List[Dict[str, Any]]:
    """
    Get recent metrics for a specific host.
    
    Args:
        host_id: ID of the host
        limit: Maximum number of records to return (default: 100, max: 1000)
        
    Returns:
        List of metrics with timestamp and values
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get raw metrics and extract individual samples
        cursor.execute(
            """
            SELECT 
                created_at,
                payload
            FROM metrics_raw
            WHERE host_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (host_id, limit)
        )
        
        raw_metrics = cursor.fetchall()
        
        # Flatten the metrics
        metrics = []
        for record in raw_metrics:
            timestamp = record['created_at'].isoformat()
            samples = record['payload'].get('samples', [])
            
            # Group samples by timestamp
            metric_point = {
                'timestamp': timestamp,
                'cpu_percent': None,
                'mem_percent': None
            }
            
            for sample in samples:
                metric_name = sample.get('metric')
                value = sample.get('value')
                
                if metric_name:
                    metric_point[metric_name] = value
            
            metrics.append(metric_point)
        
        return metrics
        
    finally:
        cursor.close()
        conn.close()
