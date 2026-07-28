"""
AI Infra Monitor - Metrics API Routes

This module defines API endpoints for metric retrieval, supporting real agent telemetry.
"""

import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

from backend.db.connection import get_db_connection


@router.get("/metrics")
async def get_metrics(
    host_id: int = Query(..., description="Host ID to filter metrics"),
    limit: int = Query(100, description="Maximum number of metrics to return", le=1000)
) -> List[Dict[str, Any]]:
    """
    Get recent telemetry metrics for a specific host.
    Reads real metrics submitted by host agents from metrics_raw.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Query latest metric batches for host
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
        
        metrics = []
        for record in raw_metrics:
            dt = record['created_at']
            # Format ISO UTC timestamp with explicit Z suffix so frontend converts to local browser time
            if isinstance(dt, datetime):
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                timestamp = dt.isoformat().replace("+00:00", "Z")
                if not timestamp.endswith("Z"):
                    timestamp += "Z"
            else:
                timestamp = str(dt)

            payload = record['payload'] if isinstance(record['payload'], dict) else json.loads(record['payload'])
            samples = payload.get('samples', [])
            hostname = payload.get('hostname', f"Host #{host_id}")
            
            # Extract metrics from samples (handling both flat and nested sample formats)
            metric_point = {
                'timestamp': timestamp,
                'hostname': hostname,
                'cpu_percent': None,
                'mem_percent': None,
                'disk_percent': None,
                'disk_free_gb': None,
                'disk_total_gb': None,
                'net_bytes_sent': None,
                'net_bytes_recv': None
            }
            
            for item in samples:
                if not isinstance(item, dict):
                    continue
                
                # Check if item is a flat metric dict {"metric": "cpu_percent", "value": 11.0}
                if 'metric' in item and 'value' in item:
                    m_name = item.get('metric')
                    m_val = item.get('value')
                    if m_name in metric_point and m_val is not None:
                        metric_point[m_name] = float(m_val)
                
                # Check if item is a sample container containing a "metrics" array
                if 'metrics' in item and isinstance(item['metrics'], list):
                    for sub in item['metrics']:
                        if isinstance(sub, dict) and 'metric' in sub and 'value' in sub:
                            m_name = sub.get('metric')
                            m_val = sub.get('value')
                            if m_name in metric_point and m_val is not None:
                                metric_point[m_name] = float(m_val)

            # Only include point if at least CPU or Memory metric was extracted
            if metric_point['cpu_percent'] is not None or metric_point['mem_percent'] is not None:
                metrics.append(metric_point)

        # Trigger auto-remediation check if latest disk usage >= 90%
        if metrics:
            latest_disk = metrics[0].get('disk_percent') or 0.0
            if latest_disk >= 90.0:
                try:
                    import asyncio
                    from backend.disk_analyzer.auto_remediator import AutoRemediator
                    asyncio.create_task(AutoRemediator.check_and_execute(host_id, org_id=1, current_disk_percent=latest_disk))
                except Exception as ex:
                    logger.error(f"Error launching AutoRemediator task: {ex}")

        return metrics
        
    finally:
        cursor.close()
        conn.close()
