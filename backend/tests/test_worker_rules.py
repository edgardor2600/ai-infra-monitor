"""
Tests for worker rules
"""

import pytest
from backend.worker.rules import rule_cpu_over_90, rule_cpu_delta


def test_cpu_over_90_triggers():
    """
    Test that rule_cpu_over_90 triggers when avg_30 > 90
    """
    # avg_30 = 92 → alert severity HIGH
    result = rule_cpu_over_90(92.0)
    
    assert result is not None
    assert result["metric"] == "cpu_percent"
    assert result["severity"] == "HIGH"
    assert "CPU usage above 90%" in result["message"]
    assert "92.0%" in result["message"]


def test_cpu_over_90_no_trigger():
    """
    Test that rule_cpu_over_90 does not trigger when avg_30 <= 90
    """
    # avg_30 = 50 → no alert
    result = rule_cpu_over_90(50.0)
    assert result is None
    
    # Edge case: exactly 90
    result = rule_cpu_over_90(90.0)
    assert result is None


def test_cpu_delta_triggers():
    """
    Test that rule_cpu_delta triggers when delta > 200%
    """
    # avg_30 = 90, avg_60 = 20 → delta = 350% → alert MEDIUM
    result = rule_cpu_delta(90.0, 20.0)
    
    assert result is not None
    assert result["metric"] == "cpu_percent"
    assert result["severity"] == "MEDIUM"
    assert "increased" in result["message"].lower()
    assert "350" in result["message"]


def test_cpu_delta_no_trigger():
    """
    Test that rule_cpu_delta does not trigger when delta <= 200%
    """
    # avg_30 = 40, avg_60 = 30 → delta = 33.3% → no alert
    result = rule_cpu_delta(40.0, 30.0)
    assert result is None
    
    # Edge case: exactly 200%
    result = rule_cpu_delta(60.0, 20.0)
    assert result is None


def test_cpu_delta_zero_division():
    """
    Test that rule_cpu_delta handles division by zero gracefully
    """
    # avg_60 = 0 → should not crash
    result = rule_cpu_delta(50.0, 0.0)
    assert result is None


def test_cpu_delta_negative_values():
    """
    Test that rule_cpu_delta handles negative deltas (CPU decrease)
    """
    # avg_30 = 20, avg_60 = 80 → delta = -75% → no alert
    result = rule_cpu_delta(20.0, 80.0)
    assert result is None
