"""
AI Infra Monitor Agent - Collector Module

This module provides functions to collect system metrics using psutil.
"""

import logging
import psutil
from typing import Dict, Any

logger = logging.getLogger(__name__)


def collect_once() -> Dict[str, Any]:
    """
    Usa psutil para obtener métricas básicas.
    
    Devuelve un diccionario con:
    {
        "metric": "<nombre>",
        "value": <float|int>
    }
    
    Returns:
        Dict[str, Any]: Dictionary containing metric name and value
    """
    logger.info("Collecting metrics using psutil")
    
    # Collect CPU percentage (non-blocking, interval=1 for accuracy)
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Collect memory percentage
    mem_percent = psutil.virtual_memory().percent
    
    # Return as list of samples
    samples = [
        {"metric": "cpu_percent", "value": cpu_percent},
        {"metric": "mem_percent", "value": mem_percent}
    ]
    
    logger.info(f"Collected {len(samples)} metrics")
    return samples
