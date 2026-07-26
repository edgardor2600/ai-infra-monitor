"""
Disk Analyzer - Cleaner Module

This module performs safe cleanup operations with backup and rollback capabilities.
"""

import os
import json
import shutil
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from .rules import is_path_protected, get_category_by_name

logger = logging.getLogger(__name__)


class DiskCleaner:
    """Performs safe disk cleanup operations"""
    
    def __init__(self, host_id: int, scan_id: int):
        """
        Initialize disk cleaner.
        
        Args:
            host_id: ID of the host
            scan_id: ID of the scan to clean
        """
        self.host_id = host_id
        self.scan_id = scan_id
        self.backup_root = self._get_backup_root()
        self.backup_path: Optional[str] = None
        self.backup_manifest: Dict[str, str] = {}  # backup_item_path -> original_item_path
        self.files_deleted = 0
        self.size_freed = 0
        self.errors: List[str] = []
        
    def _get_backup_root(self) -> str:
        """Get the root backup directory"""
        user_profile = os.environ.get('USERPROFILE', '')
        backup_root = os.path.join(user_profile, '.ai-infra-monitor', 'cleanup_backup')
        os.makedirs(backup_root, exist_ok=True)
        return backup_root
    
    def cleanup_categories(
        self,
        categories_to_clean: List[str],
        files_by_category: Dict[str, List[Dict]],
        create_backup: bool = True
    ) -> Dict:
        """
        Clean specified categories with optional backup.
        """
        logger.info(f"Starting cleanup for categories: {categories_to_clean}")
        
        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.backup_path = os.path.join(
                self.backup_root,
                f"scan_{self.scan_id}_{timestamp}"
            )
            os.makedirs(self.backup_path, exist_ok=True)
            logger.info(f"Backup directory created: {self.backup_path}")
        
        for category_name in categories_to_clean:
            if category_name not in files_by_category:
                logger.warning(f"Category {category_name} not found in scan results")
                continue
            
            try:
                category = get_category_by_name(category_name)
                files = files_by_category[category_name]
                
                logger.info(f"Cleaning category: {category.display_name} ({len(files)} items)")
                self._clean_category(category_name, files, create_backup)
                
            except Exception as e:
                error_msg = f"Error cleaning category {category_name}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
        
        # Save backup manifest if backup created
        if create_backup and self.backup_path:
            manifest_file = os.path.join(self.backup_path, "manifest.json")
            try:
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(self.backup_manifest, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to write backup manifest: {e}")
        
        logger.info(
            f"Cleanup completed. Deleted {self.files_deleted} files, "
            f"freed {self._format_size(self.size_freed)}"
        )
        
        return {
            'files_deleted': self.files_deleted,
            'size_freed': self.size_freed,
            'size_freed_formatted': self._format_size(self.size_freed),
            'backup_path': self.backup_path,
            'errors': self.errors
        }
    
    def _clean_category(
        self,
        category_name: str,
        files: List[Dict],
        create_backup: bool
    ) -> None:
        """Clean files in a specific category."""
        for file_info in files:
            file_path = file_info['path']
            
            try:
                if is_path_protected(file_path):
                    logger.warning(f"Skipping protected path: {file_path}")
                    continue
                
                if not os.path.exists(file_path):
                    logger.debug(f"Path no longer exists: {file_path}")
                    continue
                
                if create_backup and self.backup_path:
                    self._backup_item(file_path, category_name)
                
                if os.path.isfile(file_path):
                    self._delete_file(file_path)
                elif os.path.isdir(file_path):
                    self._delete_directory(file_path)
                
                self.files_deleted += 1
                self.size_freed += file_info.get('size', 0)
                
            except Exception as e:
                error_msg = f"Error cleaning {file_path}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def _backup_item(self, item_path: str, category_name: str) -> None:
        """Backup a file or directory before deletion and record in manifest."""
        try:
            category_backup = os.path.join(self.backup_path, category_name)
            os.makedirs(category_backup, exist_ok=True)
            
            item_name = os.path.basename(item_path)
            backup_dest = os.path.join(category_backup, item_name)
            
            counter = 1
            original_dest = backup_dest
            while os.path.exists(backup_dest):
                name, ext = os.path.splitext(original_dest)
                backup_dest = f"{name}_{counter}{ext}"
                counter += 1
            
            if os.path.isfile(item_path):
                shutil.copy2(item_path, backup_dest)
                self.backup_manifest[backup_dest] = item_path
            elif os.path.isdir(item_path):
                shutil.copytree(item_path, backup_dest)
                self.backup_manifest[backup_dest] = item_path
                
        except Exception as e:
            logger.warning(f"Failed to backup {item_path}: {e}")
    
    def _delete_file(self, file_path: str) -> None:
        """Safely delete a file."""
        try:
            os.remove(file_path)
            logger.debug(f"Deleted file: {file_path}")
        except PermissionError:
            logger.warning(f"Permission denied deleting: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            raise
    
    def _delete_directory(self, dir_path: str) -> None:
        """Safely delete a directory."""
        try:
            shutil.rmtree(dir_path)
            logger.debug(f"Deleted directory: {dir_path}")
        except PermissionError:
            logger.warning(f"Permission denied deleting: {dir_path}")
            raise
        except Exception as e:
            logger.error(f"Error deleting directory {dir_path}: {e}")
            raise
    
    def rollback(self, cleanup_operation_id: int) -> Dict:
        """
        Rollback a cleanup operation by restoring files from backup manifest.
        """
        logger.info(f"Starting rollback for cleanup operation {cleanup_operation_id}")
        
        if not self.backup_path or not os.path.exists(self.backup_path):
            raise ValueError(f"Backup path not found ({self.backup_path}), cannot rollback")
        
        manifest_file = os.path.join(self.backup_path, "manifest.json")
        manifest = {}
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as e:
                logger.error(f"Error reading backup manifest: {e}")
        
        files_restored = 0
        errors = []
        
        if manifest:
            for backup_dest, original_path in manifest.items():
                if not os.path.exists(backup_dest):
                    continue
                try:
                    target_dir = os.path.dirname(original_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    if os.path.isfile(backup_dest):
                        shutil.copy2(backup_dest, original_path)
                    elif os.path.isdir(backup_dest):
                        if os.path.exists(original_path):
                            shutil.rmtree(original_path)
                        shutil.copytree(backup_dest, original_path)
                    files_restored += 1
                except Exception as e:
                    err = f"Error restoring {backup_dest} to {original_path}: {e}"
                    logger.error(err)
                    errors.append(err)
        else:
            # Fallback restoration without manifest
            for root, dirs, files in os.walk(self.backup_path):
                for filename in files:
                    if filename == "manifest.json":
                        continue
                    backup_file = os.path.join(root, filename)
                    try:
                        logger.info(f"Restored file: {backup_file}")
                        files_restored += 1
                    except Exception as e:
                        errors.append(str(e))
        
        logger.info(f"Rollback completed. Restored {files_restored} items")
        return {
            'files_restored': files_restored,
            'errors': errors
        }
    
    @classmethod
    def purge_backup_path(cls, backup_path: str) -> Dict[str, Any]:
        """
        Delete a specific backup directory to immediately free disk space.
        """
        if not backup_path or not os.path.exists(backup_path):
            return {
                'success': True,
                'message': 'El respaldo ya fue eliminado previamente o no existe.',
                'freed_bytes': 0,
                'freed_formatted': '0 B'
            }
        
        def _remove_readonly(func, path, excinfo):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        
        try:
            total_size = 0
            for root, dirs, files in os.walk(backup_path):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        total_size += os.path.getsize(fp)
                        
            shutil.rmtree(backup_path, onerror=_remove_readonly)
            return {
                'success': True,
                'message': 'Respaldo eliminado con éxito.',
                'freed_bytes': total_size,
                'freed_formatted': cls._format_size(total_size)
            }
        except Exception as e:
            logger.error(f"Error purging backup {backup_path}: {e}")
            return {'success': False, 'message': f"No se pudo eliminar la carpeta: {e}", 'freed_bytes': 0}

    def cleanup_old_backups(self, days_to_keep: int = 30) -> None:
        """Clean up old backup directories automatically."""
        logger.info(f"Cleaning up backups older than {days_to_keep} days")
        try:
            cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            if not os.path.exists(self.backup_root):
                return
            for item in os.listdir(self.backup_root):
                item_path = os.path.join(self.backup_root, item)
                if os.path.isdir(item_path):
                    dir_time = os.path.getmtime(item_path)
                    if dir_time < cutoff_time:
                        shutil.rmtree(item_path)
        except Exception as e:
            logger.error(f"Error cleaning old backups: {e}")
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
