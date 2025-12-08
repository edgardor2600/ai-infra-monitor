"""
Disk Analyzer - Cleanup Rules

This module defines what files are safe to clean and their risk levels.
"""

import os
from typing import Dict, List, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CleanupCategory:
    """Represents a category of files that can be cleaned"""
    name: str
    display_name: str
    description: str
    risk_level: str  # 'low', 'medium', 'high'
    is_safe_auto: bool  # Can be cleaned automatically
    get_paths: Callable  # Function that returns list of paths to scan


def get_temp_directories() -> List[str]:
    """Get Windows temporary directories"""
    paths = []
    
    # Windows Temp
    if os.path.exists(r"C:\Windows\Temp"):
        paths.append(r"C:\Windows\Temp")
    
    # User Temp
    user_temp = os.environ.get('TEMP')
    if user_temp and os.path.exists(user_temp):
        paths.append(user_temp)
    
    # Alternative user temp
    user_temp_alt = os.environ.get('TMP')
    if user_temp_alt and os.path.exists(user_temp_alt) and user_temp_alt not in paths:
        paths.append(user_temp_alt)
    
    return paths


def get_browser_cache_directories() -> List[str]:
    """Get browser cache directories"""
    paths = []
    user_profile = os.environ.get('USERPROFILE', '')
    
    if not user_profile:
        return paths
    
    # Chrome cache
    chrome_cache = os.path.join(user_profile, r"AppData\Local\Google\Chrome\User Data\Default\Cache")
    if os.path.exists(chrome_cache):
        paths.append(chrome_cache)
    
    # Edge cache
    edge_cache = os.path.join(user_profile, r"AppData\Local\Microsoft\Edge\User Data\Default\Cache")
    if os.path.exists(edge_cache):
        paths.append(edge_cache)
    
    # Firefox cache
    firefox_cache = os.path.join(user_profile, r"AppData\Local\Mozilla\Firefox\Profiles")
    if os.path.exists(firefox_cache):
        paths.append(firefox_cache)
    
    return paths


def get_recycle_bin_path() -> List[str]:
    """Get recycle bin path"""
    # Note: Recycle bin is special, we'll handle it differently
    return [r"C:\$Recycle.Bin"]


def get_windows_update_cache() -> List[str]:
    """Get Windows Update cache directories"""
    paths = []
    
    if os.path.exists(r"C:\Windows\SoftwareDistribution\Download"):
        paths.append(r"C:\Windows\SoftwareDistribution\Download")
    
    return paths


def get_installer_cache() -> List[str]:
    """Get installer cache directories"""
    paths = []
    user_profile = os.environ.get('USERPROFILE', '')
    
    if not user_profile:
        return paths
    
    # Downloads folder (we'll filter for installers)
    downloads = os.path.join(user_profile, "Downloads")
    if os.path.exists(downloads):
        paths.append(downloads)
    
    return paths


def get_development_cache() -> List[str]:
    """Get development cache directories (node_modules, __pycache__, etc.)"""
    paths = []
    user_profile = os.environ.get('USERPROFILE', '')
    
    if not user_profile:
        return paths
    
    # Common development directories
    dev_dirs = [
        os.path.join(user_profile, "Documents"),
        os.path.join(user_profile, "Projects"),
        os.path.join(user_profile, "Desktop"),
    ]
    
    return [d for d in dev_dirs if os.path.exists(d)]


def get_thumbnail_cache() -> List[str]:
    """Get Windows thumbnail cache"""
    paths = []
    user_profile = os.environ.get('USERPROFILE', '')
    
    if not user_profile:
        return paths
    
    thumbs_cache = os.path.join(user_profile, r"AppData\Local\Microsoft\Windows\Explorer")
    if os.path.exists(thumbs_cache):
        paths.append(thumbs_cache)
    
    return paths


