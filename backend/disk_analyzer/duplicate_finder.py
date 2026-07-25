"""
SHA-256 Duplicate File Finder Engine (Zero-Copy Deduplication).
Uses a fast 2-stage hashing algorithm (exact size -> 4KB sample hash -> full SHA-256).
"""

import os
import hashlib
from typing import Dict, List, Any


class DuplicateFinder:
    """Finds exact duplicate files across directories or drives efficiently."""

    def __init__(self, min_file_size_bytes: int = 1048576): # Default min 1MB
        self.min_file_size_bytes = min_file_size_bytes

    def calculate_file_hash(self, filepath: str, sample_only: bool = False) -> str:
        """Calculate SHA-256 hash (or 4KB sample hash for rapid elimination)."""
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                if sample_only:
                    chunk = f.read(4096)
                    hasher.update(chunk)
                else:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, OSError):
            return ""

    def scan_directory_for_duplicates(self, target_path: str) -> Dict[str, Any]:
        """
        Scan target directory for duplicate files.
        
        Returns:
            Dict containing duplicate groups, total waste size, and count.
        """
        size_groups: Dict[int, List[str]] = {}
        
        # 1. Group files by exact size
        for root, _, files in os.walk(target_path):
            for file in files:
                try:
                    filepath = os.path.join(root, file)
                    if os.path.isfile(filepath):
                        size = os.path.getsize(filepath)
                        if size >= self.min_file_size_bytes:
                            size_groups.setdefault(size, []).append(filepath)
                except (PermissionError, OSError):
                    continue

        # Filter sizes with at least 2 files
        potential_sizes = {sz: paths for sz, paths in size_groups.items() if len(paths) > 1}
        
        # 2. Stage 2: 4KB Sample Hash
        sample_hash_groups: Dict[str, List[str]] = {}
        for size, paths in potential_sizes.items():
            for path in paths:
                s_hash = self.calculate_file_hash(path, sample_only=True)
                if s_hash:
                    key = f"{size}_{s_hash}"
                    sample_hash_groups.setdefault(key, []).append(path)

        potential_samples = {key: paths for key, paths in sample_hash_groups.items() if len(paths) > 1}

        # 3. Stage 3: Full SHA-256 Hash
        full_hash_groups: Dict[str, List[str]] = {}
        for paths in potential_samples.values():
            for path in paths:
                full_hash = self.calculate_file_hash(path, sample_only=False)
                if full_hash:
                    full_hash_groups.setdefault(full_hash, []).append(path)

        # Build final duplicates report
        duplicate_sets = []
        total_wasted_bytes = 0
        total_duplicate_files = 0

        for f_hash, paths in full_hash_groups.items():
            if len(paths) > 1:
                # Sort by modification time (newest first)
                sorted_paths = sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)
                original_file = sorted_paths[0]
                duplicates = sorted_paths[1:]
                
                file_size = os.path.getsize(original_file)
                wasted = file_size * len(duplicates)
                
                total_wasted_bytes += wasted
                total_duplicate_files += len(duplicates)

                duplicate_sets.append({
                    "sha256": f_hash,
                    "original_path": original_file,
                    "duplicate_paths": duplicates,
                    "file_size_bytes": file_size,
                    "wasted_bytes": wasted,
                    "file_count": len(paths)
                })

        return {
            "duplicate_sets": duplicate_sets,
            "total_wasted_bytes": total_wasted_bytes,
            "total_duplicate_files": total_duplicate_files
        }
