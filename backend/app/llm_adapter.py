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
        # Generic text fallback if called directly via analyze_text
        return json.dumps({
            "title": "Diagnóstico Local (Modo Privacidad)",
            "overall_status": "Saludable",
            "explanation_es": "Análisis ejecutado de forma 100% confidencial en tu equipo sin transmitir datos a la nube.",
            "safety_guarantee": "El motor garantiza la protección total de tus proyectos, documentos, fotos y archivos del sistema operativo.",
            "top_recommendations": [
                "Limpia la Caché de Gestores de Paquetes (pip, npm, yarn) para liberar varios GB sin afectar tus proyectos.",
                "Revisa Instaladores Antiguos en la carpeta Descargas y elimina los ejecutables (.exe/.msi) que ya instalaste.",
                "Vacía Archivos Temporales y Papelera de Reciclaje para recuperar espacio inmediato."
            ]
        }, ensure_ascii=False)


def build_rule_based_diagnosis(scan_data: Dict[str, Any], provider_name: str = "Reglas del Sistema") -> Dict[str, Any]:
    """
    Build a dynamic, data-driven quantitative diagnosis from raw scan data
    without relying on static hardcoded fallback strings.
    """
    categories = scan_data.get("categories", {})
    if not isinstance(categories, dict):
        categories = {}
        
    disk_info = scan_data.get("disk_info") or categories.get("disk_info", {})
    if not isinstance(disk_info, dict):
        disk_info = {}

    total_disk = disk_info.get("total", 0)
    used_disk = disk_info.get("used", 0)
    free_disk = disk_info.get("free", 0)
    used_percent = disk_info.get("used_percent") or disk_info.get("percent_used") or 0.0

    # Compute category metrics
    safe_bytes = 0
    dev_bytes = 0
    category_summary = {}

    for cat_key, cat_val in categories.items():
        if cat_key in ["disk_info", "drive"] or not isinstance(cat_val, dict):
            continue
        
        files = cat_val.get("files", [])
        total_cat_bytes = cat_val.get("total_size", sum(f.get("size", 0) for f in files if isinstance(f, dict)))
        file_count = len(files) if files else cat_val.get("file_count", 0)

        if cat_key == "dev_cache":
            dev_bytes += total_cat_bytes
        else:
            safe_bytes += total_cat_bytes

        category_summary[cat_key] = {
            "bytes": total_cat_bytes,
            "mb": round(total_cat_bytes / (1024 * 1024), 2),
            "gb": round(total_cat_bytes / (1024 * 1024 * 1024), 2),
            "count": file_count
        }

    total_analyzed_bytes = scan_data.get("total_size_bytes", safe_bytes + dev_bytes)
    total_analyzed_gb = round(total_analyzed_bytes / (1024 * 1024 * 1024), 2)
    safe_gb = round(safe_bytes / (1024 * 1024 * 1024), 2)
    dev_gb = round(dev_bytes / (1024 * 1024 * 1024), 2)

    # Health score (0 - 100)
    if used_percent > 0:
        health_score = max(0, min(100, int(100 - used_percent)))
    else:
        health_score = 75

    # Urgency
    if used_percent >= 90:
        urgency = "CRÍTICO"
        overall_status = "Crítico"
    elif used_percent >= 80:
        urgency = "ALTO"
        overall_status = "Advertencia"
    elif used_percent >= 60:
        urgency = "MEDIO"
        overall_status = "Advertencia"
    else:
        urgency = "BAJO"
        overall_status = "Saludable"

    # Recommendations
    recommendations = []
    if category_summary.get("pkg_managers", {}).get("gb", 0) > 0.05:
        pip_gb = category_summary["pkg_managers"]["gb"]
        recommendations.append(f"Ejecuta 'pip cache purge' para recuperar {pip_gb} GB de caché de paquetes (100% seguro sin afectar proyectos).")
    
    if category_summary.get("installers", {}).get("gb", 0) > 0.05:
        inst_gb = category_summary["installers"]["gb"]
        recommendations.append(f"Elimina ejecutables de instalación antiguos de Descargas para liberar {inst_gb} GB.")

    if category_summary.get("browser_cache", {}).get("mb", 0) > 10:
        br_mb = category_summary["browser_cache"]["mb"]
        recommendations.append(f"Vacía la caché del navegador Chrome para agilizar el sistema y liberar {br_mb} MB.")

    if category_summary.get("dev_cache", {}).get("gb", 0) > 0.05:
        dev_c_gb = category_summary["dev_cache"]["gb"]
        recommendations.append(f"Revisa carpetas 'venv' o 'node_modules' inactivas para recuperar hasta {dev_c_gb} GB.")

    if not recommendations:
        recommendations.append("El disco presenta una excelente disponibilidad de espacio.")

    return {
        "title": f"Diagnóstico Corporativo de Espacio en Disco ({provider_name})",
        "overall_status": overall_status,
        "health_score": health_score,
        "urgency_level": urgency,
        "explanation_es": (
            f"El almacenamiento del disco se encuentra al {used_percent:.1f}% de ocupación ({overall_status}). "
            f"Se identificaron {total_analyzed_gb} GB en archivos analizados. "
            f"De estos, {safe_gb} GB son totalmente seguros de eliminar sin afectar el sistema ni aplicaciones instaladas, "
            f"y {dev_gb} GB corresponden a cachés de desarrollo opcionales."
        ),
        "safety_guarantee": (
            "Protección de Datos Activada: Ningún documento personal (.pdf, .docx), imagen (.jpg, .png), "
            "video, código fuente o archivo crítico del sistema operativo será modificado ni eliminado."
        ),
        "storage_health": {
            "health_score": health_score,
            "urgency_level": urgency,
            "used_percent": round(used_percent, 2),
            "total_analyzed_gb": total_analyzed_gb,
            "safe_recovery_gb": safe_gb,
            "conditional_recovery_gb": dev_gb
        },
        "top_recommendations": recommendations,
        "categories_advice": {
            "pkg_managers": {
                "what_it_contains": "Archivos de caché HTTP y paquetes wheel de Python/npm descargados previamente.",
                "what_will_be_lost": "Solo la copia local descargada. Si un proyecto requiere la librería, se descargará nuevamente.",
                "is_recommended_to_select": True,
                "risk_note": "100% seguro. No desinstala ningún paquete de tus entornos virtuales activos."
            },
            "installers": {
                "what_it_contains": "Instaladores binarios (.exe, .msi) almacenados en Descargas.",
                "what_will_be_lost": "El archivo instalador original.",
                "is_recommended_to_select": True,
                "risk_note": "Seguro de borrar si el programa ya se encuentra instalado en el equipo."
            },
            "dev_cache": {
                "what_it_contains": "Entornos virtuales (venv), node_modules y carpetas de compilación (build).",
                "what_will_be_lost": "Tendrás que ejecutar 'pip install' o 'npm install' si retomas el proyecto.",
                "is_recommended_to_select": False,
                "risk_note": "Recomendado eliminar únicamente en proyectos inactivos o archivados."
            }
        }
    }


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
            raw_response = await self._call_ollama(prompt)
            result = json.loads(raw_response) if isinstance(raw_response, str) and raw_response.startswith('{') else self._parse_json_response(raw_response)
            if self.redis:
                try:
                    self.redis.setex(cache_key, 3600, json.dumps(result))
                except Exception:
                    pass
            return result
        except Exception as e:
            logger.error(f"Alert analysis error: {e}")
            return {
                "summary": "Analysis failed",
                "causes": [],
                "recommendations": [],
                "confidence": 0.0,
                "error": str(e)
            }

    async def analyze_disk_scan(self, scan_summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze disk scan with configured LLM Provider."""
        if isinstance(self.provider, NoCloudProvider):
            return build_rule_based_diagnosis(scan_summary_data, provider_name=self.provider.get_provider_name())

        prompt = f"""Eres un Asistente Experto en Optimización y Seguridad de Disco Duro (Disk Analyzer AI Pro).
Tu objetivo es analizar los resultados del escaneo de disco y generar una explicación ULTRADETALLADA, clara, profesional y muy tranquilizadora en ESPAÑOL basada en los datos cuantitativos reales.

Proveedor de IA Activo: {self.provider.get_provider_name()}

Datos del Escaneo Real del Usuario:
{json.dumps(scan_summary_data, indent=2, ensure_ascii=False)}

Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
{{
  "title": "Diagnóstico Detallado de Espacio en Disco ({self.provider.get_provider_name()})",
  "overall_status": "Crítico / Advertencia / Saludable",
  "health_score": 0 a 100,
  "urgency_level": "Crítico / Alto / Medio / Bajo",
  "explanation_es": "Resumen ejecutivo con GB/MB reales encontrados y porcentaje de ocupación.",
  "safety_guarantee": "Explicación detallada de por qué el sistema garantiza que NO se borrarán fotos, videos, documentos PDF/Word ni archivos esenciales del sistema operativo.",
  "storage_health": {{
    "health_score": 0 a 100,
    "urgency_level": "Crítico / Alto / Medio / Bajo",
    "safe_recovery_gb": 0.0,
    "conditional_recovery_gb": 0.0
  }},
  "top_recommendations": [
    "Paso 1 sugerido con cifras numéricas concretas",
    "Paso 2 sugerido con cifras numéricas concretas"
  ],
  "categories_advice": {{
    "nombre_categoria": {{
      "what_it_contains": "Qué archivos específicos contiene esta carpeta",
      "what_will_be_lost": "Qué ocurre al borrarlos",
      "is_recommended_to_select": true,
      "risk_note": "Nota tranquilizadora de seguridad aclarando si es 100% seguro"
    }}
  }}
}}"""
        try:
            logger.info(f"Analyzing disk scan via {self.provider.get_provider_name()}...")
            raw_response = await self.provider.analyze_text(prompt)
            parsed = self._parse_json_response(raw_response, scan_summary_data=scan_summary_data)
            return parsed
        except Exception as e:
            logger.error(f"LLM Provider analysis failed ({self.provider.get_provider_name()}): {e}")
            return build_rule_based_diagnosis(scan_summary_data, provider_name=self.provider.get_provider_name())

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

    async def _call_ollama(self, prompt: str) -> str:
        """Legacy helper for Ollama HTTP call."""
        return await self.provider.analyze_text(prompt)

    def _parse_json_response(self, text: str, scan_summary_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse LLM JSON response cleanly."""
        try:
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            # Extract first JSON object block if extra text exists around it
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx + 1]
                return json.loads(json_str)
                
            return json.loads(text)
        except Exception:
            if scan_summary_data:
                return build_rule_based_diagnosis(scan_summary_data, provider_name=self.provider.get_provider_name())
            return {
                "summary": text[:200] if text else "Diagnóstico ejecutado",
                "title": "Diagnóstico de Disco",
                "overall_status": "Completado",
                "explanation_es": text if text else "Análisis completado. Se detectaron cachés y archivos prescindibles para su eliminación segura.",
                "safety_guarantee": "Protección automática activada. Tus documentos, fotos y videos no serán tocados.",
                "top_recommendations": [
                    "Limpia la Caché de Gestores de Paquetes para recuperar gigabytes de forma inmediata sin tocar código fuente.",
                    "Elimina los Instaladores Antiguos de la carpeta Descargas que superen los 30 días.",
                    "Vacía Archivos Temporales y Caché de Navegadores para agilizar el equipo."
                ]
            }

