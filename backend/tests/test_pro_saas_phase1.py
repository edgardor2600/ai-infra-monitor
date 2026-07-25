"""
Tests for Pro SaaS Phase 1: Multi-tenant, Audit Logs, OS Adapter, and Pluggable LLM Providers.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch

from backend.disk_analyzer.os_adapter import (
    get_os_adapter,
    WindowsOSAdapter,
    LinuxOSAdapter
)
from backend.app.llm_adapter import (
    get_llm_provider,
    MiniMaxProvider,
    GeminiProvider,
    NoCloudProvider,
    LLMAdapter
)


def test_os_adapter_protected_paths():
    """Verify OS Adapter handles path protection cleanly across platforms."""
    adapter = get_os_adapter()
    assert adapter.get_system_name() in ["Windows", "Linux"]
    
    win_adapter = WindowsOSAdapter()
    assert win_adapter.is_path_protected(r"C:\Windows\System32\drivers\etc") is True
    assert win_adapter.is_path_protected(r"C:\Users\EDGARDO\AppData\Local\Temp\cache.tmp") is False
    
    linux_adapter = LinuxOSAdapter()
    assert linux_adapter.is_path_protected("/etc/shadow") is True
    assert linux_adapter.is_path_protected("/tmp/test.tmp") is False


def test_llm_provider_factory():
    """Verify factory instantiates providers based on config or env."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "nocloud"}):
        provider = get_llm_provider()
        assert isinstance(provider, NoCloudProvider)
        assert provider.get_provider_name() == "Sin Nube (Privacidad Total 100% Offline)"
        
    with patch.dict(os.environ, {"MINIMAX_API_KEY": "test_key", "LLM_PROVIDER": "minimax"}):
        provider = get_llm_provider()
        assert isinstance(provider, MiniMaxProvider)
        assert provider.get_provider_name() == "MiniMax AI"


@pytest.mark.asyncio
async def test_no_cloud_privacy_provider():
    """Verify NoCloudProvider returns offline report without external calls."""
    adapter = LLMAdapter(provider=NoCloudProvider())
    report = await adapter.analyze_disk_scan({"total_files": 5, "total_size_formatted": "100 MB"})
    assert "Diagnóstico" in report["title"]
    assert "Privacidad" in report.get("title", "") or "sin enviar datos" in report.get("explanation_es", "")
