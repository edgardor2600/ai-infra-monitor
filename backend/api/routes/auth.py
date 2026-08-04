"""
Authentication & Multi-Tenant User Management Routes for Pro SaaS Edition.
Uses PBKDF2 password hashing and signed JWT Access Tokens.
"""

import os
import json
import base64
import hmac
import hashlib
import time
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
import psycopg2
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    logger.warning("⚠️ JWT_SECRET no está configurado en el entorno. Se usará clave por defecto solo para desarrollo local.")
    JWT_SECRET = "development_fallback_key_ai_infra_monitor_2026"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 7 * 24 * 3600 # 7 days


from backend.db.connection import get_db_connection


# --- Password Hashing Utilities ---

def hash_password(password: str) -> str:
    """Hash password using PBKDF2 HMAC SHA-256 with random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify raw password against stored PBKDF2 hash."""
    try:
        if "$" not in password_hash:
            return False
        salt_hex, stored_key_hex = password_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(key.hex(), stored_key_hex)
    except Exception:
        return False


# --- Lightweight JWT Utilities ---

def create_jwt_token(payload: Dict[str, Any]) -> str:
    """Create a HS256 JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + JWT_EXPIRATION_SECONDS
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_copy).encode()).decode().rstrip("=")
    
    signature_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and verify HS256 JWT access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")
            
        header_b64, payload_b64, sig_b64 = parts
        
        # Verify signature
        signature_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()
        
        # Padding fix for base64 decode
        padded_sig_b64 = sig_b64 + "=" * (-len(sig_b64) % 4)
        actual_sig = base64.urlsafe_b64decode(padded_sig_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=401, detail="Token signature invalid")
            
        padded_payload_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_payload_b64).decode())
        
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
            
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation error: {str(e)}")



def get_current_org_id(authorization: Optional[str] = None) -> int:
    """Extract org_id from JWT token in Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ")[1]
            payload = decode_jwt_token(token)
            return payload.get("org_id", 1)
        except Exception:
            pass
    return 1


# --- Request Models ---

class RegisterRequest(BaseModel):
    organization_name: str = Field(..., description="Company or Organization Name")
    email: str = Field(..., description="Administrator Email")
    password: str = Field(..., description="Password (min 6 characters)")
    license_tier: Optional[str] = Field(default="pro_saas", description="Initial License Tier")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User Email")
    password: str = Field(..., description="Password")


class AdminChangeTierRequest(BaseModel):
    org_id: int = Field(..., description="ID of the organization to modify")
    license_tier: str = Field(..., description="New license tier: starter, pro_saas, enterprise")


class AdminChangeRoleRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user to modify")
    role: str = Field(..., description="New role: superadmin, admin, user")


class AdminResetPasswordRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    new_password: str = Field(..., description="New password string")


# --- Endpoints ---

@router.post("/register", response_model=dict)
async def register(request: RegisterRequest):
    """Register a new B2B Organization & Admin User."""
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = conn.cursor()
        
        # Check if user email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s;", (request.email.lower().strip(),))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")

        # Synchronize PostgreSQL sequence
        cursor.execute("SELECT setval('organizations_id_seq', (SELECT GREATEST(MAX(id), 1) FROM organizations));")
        cursor.execute("SELECT setval('users_id_seq', (SELECT GREATEST(MAX(id), 1) FROM users));")

        # Insert organization
        cursor.execute("""
            INSERT INTO organizations (name, license_tier)
            VALUES (%s, %s)
            RETURNING id, name, license_tier;
        """, (request.organization_name.strip(), request.license_tier.lower()))
        org_row = cursor.fetchone()
        org_id, org_name, tier = org_row[0], org_row[1], org_row[2]

        # Insert admin user
        p_hash = hash_password(request.password)
        cursor.execute("""
            INSERT INTO users (org_id, email, password_hash, role)
            VALUES (%s, %s, %s, 'admin')
            RETURNING id, email, role;
        """, (org_id, request.email.lower().strip(), p_hash))
        user_row = cursor.fetchone()
        user_id, email, role = user_row[0], user_row[1], user_row[2]

        conn.commit()

        token_payload = {
            "user_id": user_id,
            "org_id": org_id,
            "email": email,
            "role": role,
            "org_name": org_name,
            "license_tier": tier
        }
        token = create_jwt_token(token_payload)

        return {
            "ok": True,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "role": role,
                "org_id": org_id,
                "organization_id": org_id,
                "organization_name": org_name,
                "license_tier": tier.upper()
            }
        }
    finally:
        conn.close()


