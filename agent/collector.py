"""
AI Infra Monitor Agent - Collector Module

This module provides functions to collect system metrics.
For Historia 0.3, this is a mock implementation that returns simulated metrics.
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def collect_once() -> Dict[str, Any]:
    """
    Collect system metrics once.
    
    This is a mock implementation that returns simulated metrics.
    In a real implementation, this would collect actual system metrics
    using libraries like psutil.
    
    Returns:
        Dict[str, Any]: Dictionary containing mock system metrics
    """
    logger.info("Collecting metrics (mock mode)")
    
    # Mock metrics data
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "hostname": "mock-host",
        "cpu": {
            "usage_percent": 45.2,
            "cores": 8,
            "frequency_mhz": 2400
        },
        "memory": {
            "total_mb": 16384,
            "used_mb": 8192,
            "available_mb": 8192,
            "usage_percent": 50.0
        },
        "disk": {
            "total_gb": 512,
            "used_gb": 256,
            "free_gb": 256,
            "usage_percent": 50.0
        },
        "network": {
            "bytes_sent": 1048576,
            "bytes_recv": 2097152,
            "packets_sent": 1024,
            "packets_recv": 2048
        }
    }
    
    logger.info(f"Collected {len(metrics)} metric categories")
    return metrics
