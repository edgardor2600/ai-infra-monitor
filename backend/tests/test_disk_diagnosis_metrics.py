"""
Tests for Quantitative Disk Diagnosis Engine Metrics.
Verifies Health Score (0-100), Urgency Levels, exact GB calculations,
and fallback behavior without static generic filler text.
"""

import pytest
from backend.app.llm_adapter import LLMAdapter, NoCloudProvider, build_rule_based_diagnosis


def test_build_rule_based_diagnosis_calculation():
    """Verify that rule-based diagnosis correctly computes health score, urgency, and GBs."""
    sample_scan_data = {
        "total_size_bytes": 16247410020,
        "categories": {
            "disk_info": {
                "drive": "C:",
                "total": 489416888320,
                "used": 448760668160,
                "free": 40656220160,
                "used_percent": 91.69
            },
            "pkg_managers": {
                "total_size": 7051569761,
                "file_count": 23054
            },
            "dev_cache": {
                "total_size": 4636734510,
                "file_count": 133
            },
            "installers": {
                "total_size": 3515487005,
                "file_count": 25
            },
            "browser_cache": {
                "total_size": 394228881,
                "file_count": 1399
            }
        }
    }

    diag = build_rule_based_diagnosis(sample_scan_data, provider_name="Test Provider")

    assert diag["overall_status"] == "Crítico"
    assert diag["health_score"] == 8  # 100 - 91.69 = ~8
    assert diag["urgency_level"] == "CRÍTICO"
    assert "91.7%" in diag["explanation_es"] or "91.6%" in diag["explanation_es"]
    assert len(diag["top_recommendations"]) >= 2
    assert "pip cache purge" in diag["top_recommendations"][0]
    
    storage_health = diag["storage_health"]
    assert storage_health["health_score"] == 8
    assert storage_health["urgency_level"] == "CRÍTICO"
    assert storage_health["safe_recovery_gb"] > 10.0  # pkg_managers + installers + browser_cache = ~10.2 GB
    assert storage_health["conditional_recovery_gb"] == 4.31 or storage_health["conditional_recovery_gb"] == 4.32


@pytest.mark.asyncio
async def test_nocloud_llm_adapter_returns_quantitative_diagnosis():
    """Verify that LLMAdapter with NoCloudProvider returns a quantitative data-driven report."""
    adapter = LLMAdapter(provider=NoCloudProvider())

    scan_payload = {
        "total_files": 100,
        "total_size_bytes": 5368709120,  # 5 GB
        "categories": {
            "disk_info": {
                "drive": "C:",
                "total": 100000000000,
                "used": 85000000000,
                "free": 15000000000,
                "used_percent": 85.0
            },
            "pkg_managers": {
                "total_size": 3221225472,  # 3 GB
                "file_count": 1200
            }
        }
    }

    report = await adapter.analyze_disk_scan(scan_payload)

    assert "Diagnóstico Corporativo" in report["title"]
    assert report["overall_status"] == "Advertencia"
    assert report["health_score"] == 15
    assert report["urgency_level"] == "ALTO"
    assert report["storage_health"]["safe_recovery_gb"] == 3.0
    assert "pip cache purge" in report["top_recommendations"][0]
