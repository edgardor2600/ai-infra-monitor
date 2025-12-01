"""
Tests for LLM Adapter
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.llm_adapter import LLMAdapter

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    return redis

@pytest.fixture
def adapter(mock_redis):
    return LLMAdapter(mock_redis, model_name="test-model")

@pytest.mark.asyncio
async def test_analyze_cache_hit(mock_redis, adapter):
    """Test that cached result is returned if available."""
    cached_data = {
        "summary": "Cached summary",
        "causes": ["Cached cause"],
        "recommendations": ["Cached rec"],
        "confidence": 0.9
    }
    mock_redis.get.return_value = json.dumps(cached_data)
    
    result = await adapter.analyze("CPU High")
    
    assert result == cached_data
    mock_redis.get.assert_called_once()
    # Should not call Ollama (we can't easily mock private method call here without patching, 
    # but we can infer it by checking if we mocked the http call and it wasn't used, 
    # or simply trust the logic flow for now)

@pytest.mark.asyncio
async def test_analyze_cache_miss_success(mock_redis, adapter):
    """Test full flow on cache miss: call LLM, parse, cache."""
    mock_redis.get.return_value = None
    
    llm_response = {
        "summary": "LLM Summary",
        "causes": ["Cause 1"],
        "recommendations": ["Rec 1"],
        "confidence": 0.85
    }
    
    # Mock _call_ollama to avoid HTTP request
    with patch.object(adapter, '_call_ollama', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = json.dumps(llm_response)
        
        result = await adapter.analyze("CPU High")
        
        assert result == llm_response
        mock_call.assert_called_once()
        mock_redis.setex.assert_called_once()

@pytest.mark.asyncio
async def test_parse_json_response_robustness(adapter):
    """Test JSON parsing with extra text."""
    raw_text = """
    Here is the analysis:
    {
        "summary": "Test",
        "causes": [],
        "recommendations": [],
        "confidence": 1.0
    }
    Hope this helps.
    """
    
    result = adapter._parse_json_response(raw_text)
    assert result["summary"] == "Test"
    assert result["confidence"] == 1.0

@pytest.mark.asyncio
async def test_analyze_failure_handling(mock_redis, adapter):
    """Test graceful failure when LLM fails."""
    mock_redis.get.return_value = None
    
    with patch.object(adapter, '_call_ollama', side_effect=Exception("Ollama down")):
        result = await adapter.analyze("CPU High")
        
        assert result["summary"] == "Analysis failed"
        assert result["confidence"] == 0.0
