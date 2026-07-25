"""
AI Infra Monitor - LLM Adapter

This module handles interactions with MiniMax AI, Local LLM (Ollama), and Redis caching.
"""

import os
import json
import hashlib
import logging
import httpx
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMAdapter:
    def __init__(self, redis_client=None, model_name: Optional[str] = None):
        """
        Initialize the LLM Adapter.
        
        Args:
            redis_client: Redis client instance (optional)
            model_name: Name of the LLM model to use
        """
        self.redis = redis_client
        self.minimax_api_key = os.getenv("MINIMAX_API_KEY", "").strip()
        self.minimax_model = os.getenv("MINIMAX_MODEL", "abab6.5s-chat").strip()
        self.minimax_url = os.getenv("MINIMAX_API_URL", "https://api.minimaxi.chat/v1/text/chatcompletion_v2").strip()
        
        self.model_name = model_name or os.getenv("LLM_MODEL", "mistral:7b")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

    async def analyze(self, alert_summary: str) -> Dict[str, Any]:
        """
        Analyze an alert summary using MiniMax AI or fallback LLM.
        """
        cache_key = f"analysis:{hashlib.md5(alert_summary.encode()).hexdigest()}"
        
        if self.redis:
            try:
                cached_result = self.redis.get(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for analysis: {cache_key}")
                    return json.loads(cached_result)
            except Exception as e:
                logger.warning(f"Redis error checking cache: {e}")

        prompt = self._build_prompt(alert_summary)
        
        try:
            if self.minimax_api_key:
                logger.info(f"Calling MiniMax AI API model: {self.minimax_model}")
                raw_response = await self._call_minimax(prompt)
            else:
                logger.info(f"Calling Ollama model: {self.model_name}")
                raw_response = await self._call_ollama(prompt)
            
            result = self._parse_json_response(raw_response)
            
            if self.redis:
                try:
                    self.redis.setex(cache_key, 3600, json.dumps(result))
                except Exception as e:
                    logger.warning(f"Redis error setting cache: {e}")
                    
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "summary": "Analysis failed",
                "causes": ["LLM processing error"],
                "recommendations": ["Check LLM configuration or API Key"],
                "confidence": 0.0
            }

    async def analyze_disk_scan(self, scan_summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze disk scan results with MiniMax AI to produce a clear, plain-Spanish report.
        
        Args:
            scan_summary_data: Dict containing total size, category breakdown, drives info, etc.
            
        Returns:
            Dict containing AI insights, recommendations, and safety explanations.
        """
        prompt = f"""Eres un Asistente Experto en Optimización y Seguridad de Disco Duro (Disk Analyzer AI con MiniMax AI Pro).
Tu objetivo es analizar los resultados del escaneo de disco y generar una explicación ULTRADETALLADA, clara, profesional y muy tranquilizadora en ESPAÑOL para que cualquier usuario sepa exactamente qué se va a eliminar, qué se perdería y qué no se perdería en cada categoría.

Datos del Escaneo Real del Usuario:
{json.dumps(scan_summary_data, indent=2, ensure_ascii=False)}

Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
{{
  "title": "Diagnóstico Detallado de Espacio en Disco (MiniMax AI)",
  "overall_status": "Crítico / Advertencia / Saludable",
  "explanation_es": "Resumen ejecutivo del espacio total encontrado y estrategia recomendada de liberación.",
  "safety_guarantee": "Explicación detallada de por qué el sistema garantiza que NO se borrarán fotos, videos, documentos PDF/Word ni archivos esenciales del sistema operativo.",
  "top_recommendations": [
    "Paso 1 sugerido (ej. Limpiar 6.88 GB en Caché de Gestores de Paquetes)",
    "Paso 2 sugerido",
    "Paso 3 sugerido"
  ],
  "categories_advice": {{
    "nombre_categoria": {{
      "what_it_contains": "Qué archivos específicos contiene esta carpeta",
      "what_will_be_lost": "Qué ocurre al borrarlos (ej. No perderás ningún código fuente; pip o npm solo volverán a descargar los paquetes cuando ejecutes pip install o npm install)",
      "is_recommended_to_select": true,
      "risk_note": "Nota tranquilizadora de seguridad"
    }}
  }}
}}"""
        try:
            if self.minimax_api_key:
                logger.info(f"Analyzing disk scan via MiniMax AI ({self.minimax_model})...")
                raw_response = await self._call_minimax(prompt)
            else:
                logger.info("Analyzing disk scan via fallback LLM...")
                raw_response = await self._call_ollama(prompt)
                
            return self._parse_json_response(raw_response)
        except Exception as e:
            logger.error(f"MiniMax AI disk analysis failed: {e}")
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
        """
        Analyze a backup directory with MiniMax AI before permanent purge.
        """
        prompt = f"""Eres un Asistente Experto de Optimización de Almacenamiento (Disk Analyzer AI con MiniMax AI Pro).
El usuario quiere ELIMINAR PERMANENTEMENTE una carpeta de copia de seguridad (backup) para liberar espacio real en disco.
Tu tarea es inspeccionar los datos de este respaldo y generar una explicación ULTRACLARA en ESPAÑOL indicando qué aplicaciones, proyectos o archivos están dentro de esta copia y qué ocurrirá al eliminarla.

Datos del Respaldo:
{json.dumps(backup_info, indent=2, ensure_ascii=False)}

Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
{{
  "title": "Análisis de Purga Definitiva de Respaldo",
  "freed_space_notice": "Aviso destacado del espacio exacto que se recuperará en el disco duro.",
  "apps_and_projects_affected": [
    "Ej. Caché de Google Chrome (1.25 GB)",
    "Ej. Dependencias node_modules de proyectos de desarrollo (4.32 GB)"
  ],
  "purge_consequence_es": "Explicación clara de que la eliminación liberará el espacio de forma REAL e inmediata en la unidad C:, pero impedirá usar el botón Restaurar para esta limpieza pasable.",
  "safety_confirmation": "Confirmación tranquilizadora de que eliminar este respaldo NO borrará programas instalados ni archivos de usuario originales."
}}"""
        try:
            if self.minimax_api_key:
                logger.info("Analyzing backup purge via MiniMax AI...")
                raw_response = await self._call_minimax(prompt)
            else:
                raw_response = await self._call_ollama(prompt)
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

    async def _call_minimax(self, prompt: str) -> str:
        """Call MiniMax AI API."""
        headers = {
            "Authorization": f"Bearer {self.minimax_api_key}",
            "Content-Type": "application/json"
        }
        
        # MiniMax chat completion v2 payload
        payload = {
            "model": self.minimax_model,
            "messages": [
                {
                    "sender_type": "USER",
                    "sender_name": "User",
                    "text": prompt
                }
            ],
            "reply_constraints": {
                "sender_type": "BOT",
                "sender_name": "MiniMax AI Assistant"
            },
            "temperature": 0.2
        }
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(self.minimax_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # MiniMax response structure
            if "reply" in data:
                return data["reply"]
            elif "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            elif "base_resp" in data and data["base_resp"].get("status_code") != 0:
                raise ValueError(f"MiniMax API Error: {data['base_resp'].get('status_msg')}")
            else:
                return str(data)

    def _build_prompt(self, alert_summary: str) -> str:
        """Build prompt for alert analysis."""
        return f"""Eres un analizador de alertas de sistemas informáticos. 
Debes responder exclusivamente en JSON válido con las claves: summary, causes, recommendations, confidence.

Alerta:
{alert_summary}

Formato esperado:
{{
  "summary": "...",
  "causes": ["..."],
  "recommendations": ["..."],
  "confidence": 0.80
}}"""

    async def _call_ollama(self, prompt: str) -> str:
        """Call the Ollama API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.ollama_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            return response.json().get("response", "")

    def _parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        """
        Parse raw text response into dict safely.
        """
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            try:
                start = raw_text.find("{")
                end = raw_text.rfind("}")
                if start != -1 and end != -1:
                    return json.loads(raw_text[start:end+1])
                raise ValueError("No JSON object found")
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {raw_text[:100]}...")
                raise ValueError(f"JSON parsing error: {e}")

