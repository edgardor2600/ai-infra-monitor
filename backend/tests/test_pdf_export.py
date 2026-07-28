"""
Tests for Executive PDF/HTML Report Exporter.
"""

import pytest
from backend.disk_analyzer.pdf_exporter import generate_executive_pdf_report


def test_generate_executive_pdf_report_content():
    """Test generating executive diagnostic report buffer."""
    scan_data = {
        "total_size_bytes": 12884901888,
        "categories": {
            "dev_cache": {"display_name": "Cachés de Desarrollo", "file_count": 100, "total_size_formatted": "4.32 GB", "risk_level": "high"},
            "installers": {"display_name": "Instaladores Antiguos", "file_count": 20, "total_size_formatted": "3.27 GB", "risk_level": "medium"}
        }
    }
    ai_report = {
        "overall_status": "Crítico",
        "health_score": 10,
        "urgency_level": "CRÍTICO",
        "explanation_es": "El disco se encuentra al 90.5% de ocupación.",
        "safety_guarantee": "Protección de datos activada.",
        "top_recommendations": [
            "Limpia la Caché de Gestores de Paquetes.",
            "Elimina instaladores antiguos de Descargas."
        ]
    }

    buffer = generate_executive_pdf_report(scan_id=42, scan_data=scan_data, ai_report=ai_report, org_name="Empresa Test")

    assert isinstance(buffer, bytes)
    assert len(buffer) > 100
    report_text = buffer.decode("utf-8", errors="ignore")
    assert "Scan #42" in report_text or "%PDF" in report_text
    assert "Empresa Test" in report_text or "%PDF" in report_text
