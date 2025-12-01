"""
AI Infra Monitor - Worker Rules Module

This module contains alerting rules for the worker.
Each rule function checks specific conditions and returns alert information if triggered.
"""

from typing import Dict, Any, Optional


def rule_cpu_over_90(avg_30: float) -> Optional[Dict[str, Any]]:
    """
    Si avg_30 > 90, retornar dict con alert info.
    
    Args:
        avg_30: Average CPU percentage over last 30 seconds
        
    Returns:
        Dict with alert info if rule triggers, None otherwise
    """
    if avg_30 > 90:
        return {
            "metric": "cpu_percent",
            "severity": "HIGH",
            "message": f"CPU usage above 90% (avg 30s: {avg_30:.1f}%)"
        }
    return None


def rule_cpu_delta(avg_30: float, avg_60: float) -> Optional[Dict[str, Any]]:
    """
    delta = ((avg_30 - avg_60) / avg_60) * 100
    Si delta > 200%, retornar alert severity MEDIUM
    
    Args:
        avg_30: Average CPU percentage over last 30 seconds
        avg_60: Average CPU percentage over last 60 seconds
        
    Returns:
        Dict with alert info if rule triggers, None otherwise
    """
    if avg_60 == 0:
        # Avoid division by zero
        return None
    
    delta = ((avg_30 - avg_60) / avg_60) * 100
    
    if delta > 200:
        return {
            "metric": "cpu_percent",
            "severity": "MEDIUM",
            "message": f"CPU usage increased by {delta:.1f}% (30s avg: {avg_30:.1f}%, 60s avg: {avg_60:.1f}%)"
        }
    return None