# Define all cleanup categories
CLEANUP_CATEGORIES: Dict[str, CleanupCategory] = {
    'temp_files': CleanupCategory(
        name='temp_files',
        display_name='Temporary Files',
        description='Windows temporary files and folders that are safe to delete',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_temp_directories
    ),
    'browser_cache': CleanupCategory(
        name='browser_cache',
        display_name='Browser Cache',
        description='Cached files from web browsers (Chrome, Edge, Firefox)',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_browser_cache_directories
    ),
    'recycle_bin': CleanupCategory(
        name='recycle_bin',
        display_name='Recycle Bin',
        description='Files in the Recycle Bin',
        risk_level='low',
        is_safe_auto=False,  # User should review first
        get_paths=get_recycle_bin_path
    ),
    'windows_update': CleanupCategory(
        name='windows_update',
        display_name='Windows Update Cache',
        description='Old Windows Update files',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_windows_update_cache
    ),
    'installers': CleanupCategory(
        name='installers',
        display_name='Old Installers',
        description='Installation files (.msi, .exe) in Downloads folder older than 30 days',
        risk_level='medium',
        is_safe_auto=False,
        get_paths=get_installer_cache
    ),
    'thumbnails': CleanupCategory(
        name='thumbnails',
        display_name='Thumbnail Cache',
        description='Windows thumbnail cache files',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_thumbnail_cache
    ),
    'dev_cache': CleanupCategory(
        name='dev_cache',
        display_name='Development Cache',
        description='node_modules, __pycache__, .cache folders from development projects',
        risk_level='high',
        is_safe_auto=False,
        get_paths=get_development_cache
    ),
}


# File extensions that are safe to delete from temp directories
SAFE_TEMP_EXTENSIONS = {
    '.tmp', '.temp', '.log', '.bak', '.old', '.cache',
    '.dmp', '.chk', '.gid', '.~*'
}

# File extensions for installers
INSTALLER_EXTENSIONS = {
    '.msi', '.exe', '.dmg', '.pkg', '.deb', '.rpm'
}

# Directories that should NEVER be touched
PROTECTED_DIRECTORIES = {
    r"C:\Windows\System32",
    r"C:\Windows\SysWOW64",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
    os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Pictures'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Videos'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Music'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
}

# File patterns that should NEVER be deleted
PROTECTED_PATTERNS = [
    '*.docx', '*.xlsx', '*.pptx', '*.pdf',
    '*.jpg', '*.jpeg', '*.png', '*.gif', '*.mp4', '*.avi',
    '*.zip', '*.rar', '*.7z',
    '*.py', '*.js', '*.java', '*.cpp', '*.c', '*.h',
]


def is_path_protected(path: str) -> bool:
    """
    Check if a path is protected and should never be deleted.
    
    Args:
        path: File or directory path to check
        
    Returns:
        True if path is protected, False otherwise
    """
    path = os.path.abspath(path)
    
    # Check if path is in protected directories
    for protected_dir in PROTECTED_DIRECTORIES:
        if path.startswith(protected_dir):
            # Exception: temp directories within protected dirs are OK
            if 'Temp' in path or 'Cache' in path:
                continue
            return True
    
    return False


def is_file_old_enough(file_path: str, days: int = 30) -> bool:
    """
    Check if a file is older than specified days.
    
    Args:
        file_path: Path to the file
        days: Number of days threshold
        
    Returns:
        True if file is older than threshold, False otherwise
    """
    try:
        file_time = os.path.getatime(file_path)
        file_date = datetime.fromtimestamp(file_time)
        threshold = datetime.now() - timedelta(days=days)
        return file_date < threshold
    except Exception:
        return False


def get_category_by_name(category_name: str) -> CleanupCategory:
    """
    Get cleanup category by name.
    
    Args:
        category_name: Name of the category
        
    Returns:
        CleanupCategory object
        
    Raises:
        ValueError: If category not found
    """
    if category_name not in CLEANUP_CATEGORIES:
        raise ValueError(f"Unknown cleanup category: {category_name}")
    
    return CLEANUP_CATEGORIES[category_name]
