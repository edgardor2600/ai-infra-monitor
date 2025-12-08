"""
Quick test script for Disk Analyzer module

This script tests the basic functionality of the disk analyzer.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.disk_analyzer.scanner import DiskScanner
from backend.disk_analyzer.rules import CLEANUP_CATEGORIES

def test_scanner():
    """Test the disk scanner"""
    print("=" * 60)
    print("DISK ANALYZER MODULE TEST")
    print("=" * 60)
    print()
    
    print("1. Testing Cleanup Categories")
    print("-" * 60)
    print(f"Total categories defined: {len(CLEANUP_CATEGORIES)}")
    print()
    
    for name, category in CLEANUP_CATEGORIES.items():
        print(f"✓ {category.display_name}")
        print(f"  - Risk Level: {category.risk_level}")
        print(f"  - Safe Auto: {category.is_safe_auto}")
        print(f"  - Description: {category.description[:60]}...")
        print()
    
    print()
    print("2. Testing Scanner (Quick Scan)")
    print("-" * 60)
    
    scanner = DiskScanner(host_id=1)
    
    # Test a single safe category
    print("Scanning 'temp_files' category...")
    try:
        category = CLEANUP_CATEGORIES['temp_files']
        result = scanner._scan_category(category)
        
        print(f"✓ Scan completed successfully!")
        print(f"  - Files found: {result['file_count']}")
        print(f"  - Total size: {scanner._format_size(result['total_size'])}")
        print(f"  - Risk level: {result['risk_level']}")
        print()
        
        if result['files']:
            print("  Sample files (first 3):")
            for file_info in result['files'][:3]:
                print(f"    - {file_info['path'][:60]}... ({scanner._format_size(file_info['size'])})")
        
    except Exception as e:
        print(f"✗ Error during scan: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Start the backend: python -m uvicorn app.main:app --reload --port 8000")
    print("2. Navigate to: http://localhost:5173/disk-analyzer")
    print("3. Click 'Start New Scan' to see the full functionality")
    print()


if __name__ == "__main__":
    test_scanner()
