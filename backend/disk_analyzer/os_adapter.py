"""
OS Abstraction Layer for Disk Analyzer AI (Cross-Platform Ready).
Decouples OS-specific path logic, temp directories, and system command execution.
"""

import os
import sys
import platform
import shutil
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class OSAdapterBase(ABC):
    """Abstract Base Class for OS-specific storage and path operations."""
    
    @abstractmethod
    def get_system_name(self) -> str:
        pass
        
    @abstractmethod
    def get_temp_directories(self) -> List[str]:
        pass
        
    @abstractmethod
    def get_protected_paths(self) -> List[str]:
        pass
        
    @abstractmethod
    def get_log_directories(self) -> List[str]:
        pass

    @abstractmethod
    def is_path_protected(self, path: str) -> bool:
        pass


class WindowsOSAdapter(OSAdapterBase):
    """Windows specific implementation."""
    
    def get_system_name(self) -> str:
        return "Windows"
        
    def get_temp_directories(self) -> List[str]:
        temp_dirs = []
        win_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if win_temp and os.path.exists(win_temp):
            temp_dirs.append(win_temp)
        sys_temp = r"C:\Windows\Temp"
        if os.path.exists(sys_temp):
            temp_dirs.append(sys_temp)
        return temp_dirs
        
    def get_protected_paths(self) -> List[str]:
        user_profile = os.environ.get("USERPROFILE", r"C:\Users\Default")
        return [
            r"C:\Windows",
            r"C:\Windows\System32",
            r"C:\Windows\SysWOW64",
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            r"C:\ProgramData",
            os.path.join(user_profile, "Documents"),
            os.path.join(user_profile, "Desktop"),
            os.path.join(user_profile, "Pictures"),
            os.path.join(user_profile, "Videos"),
            os.path.join(user_profile, "Music"),
            os.path.join(user_profile, "OneDrive"),
        ]
        
    def get_log_directories(self) -> List[str]:
        user_profile = os.environ.get("USERPROFILE", "")
        return [
            r"C:\Windows\Logs",
            os.path.join(user_profile, r"AppData\Local\CrashDumps")
        ]
        
    def is_path_protected(self, path: str) -> bool:
        normalized = os.path.normpath(path).lower()
        for protected in self.get_protected_paths():
            protected_norm = os.path.normpath(protected).lower()
            if normalized == protected_norm or normalized.startswith(protected_norm + os.sep):
                return True
        return False


class LinuxOSAdapter(OSAdapterBase):
    """Linux specific implementation (Ready for future Linux server agent expansion)."""
    
    def get_system_name(self) -> str:
        return "Linux"
        
    def get_temp_directories(self) -> List[str]:
        return ["/tmp", "/var/tmp"]
        
    def get_protected_paths(self) -> List[str]:
        return [
            "/bin", "/sbin", "/lib", "/lib64", "/usr/bin", "/usr/sbin",
            "/usr/lib", "/etc", "/boot", "/sys", "/proc", "/dev", "/root"
        ]
        
    def get_log_directories(self) -> List[str]:
        return ["/var/log"]
        
    def is_path_protected(self, path: str) -> bool:
        normalized = os.path.normpath(path)
        for protected in self.get_protected_paths():
            protected_norm = os.path.normpath(protected)
            if normalized == protected_norm or normalized.startswith(protected_norm + os.sep) or normalized.startswith(protected_norm + "/"):
                return True
        return False


def get_os_adapter() -> OSAdapterBase:
    """Factory function returning current OS adapter."""
    current_os = platform.system().lower()
    if "win" in current_os:
        return WindowsOSAdapter()
    elif "linux" in current_os or "darwin" in current_os:
        return LinuxOSAdapter()
    return WindowsOSAdapter()
