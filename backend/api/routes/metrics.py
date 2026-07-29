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
    Only returns metrics received in the last 24 hours, prioritizing the last 10 minutes.
    This ensures stale/synthetic data never contaminates live dashboards.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Try last 30 minutes first (real-time window)
        cursor.execute(
            """
            SELECT 
                created_at,
                payload
            FROM metrics_raw
            WHERE host_id = %s
              AND created_at >= NOW() - INTERVAL '30 minutes'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (host_id, limit)
        )
        raw_metrics = cursor.fetchall()

        # Fallback 1: if no data in last 30 min, try last 6 hours
        if not raw_metrics:
            cursor.execute(
                """
                SELECT 
                    created_at,
                    payload
                FROM metrics_raw
                WHERE host_id = %s
                  AND created_at >= NOW() - INTERVAL '6 hours'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (host_id, limit)
            )
            raw_metrics = cursor.fetchall()

        # Fallback 2: if still no data, try last 24 hours (agent restarted after long pause)
        if not raw_metrics:
            cursor.execute(
                """
                SELECT 
                    created_at,
                    payload
                FROM metrics_raw
                WHERE host_id = %s
                  AND created_at >= NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (host_id, limit)
            )
            raw_metrics = cursor.fetchall()
        
        metrics = []
        for record in raw_metrics:
            batch_dt = record['created_at']
            # Format ISO UTC timestamp with explicit Z suffix so frontend converts to local browser time
            if isinstance(batch_dt, datetime):
                if batch_dt.tzinfo is None:
                    batch_dt = batch_dt.replace(tzinfo=timezone.utc)
                batch_ts = batch_dt.isoformat().replace("+00:00", "Z")
                if not batch_ts.endswith("Z"):
                    batch_ts += "Z"
            else:
                batch_ts = str(batch_dt)

            payload = record['payload'] if isinstance(record['payload'], dict) else json.loads(record['payload'])
            samples = payload.get('samples', [])
            hostname = payload.get('hostname', f"Host #{host_id}")
            
            # Detect format: nested (each sample has its own timestamp + metrics[]) vs flat (list of {metric,value})
            is_nested = samples and isinstance(samples[0], dict) and 'metrics' in samples[0]
            
            if is_nested:
                # Nested format from standalone_agent: expand each sample into its own data point
                for sample_item in samples:
                    if not isinstance(sample_item, dict):
                        continue
                    
                    # Use sample's own timestamp if available, else fallback to batch timestamp
                    sample_ts_raw = sample_item.get('timestamp')
                    if sample_ts_raw:
                        try:
                            sd = datetime.fromisoformat(sample_ts_raw.replace("Z", "+00:00"))
                            if sd.tzinfo is None:
                                sd = sd.replace(tzinfo=timezone.utc)
                            sample_ts = sd.isoformat().replace("+00:00", "Z")
                            if not sample_ts.endswith("Z"):
                                sample_ts += "Z"
                        except Exception:
                            sample_ts = batch_ts
                    else:
                        sample_ts = batch_ts

                    metric_point = {
                        'timestamp': sample_ts,
                        'hostname': hostname,
                        'cpu_percent': None,
                        'mem_percent': None,
                        'disk_percent': None,
                        'disk_free_gb': None,
                        'disk_total_gb': None,
                        'net_bytes_sent': None,
                        'net_bytes_recv': None
                    }
                    
                    for sub in sample_item.get('metrics', []):
                        if isinstance(sub, dict) and 'metric' in sub and 'value' in sub:
                            m_name = sub.get('metric')
                            m_val = sub.get('value')
                            if m_name in metric_point and m_val is not None:
                                metric_point[m_name] = float(m_val)
                    
                    if metric_point['cpu_percent'] is not None or metric_point['mem_percent'] is not None:
                        metrics.append(metric_point)
            else:
                # Flat format from run.py: one data point per batch row
                metric_point = {
                    'timestamp': batch_ts,
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
                    if 'metric' in item and 'value' in item:
                        m_name = item.get('metric')
                        m_val = item.get('value')
                        if m_name in metric_point and m_val is not None:
                            metric_point[m_name] = float(m_val)
                
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
