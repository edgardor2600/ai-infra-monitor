"""
Disk Analyzer - Scanner Module

This module scans the disk and identifies files that can be cleaned.
"""

import os
import logging
import psutil
import shutil
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from .rules import (
    CLEANUP_CATEGORIES,
    SAFE_TEMP_EXTENSIONS,
    INSTALLER_EXTENSIONS,
    is_path_protected,
    is_file_old_enough,
    get_age_category,
    get_category_by_name
)

logger = logging.getLogger(__name__)


class DiskScanner:
    """Scans disk for files that can be cleaned"""
    
    def __init__(self, host_id: int, drive: str = "C:"):
        """
        Initialize disk scanner.
        
        Args:
            host_id: ID of the host being scanned
            drive: Target drive letter (e.g., "C:", "D:")
        """
        self.host_id = host_id
        self.drive = drive.upper().rstrip("\\").rstrip("/")
        if not self.drive.endswith(":"):
            self.drive += ":"
        self.drive_root = self.drive + "\\"
        
        self.scan_results: Dict[str, List[Dict]] = {}
        self.total_size = 0

    @staticmethod
    def get_available_drives() -> List[Dict[str, any]]:
        """Get information on all fixed drives on the system."""
        drives = []
        try:
            partitions = psutil.disk_partitions(all=False)
            for part in partitions:
                if 'cdrom' in part.opts or part.fstype == '':
                    continue
                try:
                    usage = shutil.disk_usage(part.mountpoint)
                    drives.append({
                        'device': part.device,
                        'mountpoint': part.mountpoint,
                        'fstype': part.fstype,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'used_percent': round((usage.used / usage.total) * 100, 2)
                    })
                except (PermissionError, OSError):
                    continue
        except Exception as e:
            logger.error(f"Error enumerating drives: {e}")
            # Fallback to C:
            try:
                usage = shutil.disk_usage("C:\\")
                drives.append({
                    'device': 'C:',
                    'mountpoint': 'C:\\',
                    'fstype': 'NTFS',
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'used_percent': round((usage.used / usage.total) * 100, 2)
                })
            except Exception:
                pass
        return drives

    def scan_all_categories(self) -> Dict[str, any]:
        """Scan all cleanup categories on target drive."""
        logger.info(f"Starting full disk scan for host {self.host_id} on drive {self.drive}")
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
        
        total_size = sum(cat['total_size'] for cat in results.values())
        total_files = sum(cat['file_count'] for cat in results.values())
        
        disk_info = self._get_disk_info()
        
        logger.info(f"Scan completed on {self.drive}. Found {total_files} files, {self._format_size(total_size)} total")
        
        return {
            'categories': results,
            'total_size': total_size,
            'total_files': total_files,
            'total_size_formatted': self._format_size(total_size),
            'disk_info': disk_info,
            'drive': self.drive,
            'scanned_at': datetime.now().isoformat()
        }

    def _get_disk_info(self) -> Dict[str, any]:
        """Get disk space information for target drive"""
        try:
            total, used, free = shutil.disk_usage(self.drive_root)
            return {
                'drive': self.drive,
                'total': total,
                'used': used,
                'free': free,
                'used_percent': round((used / total) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Error getting disk info for {self.drive_root}: {e}")
            return {
                'drive': self.drive,
                'total': 0,
                'used': 0,
                'free': 0,
                'used_percent': 0
            }

    def _scan_category(self, category) -> Dict:
        """Scan a specific category without artificial length limits."""
        files = []
        total_size = 0
        paths_to_scan = category.get_paths()
        
        for base_path in paths_to_scan:
            # Filter paths by target drive
            if not base_path.upper().startswith(self.drive):
                continue
                
            if not os.path.exists(base_path):
                continue
            
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
            elif category.name == 'pkg_managers':
                category_files = self._scan_pkg_managers(base_path)
            elif category.name == 'system_logs':
                category_files = self._scan_system_logs(base_path)
            elif category.name == 'dev_cache':
                category_files = self._scan_dev_cache(base_path)
            else:
                category_files = []
            
            files.extend(category_files)
            total_size += sum(f['size'] for f in category_files)
        
        return {
            'files': files,  # Unlimited items for complete disk clean
            'total_size': total_size,
            'total_size_formatted': self._format_size(total_size),
            'file_count': len(files),
            'display_name': category.display_name,
            'description': category.description,
            'risk_level': category.risk_level,
            'is_safe_auto': category.is_safe_auto
        }

    def _scan_temp_files(self, base_path: str) -> List[Dict]:
        """Scan temporary files recursively"""
        files = []
        try:
            for root, dirs, filenames in os.walk(base_path):
                if is_path_protected(root):
                    continue
                
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        if not os.path.isfile(file_path) or is_path_protected(file_path):
                            continue
                        
                        stat_info = os.stat(file_path)
                        file_size = stat_info.st_size
                        last_mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        age_cat = get_age_category(file_path)
                        
                        files.append({
                            'path': file_path,
                            'size': file_size,
                            'last_accessed': last_mtime.isoformat(),
                            'age_category': age_cat,
                            'is_safe': True,
                            'risk_level': 'low'
                        })
                    except (PermissionError, OSError):
                        continue
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
                        if not os.path.isfile(file_path) or is_path_protected(file_path):
                            continue
                        
                        stat_info = os.stat(file_path)
                        file_size = stat_info.st_size
                        last_mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        age_cat = get_age_category(file_path)
                        
                        files.append({
                            'path': file_path,
                            'size': file_size,
                            'last_accessed': last_mtime.isoformat(),
                            'age_category': age_cat,
                            'is_safe': True,
                            'risk_level': 'low'
                        })
                    except (PermissionError, OSError):
                        continue
        except Exception as e:
            logger.error(f"Error scanning browser cache in {base_path}: {e}")
        return files

    def _scan_recycle_bin(self, base_path: str) -> List[Dict]:
        """Scan recycle bin"""
        files = []
        try:
            if os.path.exists(base_path):
                for root, dirs, filenames in os.walk(base_path):
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        try:
                            if os.path.isfile(file_path):
                                stat_info = os.stat(file_path)
                                files.append({
                                    'path': file_path,
                                    'size': stat_info.st_size,
                                    'last_accessed': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                                    'age_category': get_age_category(file_path),
                                    'is_safe': True,
                                    'risk_level': 'low'
                                })
                        except (PermissionError, OSError):
                            continue
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
                        if not os.path.isfile(file_path) or is_path_protected(file_path):
                            continue
                        
                        stat_info = os.stat(file_path)
                        files.append({
                            'path': file_path,
                            'size': stat_info.st_size,
                            'last_accessed': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                            'age_category': get_age_category(file_path),
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
            if os.path.exists(base_path):
                for filename in os.listdir(base_path):
                    file_path = os.path.join(base_path, filename)
                    if not os.path.isfile(file_path) or is_path_protected(file_path):
                        continue
                    
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in INSTALLER_EXTENSIONS and is_file_old_enough(file_path, days=30):
                        try:
                            stat_info = os.stat(file_path)
                            files.append({
                                'path': file_path,
                                'size': stat_info.st_size,
                                'last_accessed': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                                'age_category': get_age_category(file_path),
                                'is_safe': False,
                                'risk_level': 'medium'
                            })
                        except (PermissionError, OSError):
                            continue
        except Exception as e:
            logger.error(f"Error scanning installers in {base_path}: {e}")
        return files

    def _scan_pkg_managers(self, base_path: str) -> List[Dict]:
        """Scan package manager cache directories"""
        files = []
        try:
            for root, dirs, filenames in os.walk(base_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        if os.path.isfile(file_path):
                            stat_info = os.stat(file_path)
                            files.append({
                                'path': file_path,
                                'size': stat_info.st_size,
                                'last_accessed': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                                'age_category': get_age_category(file_path),
                                'is_safe': False,
                                'risk_level': 'medium'
                            })
                    except (PermissionError, OSError):
                        continue
        except Exception as e:
            logger.error(f"Error scanning package manager cache in {base_path}: {e}")
        return files

    def _scan_system_logs(self, base_path: str) -> List[Dict]:
        """Scan system log and crash dump files"""
        files = []
        try:
            for root, dirs, filenames in os.walk(base_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        if os.path.isfile(file_path) and is_file_old_enough(file_path, days=14):
                            stat_info = os.stat(file_path)
                            files.append({
                                'path': file_path,
                                'size': stat_info.st_size,
                                'last_accessed': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                                'age_category': get_age_category(file_path),
                                'is_safe': False,
                                'risk_level': 'medium'
                            })
                    except (PermissionError, OSError):
                        continue
        except Exception as e:
            logger.error(f"Error scanning logs in {base_path}: {e}")
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
                            if os.path.isfile(file_path):
                                stat_info = os.stat(file_path)
                                files.append({
                                    'path': file_path,
                                    'size': stat_info.st_size,
                                    'last_accessed': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                                    'age_category': get_age_category(file_path),
                                    'is_safe': True,
                                    'risk_level': 'low'
                                })
                        except (PermissionError, OSError):
                            continue
        except Exception as e:
            logger.error(f"Error scanning thumbnails: {e}")
        return files

    def _scan_dev_cache(self, base_path: str) -> List[Dict]:
        """Scan development cache directories (node_modules, __pycache__, etc.)"""
        files = []
        cache_dirs = {'node_modules', '__pycache__', '.cache', '.next', 'dist', 'build', '.venv', 'venv', 'target'}
        try:
            for root, dirs, filenames in os.walk(base_path):
                dir_name = os.path.basename(root)
                if dir_name in cache_dirs:
                    try:
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
                            'age_category': get_age_category(root),
                            'is_safe': False,
                            'risk_level': 'high'
                        })
                        dirs.clear()
                    except (PermissionError, OSError):
                        continue
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
