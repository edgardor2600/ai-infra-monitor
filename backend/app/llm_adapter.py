"""
AI Infra Monitor - LLM Adapter

This module handles interactions with the Local LLM (Ollama) and caching via Redis.
"""

import json
import hashlib
import logging
import httpx
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMAdapter:
    def __init__(self, redis_client, model_name: str = "mistral:7b"):
        """
        Initialize the LLM Adapter.
        
        Args:
            redis_client: Redis client instance
            model_name: Name of the Ollama model to use
        """
        self.redis = redis_client
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"

    async def analyze(self, alert_summary: str) -> Dict[str, Any]:
        """
        Analyze an alert summary using the LLM.
        
        1. Check cache
        2. If miss, call Ollama
        3. Parse result
        4. Cache result
        
        Args:
            alert_summary: Text description of the alert
            
        Returns:
            Dict containing analysis result (summary, causes, recommendations, confidence)
        """
        # 1. Check cache
        cache_key = f"analysis:{hashlib.md5(alert_summary.encode()).hexdigest()}"
        
        try:
            cached_result = self.redis.get(cache_key)
            if cached_result:
                logger.info(f"Cache hit for analysis: {cache_key}")
                return json.loads(cached_result)
        except Exception as e:
            logger.warning(f"Redis error checking cache: {e}")

        # 2. Call Ollama
        logger.info(f"Cache miss. Calling Ollama model: {self.model_name}")
        prompt = self._build_prompt(alert_summary)
        
        try:
            raw_response = await self._call_ollama(prompt)
            
            # 3. Parse result
            result = self._parse_json_response(raw_response)
            
            # 4. Cache result (TTL 1h = 3600s)
            try:
                self.redis.setex(cache_key, 3600, json.dumps(result))
            except Exception as e:
                logger.warning(f"Redis error setting cache: {e}")
                
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # Return a fallback structure in case of failure
            return {
                "summary": "Analysis failed",
                "causes": ["LLM processing error"],
                "recommendations": ["Check LLM logs"],
                "confidence": 0.0
            }

    def _build_prompt(self, alert_summary: str) -> str:
        """Build the prompt for the LLM."""
        return f"""Eres un analizador de alertas de sistemas. 
Debes responder exclusivamente en JSON valido con las claves:
summary, causes, recommendations, confidence.

Alerta:
{alert_summary}

Formato final esperado:
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
                    "format": "json"  # Force JSON mode if supported by model/version
                }
            )
            response.raise_for_status()
            return response.json().get("response", "")

    def _parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        """
        Parse the raw text response from the LLM into a dictionary.
        Robustly handles potential extra text around the JSON.
        """
        try:
            # Try direct parsing first
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to find JSON block
            try:
                start = raw_text.find("{")
                end = raw_text.rfind("}")
                
                if start != -1 and end != -1:
                    json_str = raw_text[start:end+1]
                    return json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in response")
            except Exception as e:
                logger.error(f"Failed to parse JSON from LLM response: {raw_text[:100]}...")
                raise ValueError(f"JSON parsing failed: {e}")
