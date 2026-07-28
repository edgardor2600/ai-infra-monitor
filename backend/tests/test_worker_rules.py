"""
Tests for Intelligent Alert Rules Engine v2.
"""

import pytest
from backend.worker.rules import (
    rule_cpu_sustained,
    rule_cpu_anomaly_spike,
    rule_memory_critical,
    rule_disk_critical,
    rule_host_silent,
    RuleResult
)


def test_rule_cpu_sustained_triggers():
    """Test rule_cpu_sustained triggers when 3min average >= 85%."""
    res = rule_cpu_sustained(avg_30s=92.0, avg_180s=88.0)
    assert res is not None
    assert isinstance(res, RuleResult)
    assert res.rule_name == "cpu_sustained"
    assert res.severity == "HIGH"
    assert "88.0%" in res.message


def test_rule_cpu_sustained_no_trigger():
    """Test rule_cpu_sustained does not trigger for momentary spikes (<85% 3min avg)."""
    res = rule_cpu_sustained(avg_30s=95.0, avg_180s=60.0)
    assert res is None


def test_rule_cpu_anomaly_spike():
    """Test rule_cpu_anomaly_spike triggers on 200%+ increase over low baseline."""
    res = rule_cpu_anomaly_spike(avg_30s=90.0, baseline_avg=20.0)
    assert res is not None
    assert res.rule_name == "cpu_anomaly_spike"
    assert res.severity == "MEDIUM"
    assert "+350%" in res.message


def test_rule_memory_critical():
    """Test rule_memory_critical triggers when memory usage > 90% and free MB < 500."""
    res = rule_memory_critical(mem_used_pct=92.0, mem_free_mb=300.0)
    assert res is not None
    assert res.severity == "HIGH"


def test_rule_disk_critical():
    """Test rule_disk_critical triggers when disk usage >= 95% or free GB < 5.0."""
    res = rule_disk_critical(disk_used_pct=96.0, disk_free_gb=3.0, drive="C:")
    assert res is not None
    assert res.severity == "HIGH" or res.severity == "CRITICAL"


def test_rule_host_silent():
    """Test rule_host_silent triggers when agent is silent for 5+ minutes."""
    res = rule_host_silent(minutes_since_last_metric=5.0)
    assert res is not None
    assert res.rule_name == "host_silent"
    assert res.severity == "HIGH"
