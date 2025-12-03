"""
Test script to verify process metrics collection
"""
import sys
import os

# Add agent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent'))

from collector import collect_process_metrics

print("Testing process metrics collection...")
processes = collect_process_metrics()

print(f"\nCollected {len(processes)} processes:")
for p in processes:
    print(f"  - {p['name']} (PID: {p['pid']}) - CPU: {p['cpu_percent']}%, Memory: {p['memory_mb']}MB, Status: {p['status']}")

if len(processes) == 0:
    print("\n⚠️  WARNING: No processes collected! This might be an issue.")
else:
    print(f"\n✅ Successfully collected {len(processes)} processes")
