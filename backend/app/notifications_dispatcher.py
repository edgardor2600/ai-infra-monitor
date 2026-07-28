"""
AI Infra Monitor - Webhook & Push Notifications Dispatcher

Handles asynchronous dispatching of Webhook notifications (Slack, Microsoft Teams, Discord, custom HTTP POST)
when system alerts reach CRITICAL/HIGH severity or auto-remediation triggers.
"""

import os
import json
import logging
import httpx
import psycopg2
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_db_connection():
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
    except Exception as e:
        logger.error(f"Database connection error in notifications: {e}")
        return None


class NotificationDispatcher:
    """Dispatches webhook payloads to Slack, Teams, Discord, or custom endpoints."""

    @staticmethod
    def get_org_settings(org_id: int) -> Dict[str, Any]:
        conn = get_db_connection()
        if not conn:
            return {"webhook_url": None, "notification_email": None, "auto_remediation_enabled": True}
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT webhook_url, notification_email, auto_remediation_enabled FROM organizations WHERE id = %s;",
                (org_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "webhook_url": row[0],
                    "notification_email": row[1],
                    "auto_remediation_enabled": row[2] if row[2] is not None else True
                }
            return {"webhook_url": None, "notification_email": None, "auto_remediation_enabled": True}
        finally:
            conn.close()

    @staticmethod
    def format_slack_payload(title: str, message: str, severity: str, host_info: str) -> Dict[str, Any]:
        color_map = {
            "CRITICAL": "#ef4444",
            "HIGH": "#f97316",
            "MEDIUM": "#eab308",
            "LOW": "#3b82f6"
        }
        color = color_map.get(severity.upper(), "#38bdf8")
        return {
            "text": f"⚡ *[AI Infra Monitor]* {title}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Severidad", "value": severity.upper(), "short": True},
                        {"title": "Host", "value": host_info, "short": True},
                        {"title": "Detalle del Evento", "value": message, "short": False}
                    ],
                    "footer": "AI Infra Monitor & Disk Analyzer AI Pro"
                }
            ]
        }

    @staticmethod
    def format_teams_payload(title: str, message: str, severity: str, host_info: str) -> Dict[str, Any]:
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "EF4444" if severity.upper() == "CRITICAL" else "F97316",
            "summary": title,
            "sections": [
                {
                    "activityTitle": f"🚨 {title}",
                    "activitySubtitle": f"AI Infra Monitor · Host: {host_info}",
                    "facts": [
                        {"name": "Severidad:", "value": severity.upper()},
                        {"name": "Host:", "value": host_info},
                        {"name": "Mensaje:", "value": message}
                    ],
                    "markdown": True
                }
            ]
        }

    @classmethod
    async def send_webhook(cls, webhook_url: str, title: str, message: str, severity: str = "HIGH", host_info: str = "localhost") -> bool:
        if not webhook_url or not webhook_url.startswith("http"):
            logger.warning(f"Skipping webhook dispatch: invalid URL '{webhook_url}'")
            return False

        try:
            url_lower = webhook_url.lower()
            if "slack.com" in url_lower:
                payload = cls.format_slack_payload(title, message, severity, host_info)
            elif "office.com" in url_lower or "teams" in url_lower:
                payload = cls.format_teams_payload(title, message, severity, host_info)
            else:
                # Generic JSON Webhook
                payload = {
                    "event": "alert_notification",
                    "title": title,
                    "message": message,
                    "severity": severity.upper(),
                    "host": host_info,
                    "system": "AI Infra Monitor Pro"
                }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                if response.is_success or response.status_code in [200, 201, 204]:
                    logger.info(f"Webhook dispatched successfully to {webhook_url[:30]}...")
                    return True
                else:
                    logger.error(f"Webhook HTTP failure {response.status_code}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to dispatch webhook to {webhook_url}: {e}")
            return False

    @classmethod
    async def dispatch_alert_notification(cls, org_id: int, alert_data: Dict[str, Any]) -> bool:
        settings = cls.get_org_settings(org_id)
        webhook_url = settings.get("webhook_url")
        if not webhook_url:
            return False

        severity = alert_data.get("severity", "HIGH")
        title = f"Alerta de Infraestructura: {alert_data.get('rule_name', alert_data.get('metric_name', 'Alerta de Sistema'))}"
        message = alert_data.get("message", "Se ha detectado una anomalía crítica en el servidor.")
        host_info = alert_data.get("hostname", f"Host #{alert_data.get('host_id', 1)}")

        return await cls.send_webhook(webhook_url, title, message, severity, host_info)
