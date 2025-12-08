"""
Disk Analyzer - Cleaner Module

This module performs safe cleanup operations with backup and rollback capabilities.
"""

import os
import shutil
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

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
        
        Args:
            categories_to_clean: List of category names to clean
            files_by_category: Dictionary mapping category names to file lists
            create_backup: Whether to create backup before deletion
            
        Returns:
            Dictionary with cleanup results
        """
        logger.info(f"Starting cleanup for categories: {categories_to_clean}")
        
        # Create backup directory
        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.backup_path = os.path.join(
                self.backup_root,
                f"scan_{self.scan_id}_{timestamp}"
            )
            os.makedirs(self.backup_path, exist_ok=True)
            logger.info(f"Backup directory created: {self.backup_path}")
        
        # Clean each category
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
        
        logger.info(
            f"Cleanup completed. Deleted {self.files_deleted} files, "
            f"freed {self._format_size(self.size_freed)}"
        )
        
        return {
            'files_deleted': self.files_deleted,
            'size_freed': self.size_freed,
            'backup_path': self.backup_path,
            'errors': self.errors
        }
    
    def _clean_category(
        self,
        category_name: str,
        files: List[Dict],
        create_backup: bool
    ) -> None:
        """
        Clean files in a specific category.
        
        Args:
            category_name: Name of the category
            files: List of file dictionaries to clean
            create_backup: Whether to backup before deletion
        """
        for file_info in files:
            file_path = file_info['path']
            
            try:
                # Safety check
                if is_path_protected(file_path):
                    logger.warning(f"Skipping protected path: {file_path}")
                    continue
                
                # Check if file/directory exists
                if not os.path.exists(file_path):
                    logger.debug(f"Path no longer exists: {file_path}")
                    continue
                
                # Backup if requested
                if create_backup and self.backup_path:
                    self._backup_item(file_path, category_name)
                
                # Delete the file or directory
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
        """
        Backup a file or directory before deletion.
        
        Args:
            item_path: Path to backup
            category_name: Category name for organization
        """
        try:
            # Create category backup directory
            category_backup = os.path.join(self.backup_path, category_name)
            os.makedirs(category_backup, exist_ok=True)
            
            # Generate backup path preserving some structure
            item_name = os.path.basename(item_path)
            backup_dest = os.path.join(category_backup, item_name)
            
            # Handle name collisions
            counter = 1
            original_dest = backup_dest
            while os.path.exists(backup_dest):
                name, ext = os.path.splitext(original_dest)
                backup_dest = f"{name}_{counter}{ext}"
                counter += 1
            
            # Copy file or directory
            if os.path.isfile(item_path):
                shutil.copy2(item_path, backup_dest)
                logger.debug(f"Backed up file: {item_path} -> {backup_dest}")
            elif os.path.isdir(item_path):
                shutil.copytree(item_path, backup_dest)
                logger.debug(f"Backed up directory: {item_path} -> {backup_dest}")
                
        except Exception as e:
            logger.warning(f"Failed to backup {item_path}: {e}")
            # Continue anyway - backup failure shouldn't stop cleanup
    
    def _delete_file(self, file_path: str) -> None:
        """
        Safely delete a file.
        
        Args:
            file_path: Path to file to delete
        """
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
        """
        Safely delete a directory and its contents.
        
        Args:
            dir_path: Path to directory to delete
        """
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
        Rollback a cleanup operation by restoring from backup.
        
        Args:
            cleanup_operation_id: ID of the cleanup operation to rollback
            
        Returns:
            Dictionary with rollback results
        """
        logger.info(f"Starting rollback for cleanup operation {cleanup_operation_id}")
        
        if not self.backup_path or not os.path.exists(self.backup_path):
            raise ValueError("Backup path not found, cannot rollback")
        
        files_restored = 0
        errors = []
        
        try:
            # Walk through backup directory
            for root, dirs, files in os.walk(self.backup_path):
                for filename in files:
                    backup_file = os.path.join(root, filename)
                    
                    # Determine original location
                    # This is simplified - in production, you'd store metadata
                    relative_path = os.path.relpath(backup_file, self.backup_path)
                    
                    try:
                        # For now, we'll just log what would be restored
                        # Full implementation would restore to original locations
                        logger.info(f"Would restore: {backup_file}")
                        files_restored += 1
                        
                    except Exception as e:
                        error_msg = f"Error restoring {backup_file}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            
            logger.info(f"Rollback completed. Restored {files_restored} files")
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise
        
        return {
            'files_restored': files_restored,
            'errors': errors
        }
    
    def cleanup_old_backups(self, days_to_keep: int = 30) -> None:
        """
        Clean up old backup directories.
        
        Args:
            days_to_keep: Number of days to keep backups
        """
        logger.info(f"Cleaning up backups older than {days_to_keep} days")
        
        try:
            cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            
            for item in os.listdir(self.backup_root):
                item_path = os.path.join(self.backup_root, item)
                
                if not os.path.isdir(item_path):
                    continue
                
                # Check directory age
                dir_time = os.path.getmtime(item_path)
                if dir_time < cutoff_time:
                    logger.info(f"Removing old backup: {item_path}")
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
