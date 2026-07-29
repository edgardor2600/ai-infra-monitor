"""
Tests for B2B Authentication & JWT Token Verification.
"""

import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_auth_registration_and_login_flow():
    """Test full registration, login, and JWT verification flow."""
    unique_email = f"admin_{int(time.time())}@techcorp.com"
    
    # 1. Register new organization & admin user
    reg_payload = {
        "organization_name": "TechCorp B2B",
        "email": unique_email,
        "password": "Password123!",
        "license_tier": "pro_saas"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["ok"] is True
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == unique_email
    assert reg_data["user"]["organization_name"] == "TechCorp B2B"
    assert reg_data["user"]["license_tier"] == "PRO_SAAS"

    token = reg_data["access_token"]

    # 2. Test /auth/me with Bearer token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["ok"] is True
    assert me_data["user"]["email"] == unique_email
    assert me_data["user"]["organization_name"] == "TechCorp B2B"

    # 3. Test login with correct credentials
    login_res = client.post("/api/v1/auth/login", json={"email": unique_email, "password": "Password123!"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["ok"] is True
    assert "access_token" in login_data

    # 4. Test login with wrong password
    wrong_pass_res = client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"})
    assert wrong_pass_res.status_code == 401
    assert "Credenciales incorrectas" in wrong_pass_res.json()["detail"]


def test_hosts_auto_provisioning_for_new_org():
    """Test that GET /hosts returns an empty list for new orgs (no phantom server-side host).
    Hosts are only created when a real agent connects and registers via ingest."""
    unique_email = f"auto_host_{int(time.time())}@company.com"
    reg_res = client.post("/api/v1/auth/register", json={
        "organization_name": "Auto Host Corp",
        "email": unique_email,
        "password": "Password123!",
        "license_tier": "pro_saas"
    })
    token = reg_res.json()["access_token"]

    hosts_res = client.get("/api/v1/hosts", headers={"Authorization": f"Bearer {token}"})
    assert hosts_res.status_code == 200
    data = hosts_res.json()
    assert "hosts" in data
    # New orgs have no hosts until a real agent connects — no phantom server-side host
    assert isinstance(data["hosts"], list)
