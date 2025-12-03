import requests
import json
from datetime import datetime, timezone

url = "http://localhost:8000/api/v1/ingest/metrics"
payload = {
    "host_id": 1,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "interval": 5,
    "samples": [
        {"metric": "cpu_percent", "value": 50.0},
        {"metric": "mem_percent", "value": 60.0}
    ]
}

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