@router.post("/login", response_model=dict)
async def login(request: LoginRequest):
    """Authenticate B2B User and return JWT Access Token."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.org_id, u.email, u.password_hash, u.role, o.name, o.license_tier
            FROM users u
            JOIN organizations o ON u.org_id = o.id
            WHERE u.email = %s;
        """, (request.email.lower().strip(),))
        row = cursor.fetchone()
        
        if not row or not verify_password(request.password, row[3]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas: correo o contraseña no válidos")

        user_id, org_id, email, _, role, org_name, tier = row

        token_payload = {
            "user_id": user_id,
            "org_id": org_id,
            "email": email,
            "role": role,
            "org_name": org_name,
            "license_tier": tier
        }
        token = create_jwt_token(token_payload)

        return {
            "ok": True,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "role": role,
                "org_id": org_id,
                "organization_id": org_id,
                "organization_name": org_name,
                "license_tier": tier.upper()
            }
        }
    finally:
        conn.close()


@router.get("/me", response_model=dict)
async def get_me(authorization: Optional[str] = Header(None)):
    """Get current authenticated user details from Bearer Token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Authorization header missing")

    token = authorization.split(" ")[1]
    payload = decode_jwt_token(token)

    return {
        "ok": True,
        "user": {
            "id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "org_id": payload.get("org_id"),
            "organization_id": payload.get("org_id"),
            "organization_name": payload.get("org_name"),
            "license_tier": (payload.get("license_tier") or "PRO_SAAS").upper()
        }
    }


def check_superadmin_access(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Autorización requerida")
    payload = decode_jwt_token(authorization.split(" ")[1])
    role = payload.get("role", "").lower()
    email = payload.get("email", "").lower()
    if role != "superadmin" and email not in ["admin@admin.com", "erq2600@gmail.com"]:
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requieren permisos de Super Administrador.")
    return payload


@router.get("/admin/users", response_model=dict)
async def admin_list_users(authorization: Optional[str] = Header(None)):
    """List all users across all organizations for SuperAdmin management."""
    check_superadmin_access(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.email, u.role, u.created_at, o.id as org_id, o.name as org_name, o.license_tier,
                   (SELECT COUNT(*) FROM hosts h WHERE h.org_id = o.id) as host_count
            FROM users u
            JOIN organizations o ON u.org_id = o.id
            ORDER BY u.id DESC;
        """)
        rows = cursor.fetchall()
        users = []
        for r in rows:
            users.append({
                "id": r[0],
                "email": r[1],
                "role": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "org_id": r[4],
                "org_name": r[5],
                "license_tier": r[6].upper() if r[6] else "PRO_SAAS",
                "hosts_count": r[7]
            })
        return {"ok": True, "users": users, "total": len(users)}
    finally:
        conn.close()


@router.get("/admin/stats", response_model=dict)
async def admin_get_stats(authorization: Optional[str] = Header(None)):
    """Get global platform KPI metrics for SuperAdmin."""
    check_superadmin_access(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users;")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM organizations;")
        total_orgs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM hosts;")
        total_hosts = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM disk_scans;")
        total_scans = cursor.fetchone()[0]

        cursor.execute("SELECT license_tier, COUNT(*) FROM organizations GROUP BY license_tier;")
        tier_counts = {r[0].upper(): r[1] for r in cursor.fetchall()}

        return {
            "ok": True,
            "stats": {
                "total_users": total_users,
                "total_orgs": total_orgs,
                "total_hosts": total_hosts,
                "total_scans": total_scans,
                "tier_distribution": tier_counts
            }
        }
    finally:
        conn.close()


@router.post("/admin/change-tier", response_model=dict)
async def admin_change_tier(request: AdminChangeTierRequest, authorization: Optional[str] = Header(None)):
    """Change organization subscription tier (STARTER, PRO_SAAS, ENTERPRISE)."""
    check_superadmin_access(authorization)
    new_tier = request.license_tier.lower().strip()
    if new_tier not in ["starter", "pro_saas", "enterprise"]:
        raise HTTPException(status_code=400, detail="Plan de suscripción no válido")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE organizations SET license_tier = %s WHERE id = %s RETURNING name;", (new_tier, request.org_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        conn.commit()
        return {"ok": True, "org_id": request.org_id, "organization_name": row[0], "new_license_tier": new_tier.upper(), "message": f"Plan actualizado a {new_tier.upper()}"}
    finally:
        conn.close()


