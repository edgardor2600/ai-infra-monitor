"""
Tests for SuperAdmin Management Endpoints (/auth/admin/users, /auth/admin/stats, /auth/admin/change-tier).
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.api.routes.auth import (
    create_jwt_token,
    decode_jwt_token,
    check_superadmin_access
)
from fastapi import HTTPException


def test_superadmin_access_validation():
    """Verify check_superadmin_access grants access to superadmin and denies regular users."""
    super_token = create_jwt_token({
        "user_id": 1,
        "email": "admin@admin.com",
        "role": "superadmin",
        "org_id": 1
    })

    user_token = create_jwt_token({
        "user_id": 2,
        "email": "user@company.com",
        "role": "user",
        "org_id": 2
    })

    # Valid SuperAdmin token
    payload = check_superadmin_access(f"Bearer {super_token}")
    assert payload["role"] == "superadmin"

    # Regular user token should raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        check_superadmin_access(f"Bearer {user_token}")
    assert exc_info.value.status_code == 403
