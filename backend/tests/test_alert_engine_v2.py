"""
Tests — Alert Engine v2 & Intelligent Rules

Covers:
  - All 7 rule functions with boundary conditions
  - AlertEngine deduplication behavior
  - AlertEngine auto-resolution behavior
  - Alerts API enriched endpoints
"""

import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.worker.rules import (
    rule_cpu_sustained,
    rule_cpu_anomaly_spike,
    rule_memory_critical,
    rule_memory_high_sustained,
    rule_disk_critical,
    rule_disk_trend_runaway,
    rule_host_silent,
    evaluate_all_rules,
)
from backend.worker.alert_engine import (
    AlertEngine,
    SEVERITY_ORDER,
    _is_condition_resolved,
)

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Rule Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCPUSustainedRule:
    def test_does_not_fire_below_threshold(self):
        result = rule_cpu_sustained(avg_30s=75.0, avg_180s=72.0)
        assert result is None

    def test_fires_high_at_85_pct(self):
        result = rule_cpu_sustained(avg_30s=88.0, avg_180s=87.0)
        assert result is not None
        assert result.severity == "HIGH"
        assert result.rule_name == "cpu_sustained"

    def test_escalates_to_critical_at_95_pct(self):
        result = rule_cpu_sustained(avg_30s=97.0, avg_180s=96.0)
        assert result is not None
        assert result.severity == "CRITICAL"

    def test_no_history_returns_none(self):
        result = rule_cpu_sustained(avg_30s=99.0, avg_180s=0.0)
        assert result is None


class TestCPUAnomalySpikeRule:
    def test_fires_on_large_spike(self):
        result = rule_cpu_anomaly_spike(avg_30s=85.0, baseline_avg=20.0)
        assert result is not None
        assert result.severity == "MEDIUM"
        assert "spike" in result.rule_name

    def test_does_not_fire_when_baseline_is_high(self):
        result = rule_cpu_anomaly_spike(avg_30s=90.0, baseline_avg=70.0)
        assert result is None

    def test_does_not_fire_below_200_pct_delta(self):
        result = rule_cpu_anomaly_spike(avg_30s=45.0, baseline_avg=20.0)
        assert result is None


class TestMemoryRules:
    def test_memory_critical_above_92_pct(self):
        result = rule_memory_critical(mem_used_pct=94.0, mem_free_mb=1024)
        assert result is not None
        assert result.severity in ("HIGH", "CRITICAL")
        assert result.rule_name == "memory_critical"

    def test_memory_critical_on_low_free_mb(self):
        result = rule_memory_critical(mem_used_pct=80.0, mem_free_mb=150)
        assert result is not None

    def test_memory_normal_returns_none(self):
        result = rule_memory_critical(mem_used_pct=70.0, mem_free_mb=4096)
        assert result is None

    def test_memory_high_sustained_fires(self):
        result = rule_memory_high_sustained(avg_mem_5min=88.0)
        assert result is not None
        assert result.severity == "MEDIUM"

    def test_memory_high_sustained_normal(self):
        result = rule_memory_high_sustained(avg_mem_5min=75.0)
        assert result is None


class TestDiskRules:
    def test_disk_critical_on_high_usage(self):
        result = rule_disk_critical(disk_used_pct=97.0, disk_free_gb=3.0)
        assert result is not None
        assert result.severity in ("HIGH", "CRITICAL")

    def test_disk_critical_on_low_free_gb(self):
        result = rule_disk_critical(disk_used_pct=70.0, disk_free_gb=2.0)
        assert result is not None

    def test_disk_normal_returns_none(self):
        result = rule_disk_critical(disk_used_pct=60.0, disk_free_gb=50.0)
        assert result is None

    def test_disk_trend_runaway_fires(self):
        result = rule_disk_trend_runaway(free_gb_now=40.0, free_gb_24h_ago=55.0)
        assert result is not None
        assert result.actual_value == pytest.approx(15.0)

    def test_disk_trend_normal(self):
        result = rule_disk_trend_runaway(free_gb_now=49.0, free_gb_24h_ago=50.0)
        assert result is None


