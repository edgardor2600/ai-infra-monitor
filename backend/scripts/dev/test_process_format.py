"""
Test script to verify process data format matches the API model
"""
import json
import sys
import os
from datetime import datetime, timezone

# Add agent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent'))

from collector import collect_process_metrics

print("Collecting process metrics...")
processes = collect_process_metrics()

print(f"\nCollected {len(processes)} processes")
print("\nSample process data:")
if processes:
    print(json.dumps(processes[0], indent=2))
    
# Create a test batch
batch = {
    "host_id": 1,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "interval": 5,
    "samples": [
        {"metric": "cpu_percent", "value": 50.0},
        {"metric": "mem_percent", "value": 60.0}
    ],
    "processes": processes
}

print("\n\nTest batch structure:")
print(json.dumps(batch, indent=2))

# Try to validate against the Pydantic model
print("\n\nValidating against Pydantic model...")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from backend.api.models.ingest import IngestBatch
    
    # Try to create the model
    model = IngestBatch(**batch)
    print("✅ Validation successful!")
    print(f"\nModel dump:")
    print(json.dumps(model.model_dump(mode='json'), indent=2))
    
except Exception as e:
    print(f"❌ Validation failed: {e}")
    import traceback
    traceback.print_exc()
