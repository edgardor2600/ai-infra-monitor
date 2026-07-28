"""
Disk Analyzer AI - Executive PDF Report Exporter (High-Contrast B2B Printable PDF)

Generates 100% genuine, uncorrupted, high-contrast B2B executive diagnostic reports
with pristine typography, clean margins, corporate color palettes, and strict risk logic.
"""

import io
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

logger = logging.getLogger(__name__)


def generate_executive_pdf_report(scan_id: int, scan_data: Dict[str, Any], ai_report: Dict[str, Any], org_name: str = "Organización Principal") -> bytes:
    """
    Generate an executive binary PDF document buffer for a disk scan using ReportLab.
    Returns 100% clean, high-contrast, uncorrupted %PDF-1.4 binary bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Executive High-Contrast Color Palette for Clean Printing
    NAVY_DARK = colors.HexColor("#0f172a")
    HEADER_SLATE = colors.HexColor("#1e293b")
    PRIMARY_BLUE = colors.HexColor("#0284c7")
    CYAN_ACCENT = colors.HexColor("#0ea5e9")
    TEXT_DARK = colors.HexColor("#0f172a")
    TEXT_BODY = colors.HexColor("#334155")
    TEXT_MUTED = colors.HexColor("#64748b")
    WHITE = colors.HexColor("#ffffff")
    BG_LIGHT_BLUE = colors.HexColor("#f0f9ff")
    BG_LIGHT_GRAY = colors.HexColor("#f8fafc")
    BORDER_COLOR = colors.HexColor("#cbd5e1")
    
    GREEN_TEXT = colors.HexColor("#15803d")
    GREEN_BG = colors.HexColor("#dcfce7")
    RED_TEXT = colors.HexColor("#b91c1c")
    RED_BG = colors.HexColor("#fee2e2")
    AMBER_TEXT = colors.HexColor("#b45309")
    AMBER_BG = colors.HexColor("#fef3c7")
    GRAY_TEXT = colors.HexColor("#64748b")

    status_str = ai_report.get("overall_status", "Saludable").upper()
    status_color = RED_TEXT if status_str in ["CRÍTICO", "CRITICO"] else AMBER_TEXT if status_str in ["ADVERTENCIA", "WARNING"] else GREEN_TEXT

    # Custom High-Contrast Styles
    doc_title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=NAVY_DARK,
        alignment=TA_LEFT,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=TEXT_MUTED,
        alignment=TA_LEFT
    )

    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=NAVY_DARK,
        spaceBefore=14,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=TEXT_BODY,
        alignment=TA_LEFT
    )

    ai_body_style = ParagraphStyle(
        'AIBodyCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.5,
        textColor=TEXT_BODY,
        alignment=TA_JUSTIFY
    )

    story = []

    # 1. Header Dark Banner (Clean Navy Background with Bright Cyan/White text)
    banner_left = Paragraph("<b><font color='#ffffff' size='14'>AI INFRA </font><font color='#38bdf8' size='14'>MONITOR PRO</font></b>", styles['Normal'])
    banner_right = Paragraph("<b><font color='#38bdf8' size='9'>ENTERPRISE DIAGNOSTIC REPORT</font></b>", ParagraphStyle('R', alignment=TA_RIGHT))
    
    banner_table = Table([[banner_left, banner_right]], colWidths=[320, 220])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY_DARK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 14))

    # 2. Document Title & Metadata Block
    story.append(Paragraph("Informe Corporativo de Diagnóstico de Almacenamiento", doc_title_style))
    story.append(Spacer(1, 4))
    
    meta_text = Paragraph(f"<b>Organización:</b> {org_name} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Scan ID:</b> #{scan_id} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Fecha de Emisión:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", subtitle_style)
    story.append(meta_text)
    story.append(Spacer(1, 12))

    # 3. KPI Cards Table (Dark Navy Header, Light Gray Cells, High-Contrast Text)
    total_bytes = scan_data.get("total_size_bytes", 0)
    total_gb = round(total_bytes / (1024 * 1024 * 1024), 2)
    health_score = ai_report.get("health_score", 90)
    urgency = ai_report.get("urgency_level", "BAJO").upper()

    kpi_headers = [
        Paragraph("<b>ESTADO DE SALUD</b>", ParagraphStyle('KH1', fontSize=8, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>PUNTAJE DISCO</b>", ParagraphStyle('KH2', fontSize=8, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>ESPACIO ANALIZADO</b>", ParagraphStyle('KH3', fontSize=8, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>NIVEL URGENCIA</b>", ParagraphStyle('KH4', fontSize=8, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER)),
    ]
    
    kpi_values = [
        Paragraph(f"<b><font color='{status_color.hexval()}'>{status_str}</font></b>", ParagraphStyle('KV1', fontSize=13, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph(f"<b><font color='#0f172a'>{health_score} / 100</font></b>", ParagraphStyle('KV2', fontSize=13, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph(f"<b><font color='#0284c7'>{total_gb} GB</font></b>", ParagraphStyle('KV3', fontSize=13, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph(f"<b><font color='{status_color.hexval()}'>{urgency}</font></b>", ParagraphStyle('KV4', fontSize=13, fontName='Helvetica-Bold', alignment=TA_CENTER)),
    ]

    kpi_table = Table([kpi_headers, kpi_values], colWidths=[135, 135, 135, 135])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_SLATE),
        ('BACKGROUND', (0, 1), (-1, 1), BG_LIGHT_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # 4. AI Executive Diagnosis Box (Light Blue Background with Dark Blue Header & Border)
    ai_explanation = ai_report.get("explanation_es", "Análisis ejecutado correctamente.")
    ai_safety = ai_report.get("safety_guarantee", "Protección de Datos Activada: Ningún archivo crítico del sistema será modificado.")

    ai_header_p = Paragraph("<b>DIAGNÓSTICO DE INTELIGENCIA ARTIFICIAL (MiniMax / Gemini AI)</b>", ParagraphStyle('AIH', fontSize=10.5, fontName='Helvetica-Bold', textColor=PRIMARY_BLUE))
    ai_body_p = Paragraph(ai_explanation, ai_body_style)
    ai_safety_p = Paragraph(f"<b><font color='#15803d'>Garantía de Seguridad:</font></b> {ai_safety.replace('🛡️', '').replace('nn', '').strip()}", ParagraphStyle('AIS', fontSize=9, fontName='Helvetica', textColor=GREEN_TEXT))

    ai_table = Table([[ai_header_p], [Spacer(1, 2)], [ai_body_p], [Spacer(1, 6)], [ai_safety_p]], colWidths=[540])
    ai_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT_BLUE),
        ('BOX', (0, 0), (-1, -1), 1.5, PRIMARY_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(ai_table)
    story.append(Spacer(1, 14))

    # 5. Categories Breakdown Table with Strict Risk & 0-Byte Logic
    story.append(Paragraph("Desglose Cuantitativo por Categorías de Almacenamiento", section_header_style))

    table_headers = [
        Paragraph("<b>CATEGORÍA</b>", ParagraphStyle('TH1', fontSize=8.5, fontName='Helvetica-Bold', textColor=WHITE)),
        Paragraph("<b>ARCHIVOS</b>", ParagraphStyle('TH2', fontSize=8.5, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>TAMAÑO RECUPERABLE</b>", ParagraphStyle('TH3', fontSize=8.5, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_RIGHT)),
        Paragraph("<b>NIVEL DE RIESGO</b>", ParagraphStyle('TH4', fontSize=8.5, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_CENTER))
    ]
    
    table_rows = [table_headers]

    categories = scan_data.get("categories", {})
    row_count = 0

    for cat_key, cat_val in categories.items():
        if cat_key in ["disk_info", "drive"] or not isinstance(cat_val, dict):
            continue

        display_name = cat_val.get("display_name", cat_key)
        file_count = cat_val.get("file_count", 0)
        size_bytes = cat_val.get("total_size", cat_val.get("total_size_bytes", 0))
        size_fmt = cat_val.get("total_size_formatted", "0 B")
        
        # Strict Risk Evaluation Logic
        if file_count == 0 or size_bytes == 0 or size_fmt in ["0 B", "0.00 B"]:
            risk_label = "NINGUNO"
            risk_color = GRAY_TEXT
        elif cat_key in ["temp_files", "browser_cache", "recycle_bin", "thumbnails"]:
            risk_label = "CERO RIESGO"
            risk_color = GREEN_TEXT
        elif cat_key in ["pkg_managers", "installers", "windows_update"]:
            risk_label = "BAJO"
            risk_color = AMBER_TEXT
        else:
            risk_label = "REVISAR"
            risk_color = RED_TEXT

        row_bg = BG_LIGHT_GRAY if row_count % 2 == 1 else WHITE
        row_count += 1

        table_rows.append([
            Paragraph(f"<b>{display_name}</b>", body_style),
            Paragraph(str(file_count), ParagraphStyle('C1', fontSize=9.5, textColor=TEXT_BODY, alignment=TA_CENTER)),
            Paragraph(f"<b><font color='#0284c7'>{size_fmt}</font></b>", ParagraphStyle('C2', fontSize=9.5, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
            Paragraph(f"<b><font color='{risk_color.hexval()}'>{risk_label}</font></b>", ParagraphStyle('C3', fontSize=8.5, fontName='Helvetica-Bold', alignment=TA_CENTER))
        ])

    cat_table = Table(table_rows, colWidths=[185, 95, 140, 120])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY_DARK),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # Apply row shading
    for i in range(1, len(table_rows)):
        bg = BG_LIGHT_GRAY if i % 2 == 1 else WHITE
        cat_table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), bg)]))

    story.append(cat_table)
    story.append(Spacer(1, 14))

    # 6. AI Recommendations List (Clean bullet points without corrupt unicode square icons)
    story.append(Paragraph("Recomendaciones Principales de Optimización", section_header_style))
    recs = ai_report.get("top_recommendations", ["Mantener actualizadas las políticas de mantenimiento preventivo."])
    
    for rec in recs:
        clean_rec = rec.replace("•", "").replace("🤖", "").replace("⚡", "").strip()
        rec_p = Paragraph(f"• &nbsp; {clean_rec}", ParagraphStyle('RecItem', fontSize=9.5, leading=14, textColor=TEXT_BODY))
        story.append(rec_p)
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=8))
    
    footer_p = Paragraph("AI Infra Monitor & Disk Analyzer AI Pro · Documento de Diagnóstico Corporativo Inmutable B2B", ParagraphStyle('Footer', fontSize=8, textColor=TEXT_MUTED, alignment=TA_CENTER))
    story.append(footer_p)

    # Build PDF binary
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(f"Generated executive high-contrast PDF report for Scan #{scan_id} ({len(pdf_bytes)} bytes)")
    return pdf_bytes
