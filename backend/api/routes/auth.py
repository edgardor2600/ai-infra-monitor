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

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_b2b_saas_key_2026_x99")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 7 * 24 * 3600 # 7 days


def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error in auth: {e}")
        return None


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


# --- Request Models ---

class RegisterRequest(BaseModel):
    organization_name: str = Field(..., description="Company or Organization Name")
    email: str = Field(..., description="Administrator Email")
    password: str = Field(..., description="Password (min 6 characters)")
    license_tier: Optional[str] = Field(default="pro_saas", description="Initial License Tier")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User Email")
    password: str = Field(..., description="Password")


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
            "organization_id": payload.get("org_id"),
            "organization_name": payload.get("org_name"),
            "license_tier": (payload.get("license_tier") or "PRO_SAAS").upper()
        }
    }
