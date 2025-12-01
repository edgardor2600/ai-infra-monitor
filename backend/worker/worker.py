"""
AI Infra Monitor - Worker Module

This module processes host metrics and creates alerts based on defined rules.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.worker.rules import rule_cpu_over_90, rule_cpu_delta

logger = logging.getLogger(__name__)


async def create_alert(
    conn,
    host_id: int,
    metric_name: str,
    severity: str,
    message: str
) -> int:
    """
    Inserta una alerta en BD.
    
    Args:
        conn: Database connection
        host_id: Host identifier
        metric_name: Name of the metric that triggered the alert
        severity: Alert severity (HIGH, MEDIUM, LOW)
        message: Alert message
        
    Returns:
        int: ID of the created alert
    """
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO alerts (host_id, metric_name, severity, message, status)
        VALUES (%s, %s, %s, %s, 'open')
        RETURNING id
        """,
        (host_id, metric_name, severity, message)
    )
    
    alert_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    
    # Create alert dict for notification
    alert_data = {
        "id": alert_id,
        "host_id": host_id,
        "metric_name": metric_name,
        "severity": severity,
        "message": message,
        "status": "open",
        "created_at": datetime.now(timezone.utc)
    }
    
    # Send notification
    from backend.worker.notifications import log_alert
    log_alert(alert_data)
    
    return alert_id


async def process_host(host_id: int, conn) -> List[int]:
    """
    Lee métricas de la BD del host dado en las últimas ventanas:
    - Últimos 30s → avg_cpu_30
    - Últimos 60s → avg_cpu_60

    Calcula reglas y retorna lista de alert IDs creados.
    Inserta alerts en BD con status='open'.
    
    Args:
        host_id: Host identifier to process
        conn: Database connection
        
    Returns:
        List of alert IDs created
    """
    cursor = conn.cursor()
    
    # Query metrics from last 30 seconds
    # Use subquery to extract samples from JSONB
    cursor.execute(
        """
        SELECT (sample->>'value')::float as value
        FROM metrics_raw,
             jsonb_array_elements(payload->'samples') as sample
        WHERE host_id = %s
          AND sample->>'metric' = 'cpu_percent'
          AND created_at >= NOW() - INTERVAL '30 seconds'
        """,
        (host_id,)
    )
    
    cpu_values_30 = [row[0] for row in cursor.fetchall()]
    
    # Query metrics from last 60 seconds
    cursor.execute(
        """
        SELECT (sample->>'value')::float as value
        FROM metrics_raw,
             jsonb_array_elements(payload->'samples') as sample
        WHERE host_id = %s
          AND sample->>'metric' = 'cpu_percent'
          AND created_at >= NOW() - INTERVAL '60 seconds'
        """,
        (host_id,)
    )
    
    cpu_values_60 = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    
    logger.info(
        f"Host {host_id}: Found {len(cpu_values_30)} samples in 30s window, "
        f"{len(cpu_values_60)} samples in 60s window"
    )
    
    # Calculate averages
    avg_cpu_30 = sum(cpu_values_30) / len(cpu_values_30) if cpu_values_30 else 0
    avg_cpu_60 = sum(cpu_values_60) / len(cpu_values_60) if cpu_values_60 else 0
    
    logger.info(
        f"Host {host_id}: avg_cpu_30={avg_cpu_30:.2f}, "
        f"avg_cpu_60={avg_cpu_60:.2f}"
    )
    
    # Check rules and create alerts
    alerts_created = []
    
    # Rule 1: CPU over 90%
    alert_info = rule_cpu_over_90(avg_cpu_30)
    if alert_info:
        alert_id = await create_alert(
            conn,
            host_id,
            alert_info["metric"],
            alert_info["severity"],
            alert_info["message"]
        )
        alerts_created.append(alert_id)
    
    # Rule 2: CPU delta
    alert_info = rule_cpu_delta(avg_cpu_30, avg_cpu_60)
    if alert_info:
        alert_id = await create_alert(
            conn,
            host_id,
            alert_info["metric"],
            alert_info["severity"],
            alert_info["message"]
        )
        alerts_created.append(alert_id)
    
    return alerts_created
