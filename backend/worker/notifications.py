"""
AI Infra Monitor - Notifications Module

This module handles notifications for alerts.
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def log_alert(alert: Dict[str, Any]):
    """
    Logs the alert to the console in JSON format.
    
    Args:
        alert: Dictionary containing alert details
    """
    # Ensure request_id is present (simulated if not provided)
    if "request_id" not in alert:
        alert["request_id"] = "N/A"
        
    payload = json.dumps(alert, default=str)
    print(f"ALERT CREATED {payload}")
    logger.info(f"ALERT CREATED {payload}")
