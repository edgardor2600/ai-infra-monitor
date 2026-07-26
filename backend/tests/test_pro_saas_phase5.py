"""
Tests for Pro SaaS Phase 5: B2B License & Plans Management.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_get_license_info_endpoint():
    """Test GET /api/v1/disk-analyzer/license-info endpoint."""
    res = client.get("/api/v1/disk-analyzer/license-info")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "license_tier" in data
    assert "allowed_features" in data
    assert "active_llm_provider" in data


def test_activate_license_endpoint():
    """Test POST /api/v1/disk-analyzer/activate-license endpoint."""
    res = client.post("/api/v1/disk-analyzer/activate-license", json={"license_key": "ENTERPRISE-KEY-2026"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["license_tier"] == "ENTERPRISE"


def test_feature_gating_strict_enforcement():
    """Test that setting license to STARTER blocks audit-logs with HTTP 403 Forbidden."""
    # Set tier to STARTER
    res_act = client.post("/api/v1/disk-analyzer/activate-license", json={"license_key": "STARTER-KEY"})
    assert res_act.status_code == 200
    assert res_act.json()["license_tier"] == "STARTER"

    # Attempting audit-logs on STARTER should be HTTP 403
    res_audit = client.get("/api/v1/disk-analyzer/audit-logs")
    assert res_audit.status_code == 403
    assert "Acceso restringido" in res_audit.json()["detail"]

    # Restore tier to PRO_SAAS
    res_restore = client.post("/api/v1/disk-analyzer/activate-license", json={"license_key": "PRO-SAAS-KEY"})
    assert res_restore.status_code == 200
    assert res_restore.json()["license_tier"] == "PRO_SAAS"
