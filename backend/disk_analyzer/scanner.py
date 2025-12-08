"""
Disk Analyzer - Scanner Module

This module scans the disk and identifies files that can be cleaned.
"""

import os
import logging
import hashlib
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

from .rules import (
    CLEANUP_CATEGORIES,
    SAFE_TEMP_EXTENSIONS,
    INSTALLER_EXTENSIONS,
    is_path_protected,
    is_file_old_enough,
    get_category_by_name
)

logger = logging.getLogger(__name__)


class DiskScanner:
    """Scans disk for files that can be cleaned"""
    
    def __init__(self, host_id: int):
        """
        Initialize disk scanner.
        
        Args:
            host_id: ID of the host being scanned
        """
        self.host_id = host_id
        self.scan_results: Dict[str, List[Dict]] = {}
        self.total_size = 0
        
    def scan_all_categories(self) -> Dict[str, any]:
        """
        Scan all cleanup categories.
        
        Returns:
            Dictionary with scan results for each category
        """
        logger.info(f"Starting disk scan for host {self.host_id}")
        results = {}
        
        for category_name, category in CLEANUP_CATEGORIES.items():
            try:
                logger.info(f"Scanning category: {category.display_name}")
                category_results = self._scan_category(category)
                results[category_name] = category_results
            except Exception as e:
                logger.error(f"Error scanning category {category_name}: {e}")
                results[category_name] = {
                    'files': [],
                    'total_size': 0,
                    'file_count': 0,
                    'error': str(e)
                }
        
        # Calculate total
        total_size = sum(cat['total_size'] for cat in results.values())
        total_files = sum(cat['file_count'] for cat in results.values())
        
        # Get disk space information
        disk_info = self._get_disk_info()
        
        logger.info(f"Scan completed. Found {total_files} files, {self._format_size(total_size)} total")
        
        return {
            'categories': results,
            'total_size': total_size,
            'total_files': total_files,
            'disk_info': disk_info,
            'scanned_at': datetime.now().isoformat()
        }
    
    def _get_disk_info(self) -> Dict[str, int]:
        """Get disk space information for C: drive"""
        try:
            import shutil
            total, used, free = shutil.disk_usage("C:\\")
            return {
                'total': total,
                'used': used,
                'free': free,
                'used_percent': round((used / total) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Error getting disk info: {e}")
            return {
                'total': 0,
                'used': 0,
                'free': 0,
                'used_percent': 0
            }
    
    def _scan_category(self, category) -> Dict:
        """
        Scan a specific category.
        
        Args:
            category: CleanupCategory to scan
            
        Returns:
            Dictionary with scan results
        """
        files = []
        total_size = 0
        
        # Get paths to scan for this category
        paths_to_scan = category.get_paths()
        
        for base_path in paths_to_scan:
            if not os.path.exists(base_path):
                logger.debug(f"Path does not exist: {base_path}")
                continue
            
            # Scan based on category type
            if category.name == 'temp_files':
                category_files = self._scan_temp_files(base_path)
            elif category.name == 'browser_cache':
                category_files = self._scan_browser_cache(base_path)
            elif category.name == 'recycle_bin':
                category_files = self._scan_recycle_bin(base_path)
            elif category.name == 'windows_update':
                category_files = self._scan_windows_update(base_path)
            elif category.name == 'installers':
                category_files = self._scan_installers(base_path)
            elif category.name == 'thumbnails':
                category_files = self._scan_thumbnails(base_path)
            elif category.name == 'dev_cache':
                category_files = self._scan_dev_cache(base_path)
            else:
                category_files = []
            
            files.extend(category_files)
            total_size += sum(f['size'] for f in category_files)
        
        return {
            'files': files[:100],  # Limit to 100 files for performance
            'total_size': total_size,
            'file_count': len(files),
            'display_name': category.display_name,
            'description': category.description,
            'risk_level': category.risk_level,
            'is_safe_auto': category.is_safe_auto
        }
    
    def _scan_temp_files(self, base_path: str) -> List[Dict]:
        """Scan temporary files"""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(base_path):
                # Skip protected directories
                if is_path_protected(root):
                    continue
                
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    
                    try:
                        # Check if file is accessible
                        if not os.path.isfile(file_path):
                            continue
                        
                        # Get file info
                        stat_info = os.stat(file_path)
                        file_size = stat_info.st_size
                        last_accessed = datetime.fromtimestamp(stat_info.st_atime)
                        
                        # Only include files older than 7 days
                        if not is_file_old_enough(file_path, days=7):
                            continue
                        
                        files.append({
                            'path': file_path,
                            'size': file_size,
                            'last_accessed': last_accessed.isoformat(),
                            'is_safe': True,
                            'risk_level': 'low'
                        })
                        
                    except (PermissionError, OSError) as e:
                        logger.debug(f"Cannot access file {file_path}: {e}")
                        continue
                
                # Limit depth to avoid very long scans
                if len(root.split(os.sep)) - len(base_path.split(os.sep)) > 3:
                    dirs.clear()
                    
        except Exception as e:
            logger.error(f"Error scanning temp files in {base_path}: {e}")
        
        return files
    
    def _scan_browser_cache(self, base_path: str) -> List[Dict]:
        """Scan browser cache files"""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(base_path):
                if is_path_protected(root):
                    continue
                
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    
                    try:
                        if not os.path.isfile(file_path):
                            continue
                        
                        stat_info = os.stat(file_path)
                        file_size = stat_info.st_size
                        last_accessed = datetime.fromtimestamp(stat_info.st_atime)
                        
                        files.append({
                            'path': file_path,
                            'size': file_size,
                            'last_accessed': last_accessed.isoformat(),
                            'is_safe': True,
                            'risk_level': 'low'
                        })
                        
                    except (PermissionError, OSError):
                        continue
                
                # Limit depth
                if len(root.split(os.sep)) - len(base_path.split(os.sep)) > 2:
                    dirs.clear()
                    
        except Exception as e:
            logger.error(f"Error scanning browser cache in {base_path}: {e}")
        
        return files
    
    def _scan_recycle_bin(self, base_path: str) -> List[Dict]:
        """Scan recycle bin"""
        files = []
        total_size = 0
        
        try:
            # For recycle bin, we'll estimate size
            # Actual implementation would require Windows API
            import shutil
            if os.path.exists(base_path):
                total_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(base_path)
                    for filename in filenames
                    if os.path.isfile(os.path.join(dirpath, filename))
                )
                
                files.append({
                    'path': base_path,
                    'size': total_size,
                    'last_accessed': datetime.now().isoformat(),
                    'is_safe': True,
                    'risk_level': 'low'
                })
        except Exception as e:
            logger.error(f"Error scanning recycle bin: {e}")
        
        return files
    
    def _scan_windows_update(self, base_path: str) -> List[Dict]:
        """Scan Windows Update cache"""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(base_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    
                    try:
                        if not os.path.isfile(file_path):
                            continue
                        
                        stat_info = os.stat(file_path)
                        file_size = stat_info.st_size
                        last_accessed = datetime.fromtimestamp(stat_info.st_atime)
                        
                        # Only old update files
                        if is_file_old_enough(file_path, days=30):
                            files.append({
                                'path': file_path,
                                'size': file_size,
                                'last_accessed': last_accessed.isoformat(),
                                'is_safe': True,
                                'risk_level': 'low'
                            })
                        
                    except (PermissionError, OSError):
                        continue
                        
        except Exception as e:
            logger.error(f"Error scanning Windows Update cache: {e}")
        
        return files
    
    def _scan_installers(self, base_path: str) -> List[Dict]:
        """Scan for old installer files"""
        files = []
        
        try:
            for filename in os.listdir(base_path):
                file_path = os.path.join(base_path, filename)
                
                if not os.path.isfile(file_path):
                    continue
                
                # Check if it's an installer
                _, ext = os.path.splitext(filename)
                if ext.lower() not in INSTALLER_EXTENSIONS:
                    continue
                
                try:
                    stat_info = os.stat(file_path)
                    file_size = stat_info.st_size
                    last_accessed = datetime.fromtimestamp(stat_info.st_atime)
                    
                    # Only installers older than 30 days
                    if is_file_old_enough(file_path, days=30):
                        files.append({
                            'path': file_path,
                            'size': file_size,
                            'last_accessed': last_accessed.isoformat(),
                            'is_safe': False,  # User should review
                            'risk_level': 'medium'
                        })
                    
                except (PermissionError, OSError):
                    continue
                    
        except Exception as e:
            logger.error(f"Error scanning installers in {base_path}: {e}")
        
        return files
    
    def _scan_thumbnails(self, base_path: str) -> List[Dict]:
        """Scan thumbnail cache"""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(base_path):
                for filename in filenames:
                    if filename.startswith('thumbcache') or filename.endswith('.db'):
                        file_path = os.path.join(root, filename)
                        
                        try:
                            if not os.path.isfile(file_path):
                                continue
                            
                            stat_info = os.stat(file_path)
                            file_size = stat_info.st_size
                            last_accessed = datetime.fromtimestamp(stat_info.st_atime)
                            
                            files.append({
                                'path': file_path,
                                'size': file_size,
                                'last_accessed': last_accessed.isoformat(),
                                'is_safe': True,
                                'risk_level': 'low'
                            })
                            
                        except (PermissionError, OSError):
                            continue
                            
        except Exception as e:
            logger.error(f"Error scanning thumbnails: {e}")
        
        return files
    
    def _scan_dev_cache(self, base_path: str) -> List[Dict]:
        """Scan development cache directories"""
        files = []
        cache_dirs = ['node_modules', '__pycache__', '.cache', '.next', 'dist', 'build']
        
        try:
            for root, dirs, filenames in os.walk(base_path):
                # Check if current directory is a cache directory
                dir_name = os.path.basename(root)
                if dir_name in cache_dirs:
                    try:
                        # Calculate directory size
                        dir_size = sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, dirnames, filenames_inner in os.walk(root)
                            for filename in filenames_inner
                            if os.path.isfile(os.path.join(dirpath, filename))
                        )
                        
                        files.append({
                            'path': root,
                            'size': dir_size,
                            'last_accessed': datetime.now().isoformat(),
                            'is_safe': False,  # Requires confirmation
                            'risk_level': 'high'
                        })
                        
                        # Don't recurse into this directory
                        dirs.clear()
                        
                    except (PermissionError, OSError):
                        continue
                
                # Limit depth to avoid very long scans
                if len(root.split(os.sep)) - len(base_path.split(os.sep)) > 4:
                    dirs.clear()
                    
        except Exception as e:
            logger.error(f"Error scanning dev cache in {base_path}: {e}")
        
        return files
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