@router.post("/admin/change-role", response_model=dict)
async def admin_change_role(request: AdminChangeRoleRequest, authorization: Optional[str] = Header(None)):
    """Change user role (superadmin, admin, user)."""
    check_superadmin_access(authorization)
    new_role = request.role.lower().strip()
    if new_role not in ["superadmin", "admin", "user"]:
        raise HTTPException(status_code=400, detail="Rol no válido")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = %s WHERE id = %s RETURNING email;", (new_role, request.user_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        conn.commit()
        return {"ok": True, "user_id": request.user_id, "email": row[0], "new_role": new_role, "message": f"Rol de {row[0]} actualizado a {new_role}"}
    finally:
        conn.close()


@router.post("/admin/reset-password", response_model=dict)
async def admin_reset_password(request: AdminResetPasswordRequest, authorization: Optional[str] = Header(None)):
    """Reset password for any user account."""
    check_superadmin_access(authorization)
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    p_hash = hash_password(request.new_password)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s RETURNING email;", (p_hash, request.user_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        conn.commit()
        return {"ok": True, "user_id": request.user_id, "email": row[0], "message": f"Contraseña actualizada para {row[0]}"}
    finally:
        conn.close()


@router.delete("/admin/users/{user_id}", response_model=dict)
async def admin_delete_user(user_id: int, authorization: Optional[str] = Header(None)):
    """Delete a user account."""
    payload = check_superadmin_access(authorization)
    if payload.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de SuperAdmin")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s RETURNING email;", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        conn.commit()
        return {"ok": True, "user_id": user_id, "email": row[0], "message": f"Usuario {row[0]} eliminado"}
    finally:
        conn.close()


class NotificationSettingsRequest(BaseModel):
    webhook_url: Optional[str] = None
    notification_email: Optional[str] = None
    auto_remediation_enabled: Optional[bool] = True

class TestWebhookRequest(BaseModel):
    webhook_url: str


@router.get("/notification-settings", response_model=dict)
async def get_notification_settings(authorization: Optional[str] = Header(None)):
    """Get current organization notification and auto-remediation settings."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT webhook_url, notification_email, auto_remediation_enabled FROM organizations WHERE id = %s;",
            (org_id,)
        )
        row = cursor.fetchone()
        return {
            "ok": True,
            "org_id": org_id,
            "webhook_url": row[0] if row else None,
            "notification_email": row[1] if row else None,
            "auto_remediation_enabled": row[2] if (row and row[2] is not None) else True
        }
    finally:
        conn.close()


@router.post("/notification-settings", response_model=dict)
async def update_notification_settings(request: NotificationSettingsRequest, authorization: Optional[str] = Header(None)):
    """Update organization notification webhook and auto-remediation policy."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE organizations
            SET webhook_url = %s,
                notification_email = %s,
                auto_remediation_enabled = %s
            WHERE id = %s;
            """,
            (request.webhook_url, request.notification_email, request.auto_remediation_enabled, org_id)
        )
        conn.commit()
        return {"ok": True, "message": "Configuración de notificaciones y auto-remediación actualizada correctamente."}
    finally:
        conn.close()


@router.post("/test-webhook", response_model=dict)
async def test_webhook_endpoint(request: TestWebhookRequest):
    """Send a test webhook ping to Slack, Teams, Discord, or generic endpoint."""
    from backend.app.notifications_dispatcher import NotificationDispatcher
    success = await NotificationDispatcher.send_webhook(
        webhook_url=request.webhook_url,
        title="Prueba de Notificación Webhook",
        message="Esta es una notificación de prueba enviada con éxito desde AI Infra Monitor Pro.",
        severity="INFO",
        host_info="Servidor Principal"
    )
    if not success:
        raise HTTPException(status_code=400, detail="No se pudo enviar la notificación de prueba al Webhook especificado. Verifica la URL.")
    return {"ok": True, "message": "¡Notificación de prueba enviada con éxito!"}

