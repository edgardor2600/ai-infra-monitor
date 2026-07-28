"""
Script to create or reset standard default admin user (admin@admin.com / admin123).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import psycopg2
from dotenv import load_dotenv
from backend.api.routes.auth import hash_password

load_dotenv()


def reset_admin():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor()

    email = "admin@admin.com"
    raw_password = "admin123"
    p_hash = hash_password(raw_password)

    # 1. Ensure default org exists
    cursor.execute("SELECT id FROM organizations WHERE id = 1;")
    org_row = cursor.fetchone()
    if not org_row:
        cursor.execute("INSERT INTO organizations (id, name, license_tier) VALUES (1, 'Organización Principal', 'pro_saas');")

    # 2. Upsert admin user
    cursor.execute("SELECT id FROM users WHERE email = %s;", (email,))
    user_row = cursor.fetchone()
    if user_row:
        cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s;", (p_hash, email))
        print(f"✓ Contraseña actualizada para {email}")
    else:
        cursor.execute("""
            INSERT INTO users (org_id, email, password_hash, role)
            VALUES (1, %s, %s, 'admin');
        """, (email, p_hash))
        print(f"✓ Usuario {email} creado exitosamente con contraseña '{raw_password}'.")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    reset_admin()
