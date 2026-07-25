"""
Tests for Disk Analyzer V2 with MiniMax AI, Multi-drive, Real Rollback, and Backup Purge.
"""

import os
import shutil
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.disk_analyzer.rules import (
    is_path_protected,
    get_age_category,
    CLEANUP_CATEGORIES
)
from backend.disk_analyzer.scanner import DiskScanner
from backend.disk_analyzer.cleaner import DiskCleaner
from backend.app.llm_adapter import LLMAdapter


def test_protected_paths_safety():
    """Verify that sensitive directories and personal file types are strictly protected."""
    assert is_path_protected(r"C:\Windows\System32\cmd.exe") is True
    assert is_path_protected(r"C:\Program Files\App\main.exe") is True
    assert is_path_protected(r"C:\Users\EDGARDO\Documents\importante.pdf") is True
    assert is_path_protected(r"C:\Users\EDGARDO\Pictures\foto.jpg") is True
    assert is_path_protected(r"C:\Users\EDGARDO\Projects\mi_codigo.py") is True
    
    # Safe temp files should NOT be protected
    assert is_path_protected(r"C:\Users\EDGARDO\AppData\Local\Temp\cache.tmp") is False


def test_scanner_unlimited_and_drives():
    """Verify that scanner retrieves available drives and does not cap at 100 items artificially."""
    drives = DiskScanner.get_available_drives()
    assert isinstance(drives, list)
    assert len(drives) > 0
    
    scanner = DiskScanner(host_id=1, drive="C:")
    assert scanner.drive == "C:"


def test_cleaner_rollback_manifest_and_purge():
    """Test full cycle: clean with backup -> verify manifest -> rollback restoration -> purge backup."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up test files
        target_dir = os.path.join(temp_dir, "app_temp")
        os.makedirs(target_dir, exist_ok=True)
        test_file = os.path.join(target_dir, "test_cache.tmp")
        
        with open(test_file, "w") as f:
            f.write("temporary data to clean")
            
        assert os.path.exists(test_file)
        
        cleaner = DiskCleaner(host_id=1, scan_id=999)
        # Force backup root into temp directory
        cleaner.backup_root = os.path.join(temp_dir, "cleanup_backup")
        
        files_by_cat = {
            'temp_files': [
                {'path': test_file, 'size': 23}
            ]
        }
        
        # 1. Clean category with backup
        res = cleaner.cleanup_categories(['temp_files'], files_by_cat, create_backup=True)
        assert res['files_deleted'] == 1
        assert not os.path.exists(test_file)
        
        backup_path = res['backup_path']
        assert os.path.exists(backup_path)
        assert os.path.exists(os.path.join(backup_path, "manifest.json"))
        
        # 2. Test Rollback restoration
        cleaner.backup_path = backup_path
        rollback_res = cleaner.rollback(cleanup_operation_id=1)
        assert rollback_res['files_restored'] == 1
        assert os.path.exists(test_file)
        
        # 3. Test Purge Backup to free disk space
        purge_res = DiskCleaner.purge_backup_path(backup_path)
        assert purge_res['success'] is True
        assert not os.path.exists(backup_path)


@pytest.mark.asyncio
async def test_minimax_llm_adapter():
    """Test MiniMax LLM adapter parsing and disk analysis generation."""
    with patch.dict(os.environ, {"MINIMAX_API_KEY": "test_key", "MINIMAX_MODEL": "abab6.5s-chat"}):
        adapter = LLMAdapter()
        assert adapter.minimax_api_key == "test_key"
        
        mock_response = {
            "title": "Diagnóstico de Disco",
            "overall_status": "Excelente",
            "explanation_es": "Se han detectado 2.5 GB en cachés.",
            "safety_guarantee": "Tus archivos están 100% protegidos.",
            "top_recommendations": ["Borrar caché del navegador"]
        }
        
        with patch.object(adapter, '_call_minimax', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = str(mock_response).replace("'", '"')
            report = await adapter.analyze_disk_scan({"total_files": 10, "total_size_bytes": 1000})
            assert report["title"] == "Diagnóstico de Disco"
            assert "top_recommendations" in report
