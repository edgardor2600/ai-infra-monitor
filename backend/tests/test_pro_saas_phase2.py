"""
Tests for Pro SaaS Phase 2: DuplicateFinder by SHA-256 and DevMediaCleaner.
"""

import os
import tempfile
import pytest

from backend.disk_analyzer.duplicate_finder import DuplicateFinder
from backend.disk_analyzer.dev_cleaner import DevMediaCleaner


def test_duplicate_finder():
    """Test duplicate detection by SHA-256."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file1 = os.path.join(temp_dir, "doc1.txt")
        file2 = os.path.join(temp_dir, "doc2_copy.txt")
        file3 = os.path.join(temp_dir, "unique.txt")
        
        content = "Exact duplicate content " * 10000 # Make > 100KB
        
        with open(file1, "w") as f:
            f.write(content)
        with open(file2, "w") as f:
            f.write(content)
        with open(file3, "w") as f:
            f.write("Different content completely")
            
        finder = DuplicateFinder(min_file_size_bytes=100)
        res = finder.scan_directory_for_duplicates(temp_dir)
        
        assert res["total_duplicate_files"] == 1
        assert res["total_wasted_bytes"] > 0
        assert len(res["duplicate_sets"]) == 1
        assert res["duplicate_sets"][0]["file_count"] == 2


def test_dev_cleaner_artifacts():
    """Test developer project artifact scanner."""
    with tempfile.TemporaryDirectory() as temp_dir:
        node_dir = os.path.join(temp_dir, "node_modules")
        os.makedirs(node_dir, exist_ok=True)
        with open(os.path.join(node_dir, "package.json"), "w") as f:
            f.write("{}")
            
        cleaner = DevMediaCleaner()
        res = cleaner.scan_dev_artifacts(temp_dir)
        
        assert res["category"] == "developer_artifacts"
        assert res["total_artifacts"] == 1
        assert res["artifacts"][0]["type"] == "node_modules"
