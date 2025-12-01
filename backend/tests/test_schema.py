"""
Database Schema Tests

Tests to verify the database schema is correctly initialized.
"""

import os
import pytest
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@pytest.fixture
def db_connection():
    """
    Create a database connection for testing.
    
    Yields:
        psycopg2.connection: Database connection
    """
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    yield conn
    conn.close()


def test_database_connection(db_connection):
    """
    Test that we can connect to the database.
    
    Args:
        db_connection: Database connection fixture
    """
    assert db_connection is not None
    assert not db_connection.closed


def test_hosts_table_exists(db_connection):
    """
    Test that the hosts table exists.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'hosts'
        );
    """)
    exists = cursor.fetchone()[0]
    cursor.close()
    assert exists, "hosts table does not exist"


def test_metrics_table_exists(db_connection):
    """
    Test that the metrics table exists.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'metrics'
        );
    """)
    exists = cursor.fetchone()[0]
    cursor.close()
    assert exists, "metrics table does not exist"


def test_alerts_table_exists(db_connection):
    """
    Test that the alerts table exists.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'alerts'
        );
    """)
    exists = cursor.fetchone()[0]
    cursor.close()
    assert exists, "alerts table does not exist"


def test_analyses_table_exists(db_connection):
    """
    Test that the analyses table exists.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'analyses'
        );
    """)
    exists = cursor.fetchone()[0]
    cursor.close()
    assert exists, "analyses table does not exist"


def test_all_tables_exist(db_connection):
    """
    Test that all required tables exist.
    
    Args:
        db_connection: Database connection fixture
    """
    required_tables = ['hosts', 'metrics', 'alerts', 'analyses']
    
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    existing_tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    
    for table in required_tables:
        assert table in existing_tables, f"Required table '{table}' is missing"


def test_hosts_table_structure(db_connection):
    """
    Test that the hosts table has the correct structure.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'hosts'
        ORDER BY ordinal_position;
    """)
    columns = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    
    assert 'id' in columns
    assert 'hostname' in columns
    assert 'created_at' in columns
    assert columns['hostname'] == 'text'
    assert 'timestamp' in columns['created_at']


def test_metrics_table_structure(db_connection):
    """
    Test that the metrics table has the correct structure.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'metrics'
        ORDER BY ordinal_position;
    """)
    columns = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    
    assert 'id' in columns
    assert 'host_id' in columns
    assert 'payload' in columns
    assert 'created_at' in columns
    assert columns['payload'] == 'jsonb'


def test_foreign_key_constraints(db_connection):
    """
    Test that foreign key constraints exist.
    
    Args:
        db_connection: Database connection fixture
    """
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT 
            tc.table_name, 
            kcu.column_name,
            ccu.table_name AS foreign_table_name
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public';
    """)
    foreign_keys = cursor.fetchall()
    cursor.close()
    
    # Should have foreign keys from metrics, alerts, and analyses to hosts
    fk_tables = [fk[0] for fk in foreign_keys]
    assert 'metrics' in fk_tables
    assert 'alerts' in fk_tables
    assert 'analyses' in fk_tables
