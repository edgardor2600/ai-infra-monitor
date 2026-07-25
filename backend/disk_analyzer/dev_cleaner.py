"""
Specialized Cleaners for Developers & Content Creators (Pro Edition).
Cleans Docker, Gradle, Xcode, Rust, Node.js, Python, Premiere, Photoshop caches safely.
"""

import os
import time
from typing import Dict, List, Any


class DevMediaCleaner:
    """Specialized cleaning engine for Developer & Multimedia caches."""

    def __init__(self, host_drive: str = "C:"):
        self.host_drive = host_drive

    def scan_dev_artifacts(self, base_dir: str) -> Dict[str, Any]:
        """Scan developer project build artifacts."""
        target_dirs = ["node_modules", "__pycache__", ".venv", ".next", "dist", "build", "target"]
        found_artifacts = []
        total_size = 0

        for root, dirs, _ in os.walk(base_dir):
            for d in list(dirs):
                if d in target_dirs:
                    full_path = os.path.join(root, d)
                    try:
                        dir_size = self._get_dir_size(full_path)
                        total_size += dir_size
                        found_artifacts.append({
                            "type": d,
                            "path": full_path,
                            "size_bytes": dir_size
                        })
                    except (PermissionError, OSError):
                        pass

        return {
            "category": "developer_artifacts",
            "total_artifacts": len(found_artifacts),
            "total_size_bytes": total_size,
            "artifacts": found_artifacts
        }

    def scan_media_cache(self) -> Dict[str, Any]:
        """Scan Adobe Photoshop / Premiere media caches."""
        user_profile = os.environ.get("USERPROFILE", "")
        media_paths = [
            os.path.join(user_profile, r"AppData\Roaming\Adobe\Common\Media Cache Files"),
            os.path.join(user_profile, r"AppData\Local\Temp\Adobe")
        ]
        
        found_files = []
        total_size = 0

        for m_path in media_paths:
            if os.path.exists(m_path):
                for root, _, files in os.walk(m_path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            total_size += sz
                            found_files.append({"path": fp, "size": sz})
                        except (PermissionError, OSError):
                            pass

        return {
            "category": "media_editing_cache",
            "total_files": len(found_files),
            "total_size_bytes": total_size,
            "files": found_files
        }

    def _get_dir_size(self, path: str) -> int:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        total += os.path.getsize(fp)
                except (PermissionError, OSError):
                    pass
        return total
