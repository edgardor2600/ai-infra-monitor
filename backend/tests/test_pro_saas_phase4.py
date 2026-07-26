"""
Tests for Pro SaaS Phase 4: Dev/Media Artifacts, Audit Logs, and Backup Purge Notifications.
"""

import tempfile
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_scan_dev_artifacts_endpoint():
    """Test POST /api/v1/disk-analyzer/scan-dev-artifacts endpoint."""
    client.post("/api/v1/disk-analyzer/activate-license", json={"license_key": "PRO-SAAS-KEY"})
    with tempfile.TemporaryDirectory() as temp_dir:
        res = client.post("/api/v1/disk-analyzer/scan-dev-artifacts", json={"target_path": temp_dir})
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert "total_artifacts" in data
        assert "artifacts" in data


def test_audit_logs_endpoint():
    """Test GET /api/v1/disk-analyzer/audit-logs endpoint under ENTERPRISE license."""
    client.post("/api/v1/disk-analyzer/activate-license", json={"license_key": "ENTERPRISE-KEY-2026"})
    res = client.get("/api/v1/disk-analyzer/audit-logs")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert isinstance(data["logs"], list)


def test_backup_purge_notifications_endpoint():
    """Test GET /api/v1/disk-analyzer/backup-purge-notifications endpoint."""
    res = client.get("/api/v1/disk-analyzer/backup-purge-notifications")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert isinstance(data["pending_purges"], list)
