"""
Disk Analyzer - Cleanup Rules

This module defines what files are safe to clean and their risk levels.
"""

import os
import fnmatch
from typing import Dict, List, Callable, Optional
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
    
    dev_dirs = [
        os.path.join(user_profile, "Documents"),
        os.path.join(user_profile, "Projects"),
        os.path.join(user_profile, "Desktop"),
        os.path.join(user_profile, "source"),
        os.path.join(user_profile, "workspace"),
    ]
    return [d for d in dev_dirs if os.path.exists(d)]


def get_package_manager_caches() -> List[str]:
    """Get package manager cache directories (pip, npm, yarn, cargo, nuget)"""
    paths = []
    user_profile = os.environ.get('USERPROFILE', '')
    if not user_profile:
        return paths
    
    pkg_dirs = [
        os.path.join(user_profile, r"AppData\Local\pip\Cache"),
        os.path.join(user_profile, r"AppData\Local\npm-cache"),
        os.path.join(user_profile, r"AppData\Local\Yarn\Cache"),
        os.path.join(user_profile, r".cargo\registry"),
        os.path.join(user_profile, r".nuget\packages"),
    ]
    return [d for d in pkg_dirs if os.path.exists(d)]


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


def get_system_log_directories() -> List[str]:
    """Get system log directories"""
    paths = []
    user_profile = os.environ.get('USERPROFILE', '')
    if os.path.exists(r"C:\Windows\Logs"):
        paths.append(r"C:\Windows\Logs")
    if user_profile:
        appdata_temp = os.path.join(user_profile, r"AppData\Local\CrashDumps")
        if os.path.exists(appdata_temp):
            paths.append(appdata_temp)
    return paths


# Define all cleanup categories
CLEANUP_CATEGORIES: Dict[str, CleanupCategory] = {
    'temp_files': CleanupCategory(
        name='temp_files',
        display_name='Archivos Temporales',
        description='Archivos y carpetas temporales de Windows que se pueden borrar de forma totalmente segura.',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_temp_directories
    ),
    'browser_cache': CleanupCategory(
        name='browser_cache',
        display_name='Caché de Navegadores',
        description='Imágenes y datos en caché de Chrome, Edge y Firefox. No borra contraseñas ni marcadores.',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_browser_cache_directories
    ),
    'recycle_bin': CleanupCategory(
        name='recycle_bin',
        display_name='Papelera de Reciclaje',
        description='Archivos eliminados previamente en la Papelera.',
        risk_level='low',
        is_safe_auto=False,
        get_paths=get_recycle_bin_path
    ),
    'windows_update': CleanupCategory(
        name='windows_update',
        display_name='Caché de Windows Update',
        description='Descargas de actualizaciones pasadas instaladas.',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_windows_update_cache
    ),
    'thumbnails': CleanupCategory(
        name='thumbnails',
        display_name='Caché de Miniaturas',
        description='Vista previa de miniaturas de imágenes generadas por Windows.',
        risk_level='low',
        is_safe_auto=True,
        get_paths=get_thumbnail_cache
    ),
    'pkg_managers': CleanupCategory(
        name='pkg_managers',
        display_name='Caché de Gestores de Paquetes',
        description='Caché de paquetes descargados por pip, npm, yarn, cargo y nuget.',
        risk_level='medium',
        is_safe_auto=False,
        get_paths=get_package_manager_caches
    ),
    'installers': CleanupCategory(
        name='installers',
        display_name='Instaladores Antiguos',
        description='Archivos de instalación (.msi, .exe) en la carpeta Descargas con más de 30 días.',
        risk_level='medium',
        is_safe_auto=False,
        get_paths=get_installer_cache
    ),
    'system_logs': CleanupCategory(
        name='system_logs',
        display_name='Logs y Volcados de Error',
        description='Registros del sistema y reportes de fallos (CrashDumps) antiguos.',
        risk_level='medium',
        is_safe_auto=False,
        get_paths=get_system_log_directories
    ),
    'dev_cache': CleanupCategory(
        name='dev_cache',
        display_name='Cachés de Desarrollo',
        description='Carpetas node_modules, __pycache__, .venv, .next, dist en proyectos de desarrollo.',
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
    r"C:\Windows\System",
    r"C:\Windows\WinSxS",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
    os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Pictures'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Videos'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Music'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
}

# File extensions/patterns that should NEVER be deleted automatically
PROTECTED_EXTENSIONS = {
    # Documents
    '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.rtf', '.csv',
    # Images/Media
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.mp4', '.avi', '.mkv', '.mov', '.mp3', '.wav',
    # Source code & Data
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.java', '.rs', '.go', '.cpp', '.c', '.h', '.cs', '.sql', '.ps1', '.json', '.yaml', '.yml',
    # Databases & Keys
    '.db', '.sqlite', '.sqlite3', '.mdf', '.accdb', '.pem', '.crt', '.key', '.p12', '.pfx'
}


def is_path_protected(path: str) -> bool:
    """
    Check if a path is protected and should never be deleted.
    
    Args:
        path: File or directory path to check
        
    Returns:
        True if path is protected, False otherwise
    """
    path = os.path.abspath(path)
    
    # Check protected directories
    for protected_dir in PROTECTED_DIRECTORIES:
        if path.lower().startswith(protected_dir.lower()):
            # Exception: Temp/Cache inside user profile or AppData
            if 'temp' in path.lower() or 'cache' in path.lower():
                continue
            return True
    
    # Check protected file extensions if it is a file
    _, ext = os.path.splitext(path)
    if ext.lower() in PROTECTED_EXTENSIONS:
        # Exception: if it's inside a temp directory or node_modules/__pycache__
        if not ('temp' in path.lower() or 'cache' in path.lower() or 'node_modules' in path.lower() or '__pycache__' in path.lower()):
            return True
            
    return False


def get_age_category(file_path: str) -> str:
    """
    Get age classification string for a file based on last modification/access time.
    Returns: '< 7 días', '7 - 30 días', '30 - 90 días', '90 - 365 días', '> 1 año'
    """
    try:
        mtime = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(mtime)
        now = datetime.now()
        diff_days = (now - file_date).days
        
        if diff_days < 7:
            return "< 7 días"
        elif diff_days <= 30:
            return "7 - 30 días"
        elif diff_days <= 90:
            return "30 - 90 días"
        elif diff_days <= 365:
            return "90 - 365 días"
        else:
            return "> 1 año"
    except Exception:
        return "Desconocido"


def is_file_old_enough(file_path: str, days: int = 30) -> bool:
    """Check if file is older than threshold days."""
    try:
        mtime = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(mtime)
        threshold = datetime.now() - timedelta(days=days)
        return file_date < threshold
    except Exception:
        return False


def get_category_by_name(category_name: str) -> CleanupCategory:
    """Get cleanup category by name."""
    if category_name not in CLEANUP_CATEGORIES:
        raise ValueError(f"Unknown cleanup category: {category_name}")
    return CLEANUP_CATEGORIES[category_name]

