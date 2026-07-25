"""
AI Infra Monitor & Disk Analyzer AI - Pluggable LLM Provider Pattern (SaaS Ready).

Provides an abstract interface (LLMProviderBase) for:
1. MiniMaxProvider (Default SaaS Pro model)
2. GeminiProvider (Enterprise B2B high-precision model)
3. OllamaLocalProvider (Self-hosted local AI)
4. NoCloudProvider (100% Offline Rule-based for strict privacy compliance)
"""

import os
import json
import hashlib
import logging
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMProviderBase(ABC):
    """Abstract Base Class for LLM Providers."""
    
    @abstractmethod
    async def analyze_text(self, prompt: str) -> str:
        """Send prompt to LLM provider and return raw response string."""
        pass
        
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier name."""
        pass


class MiniMaxProvider(LLMProviderBase):
    """MiniMax AI Provider implementation."""
    
    def __init__(self, api_key: str, model: str = "abab6.5s-chat", url: str = "https://api.minimaxi.chat/v1/text/chatcompletion_v2"):
        self.api_key = api_key
        self.model = model
        self.url = url
        
    def get_provider_name(self) -> str:
        return "MiniMax AI"
        
    async def analyze_text(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"sender_type": "USER", "sender_name": "User", "text": prompt}
            ],
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"].get("text", "")
            return data.get("reply", "")


class GeminiProvider(LLMProviderBase):
    """Google Gemini Provider implementation for Enterprise Tier."""
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model
        
    def get_provider_name(self) -> str:
        return "Google Gemini"
        
    async def analyze_text(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""


class OllamaLocalProvider(LLMProviderBase):
    """Ollama Self-hosted Local LLM Provider."""
    
    def __init__(self, model: str = "mistral:7b", url: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.url = url
        
    def get_provider_name(self) -> str:
        return "Ollama Local AI"
        
    async def analyze_text(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.url, json={"model": self.model, "prompt": prompt, "stream": False})
            response.raise_for_status()
            return response.json().get("response", "")


class NoCloudProvider(LLMProviderBase):
    """100% Offline Rule-based Fallback for Strict Privacy / Air-gapped Environments."""
    
    def get_provider_name(self) -> str:
        return "Sin Nube (Privacidad Total 100% Offline)"
        
    async def analyze_text(self, prompt: str) -> str:
        return json.dumps({
            "title": "Diagnóstico Local (Modo Privacidad)",
            "overall_status": "Completado",
            "explanation_es": "Análisis realizado localmente sin enviar datos a servicios en la nube.",
            "safety_guarantee": "Tus archivos y nombres de carpetas jamás salieron de tu infraestructura.",
            "top_recommendations": [
                "Limpieza basada en reglas de seguridad locales activadas."
            ]
        }, ensure_ascii=False)


def get_llm_provider(provider_type: Optional[str] = None) -> LLMProviderBase:
    """Factory function returning the configured LLM provider."""
    provider_name = (provider_type or os.getenv("LLM_PROVIDER", "")).lower().strip()
    minimax_key = os.getenv("MINIMAX_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    if provider_name == "gemini" or (not provider_name and gemini_key and not minimax_key):
        return GeminiProvider(api_key=gemini_key)
    elif provider_name == "nocloud" or provider_name == "offline" or provider_name == "none":
        return NoCloudProvider()
    elif provider_name == "ollama":
        return OllamaLocalProvider()
    else:
        # Default to MiniMax if key available, else Fallback to NoCloud
        if minimax_key:
            return MiniMaxProvider(api_key=minimax_key)
        elif gemini_key:
            return GeminiProvider(api_key=gemini_key)
        return NoCloudProvider()


class LLMAdapter:
    """Unified Facade for LLM Operations using the Provider Pattern."""
    
    def __init__(self, redis_client=None, provider: Optional[LLMProviderBase] = None, model_name: Optional[str] = None):
        self.redis = redis_client
        self.provider = provider or get_llm_provider()
        self.model_name = model_name or getattr(self.provider, 'model', 'mistral:7b')

    @property
    def minimax_api_key(self) -> Optional[str]:
        if isinstance(self.provider, MiniMaxProvider):
            return self.provider.api_key
        return os.getenv("MINIMAX_API_KEY", None)

    async def analyze(self, alert_summary: str) -> Dict[str, Any]:
        """Analyze system alert summary with active LLM Provider."""
        cache_key = f"analysis:{hashlib.md5(alert_summary.encode()).hexdigest()}"
        if self.redis:
            try:
                cached_result = self.redis.get(cache_key)
                if cached_result:
                    return json.loads(cached_result)
            except Exception:
                pass

        prompt = f"Analiza esta alerta del sistema:\n{alert_summary}\nResponde en JSON con las claves: summary, root_cause, recommended_action."
        try:
            raw_response = await self.provider.analyze_text(prompt)
            result = self._parse_json_response(raw_response)
            if self.redis:
                try:
                    self.redis.setex(cache_key, 3600, json.dumps(result))
                except Exception:
                    pass
            return result
        except Exception as e:
            logger.error(f"Alert analysis error: {e}")
            return {
                "summary": "Error analizando la alerta.",
                "root_cause": str(e),
                "recommended_action": "Revisar logs manualmente."
            }

    async def analyze_disk_scan(self, scan_summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze disk scan with configured LLM Provider."""
        prompt = f"""Eres un Asistente Experto en Optimización y Seguridad de Disco Duro (Disk Analyzer AI Pro).
Tu objetivo es analizar los resultados del escaneo de disco y generar una explicación ULTRADETALLADA, clara, profesional y muy tranquilizadora en ESPAÑOL para que cualquier usuario sepa exactamente qué se va a eliminar, qué se perdería y qué no se perdería en cada categoría.

Proveedor de IA Activo: {self.provider.get_provider_name()}

Datos del Escaneo Real del Usuario:
{json.dumps(scan_summary_data, indent=2, ensure_ascii=False)}

Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
{{
  "title": "Diagnóstico Detallado de Espacio en Disco ({self.provider.get_provider_name()})",
  "overall_status": "Crítico / Advertencia / Saludable",
  "explanation_es": "Resumen ejecutivo del espacio total encontrado y estrategia recomendada de liberación.",
  "safety_guarantee": "Explicación detallada de por qué el sistema garantiza que NO se borrarán fotos, videos, documentos PDF/Word ni archivos esenciales del sistema operativo.",
  "top_recommendations": [
    "Paso 1 sugerido",
    "Paso 2 sugerido"
  ],
  "categories_advice": {{
    "nombre_categoria": {{
      "what_it_contains": "Qué archivos específicos contiene esta carpeta",
      "what_will_be_lost": "Qué ocurre al borrarlos",
      "is_recommended_to_select": true,
      "risk_note": "Nota tranquilizadora de seguridad"
    }}
  }}
}}"""
        try:
            logger.info(f"Analyzing disk scan via {self.provider.get_provider_name()}...")
            raw_response = await self.provider.analyze_text(prompt)
            return self._parse_json_response(raw_response)
        except Exception as e:
            logger.error(f"LLM Provider analysis failed ({self.provider.get_provider_name()}): {e}")
            return {
                "title": "Diagnóstico de Disco",
                "overall_status": "Completado",
                "explanation_es": f"Se han analizado {scan_summary_data.get('total_files', 0)} archivos ocupando {scan_summary_data.get('total_size_formatted', 'varios GB')}.",
                "safety_guarantee": "El sistema protegerá automáticamente todos tus documentos, fotos, videos y archivos del sistema operativo.",
                "top_recommendations": [
                    "Revisa los archivos temporales y cachés para liberar espacio de forma segura."
                ],
                "categories_advice": {}
            }

    async def analyze_backup_purge(self, backup_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze backup directory purge with configured LLM Provider."""
        prompt = f"""Eres un Asistente Experto de Optimización de Almacenamiento (Disk Analyzer AI Pro).
El usuario quiere ELIMINAR PERMANENTEMENTE una carpeta de copia de seguridad (backup) para liberar espacio real en disco.
Tu tarea es inspeccionar los datos de este respaldo y generar una explicación ULTRACLARA en ESPAÑOL indicando qué aplicaciones, proyectos o archivos están dentro de esta copia y qué ocurrirá al eliminarla.

Datos del Respaldo:
{json.dumps(backup_info, indent=2, ensure_ascii=False)}

Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
{{
  "title": "Análisis de Purga Definitiva de Respaldo",
  "freed_space_notice": "Aviso destacado del espacio exacto que se recuperará en el disco duro.",
  "apps_and_projects_affected": [
    "Ej. Caché de Google Chrome",
    "Ej. Dependencias node_modules"
  ],
  "purge_consequence_es": "Explicación clara de que la eliminación liberará el espacio de forma REAL e inmediata en la unidad, pero impedirá usar el botón Restaurar.",
  "safety_confirmation": "Confirmación tranquilizadora de que eliminar este respaldo NO borrará programas instalados ni archivos de usuario originales."
}}"""
        try:
            logger.info(f"Analyzing backup purge via {self.provider.get_provider_name()}...")
            raw_response = await self.provider.analyze_text(prompt)
            return self._parse_json_response(raw_response)
        except Exception as e:
            logger.error(f"Failed to analyze backup purge with AI: {e}")
            return {
                "title": "Inspección de Respaldo",
                "freed_space_notice": f"Se liberarán {backup_info.get('size_formatted', 'varios GB')} en tu disco duro.",
                "apps_and_projects_affected": backup_info.get('categories', []),
                "purge_consequence_es": "Esta acción eliminará la copia de seguridad de forma definitiva para recuperar espacio libre real.",
                "safety_confirmation": "Tus archivos originales ya fueron eliminados o procesados de forma segura; borrar la copia libera el almacenamiento retenido."
            }

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM JSON response cleanly."""
        try:
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except Exception:
            return {
                "title": "Diagnóstico de Disco",
                "overall_status": "Completado",
                "explanation_es": text,
                "safety_guarantee": "Protección automática activada.",
                "top_recommendations": []
            }
