"""
Test script to verify process monitoring functionality.

This script tests:
1. Process collection from psutil
2. Database insertion
3. API endpoint retrieval
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from agent.collector import collect_process_metrics
import psycopg2
from dotenv import load_dotenv
import requests

load_dotenv()

def test_process_collection():
    """Test 1: Verify process collection works"""
    print("=" * 60)
    print("TEST 1: Process Collection")
    print("=" * 60)
    
    processes = collect_process_metrics()
    
    if not processes:
        print("❌ FAIL: No processes collected!")
        return False
    
    print(f"✅ SUCCESS: Collected {len(processes)} processes")
    print("\nSample processes:")
    for i, proc in enumerate(processes[:5], 1):
        print(f"  {i}. {proc['name']} (PID: {proc['pid']}) - CPU: {proc['cpu_percent']}%, RAM: {proc['memory_mb']} MB")
    
    return True


def test_database_insertion():
    """Test 2: Insert test data into database"""
    print("\n" + "=" * 60)
    print("TEST 2: Database Insertion")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        cursor = conn.cursor()
        
        # Insert a test process metric
        cursor.execute(
            """
            INSERT INTO process_metrics 
            (host_id, process_name, pid, cpu_percent, memory_mb, status, created_at)
            VALUES (1, 'test_process.exe', 12345, 25.5, 512.0, 'running', NOW())
            RETURNING id
            """)
        
        test_id = cursor.fetchone()[0]
        conn.commit()
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM process_metrics")
        count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print(f"✅ SUCCESS: Inserted test record (ID: {test_id})")
        print(f"   Total process_metrics records: {count}")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Database error: {e}")
        return False


def test_api_endpoint():
    """Test 3: Verify API endpoint returns data"""
    print("\n" + "=" * 60)
    print("TEST 3: API Endpoint")
    print("=" * 60)
    
    try:
        url = "http://localhost:8000/api/v1/processes/top?host_id=1&limit=10&metric=cpu"
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            print(f"❌ FAIL: API returned status {response.status_code}")
            return False
        
        data = response.json()
        
        if not isinstance(data, list):
            print(f"❌ FAIL: Expected list, got {type(data)}")
            return False
        
        print(f"✅ SUCCESS: API returned {len(data)} processes")
        
        if data:
            print("\nTop processes from API:")
            for i, proc in enumerate(data[:5], 1):
                print(f"  {i}. {proc['process_name']} - CPU: {proc['cpu_percent']}%, RAM: {proc['memory_mb']} MB")
        else:
            print("⚠️  WARNING: API returned empty list (this is OK if agent hasn't sent data yet)")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ FAIL: Cannot connect to backend (is it running on port 8000?)")
        return False
    except Exception as e:
        print(f"❌ FAIL: API error: {e}")
        return False


def check_agent_logs():
    """Test 4: Provide instructions for checking agent logs"""
    print("\n" + "=" * 60)
    print("TEST 4: Agent Log Check")
    print("=" * 60)
    
    print("""
To verify the agent is collecting processes, check the agent terminal for:

1. Every 60 seconds, you should see:
   "Collected X process metrics - will send with next batch"

2. When batch is sent (every 20 seconds by default):
   "Including X process metrics in batch"

If you don't see these messages:
- The agent might not be running
- The agent might have crashed
- Check for errors in the agent terminal
""")


if __name__ == "__main__":
    print("\n🔍 PROCESS MONITORING DIAGNOSTIC TESTS\n")
    
    results = []
    
    # Run tests
    results.append(("Process Collection", test_process_collection()))
    results.append(("Database Insertion", test_database_insertion()))
    results.append(("API Endpoint", test_api_endpoint()))
    check_agent_logs()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        print("\nNext steps:")
        print("1. Restart the agent: python -m agent run")
        print("2. Wait 60 seconds for first process collection")
        print("3. Check dashboard at: http://localhost:5173/hosts/1/processes")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    sys.exit(0 if all_passed else 1)