class TestHostSilentRule:
    def test_fires_after_5_minutes(self):
        result = rule_host_silent(minutes_since_last_metric=6.0)
        assert result is not None
        assert result.severity == "HIGH"

    def test_escalates_after_15_minutes(self):
        result = rule_host_silent(minutes_since_last_metric=20.0)
        assert result is not None
        assert result.severity == "CRITICAL"

    def test_does_not_fire_when_active(self):
        result = rule_host_silent(minutes_since_last_metric=1.0)
        assert result is None


class TestEvaluateAllRules:
    def test_all_normal_returns_empty(self):
        metrics = {
            "avg_cpu_30s": 20, "avg_cpu_180s": 18, "avg_cpu_baseline": 22,
            "mem_used_pct": 50, "mem_free_mb": 8000, "avg_mem_5min": 48,
            "disk_used_pct": 40, "disk_free_gb": 100, "disk_free_gb_24h": 101,
            "minutes_silent": 0.5,
        }
        results = evaluate_all_rules(metrics)
        assert len(results) == 0

    def test_multiple_conditions_returns_all(self):
        metrics = {
            "avg_cpu_30s": 97, "avg_cpu_180s": 96, "avg_cpu_baseline": 25,
            "mem_used_pct": 94, "mem_free_mb": 200, "avg_mem_5min": 91,
            "disk_used_pct": 97, "disk_free_gb": 1.5, "disk_free_gb_24h": 15,
            "minutes_silent": 0,
        }
        results = evaluate_all_rules(metrics)
        assert len(results) >= 3  # cpu_sustained + memory + disk at minimum


# ─────────────────────────────────────────────────────────────────────────────
# AlertEngine Logic Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSeverityOrder:
    def test_severity_ordering_is_correct(self):
        assert SEVERITY_ORDER["CRITICAL"] > SEVERITY_ORDER["HIGH"]
        assert SEVERITY_ORDER["HIGH"] > SEVERITY_ORDER["MEDIUM"]
        assert SEVERITY_ORDER["MEDIUM"] > SEVERITY_ORDER["LOW"]
        assert SEVERITY_ORDER["LOW"] > SEVERITY_ORDER["INFO"]


class TestConditionResolution:
    def test_cpu_resolves_when_below_75(self):
        assert _is_condition_resolved("cpu_sustained", {"avg_cpu_180s": 70.0}) is True
        assert _is_condition_resolved("cpu_sustained", {"avg_cpu_180s": 80.0}) is False

    def test_memory_resolves_when_below_85(self):
        assert _is_condition_resolved("memory_critical", {"mem_used_pct": 80.0}) is True
        assert _is_condition_resolved("memory_critical", {"mem_used_pct": 90.0}) is False

    def test_disk_resolves_when_free_above_8gb(self):
        assert _is_condition_resolved("disk_critical", {"disk_free_gb": 10.0}) is True
        assert _is_condition_resolved("disk_critical", {"disk_free_gb": 3.0}) is False

    def test_host_silent_resolves_when_active(self):
        assert _is_condition_resolved("host_silent", {"minutes_silent": 1.0}) is True
        assert _is_condition_resolved("host_silent", {"minutes_silent": 8.0}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Alerts API Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAlertsAPIv2:
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Create a test user and get auth token."""
        email = f"alerts_test_{int(time.time())}@test.com"
        res = client.post("/api/v1/auth/register", json={
            "organization_name": "Alert Test Org",
            "email": email,
            "password": "Password123!",
            "license_tier": "pro_saas",
        })
        self.token = res.json().get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_get_alerts_returns_ok(self):
        res = client.get("/api/v1/alerts", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert "alerts" in data
        assert "total" in data

    def test_get_alerts_summary_returns_health_score(self):
        res = client.get("/api/v1/alerts/summary", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100
        assert "by_severity" in data
        assert "resolved_today" in data

    def test_get_incidents_returns_ok(self):
        res = client.get("/api/v1/incidents", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert "incidents" in data
