"""
Script to purge synthetic test alerts, old process metrics, and test analyses
from PostgreSQL database so the system presents a 100% clean, fresh dashboard.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def purge_data():
    print("Cleaning synthetic test alerts and old data...")
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        cursor = conn.cursor()

        # 1. Truncate alerts and analyses
        cursor.execute("TRUNCATE TABLE analyses CASCADE;")
        cursor.execute("TRUNCATE TABLE alerts CASCADE;")
        print("✓ Cleared synthetic alerts and analyses tables.")

        # 2. Reset sequences
        cursor.execute("ALTER SEQUENCE alerts_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE analyses_id_seq RESTART WITH 1;")

        conn.commit()
        cursor.close()
        print("✓ Database alerts reset cleanly to 0!")

    except Exception as e:
        print(f"❌ Error purging synthetic data: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    purge_data()
