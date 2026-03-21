"""Tests for core/stage_driver.py and core/llm_client.py enhancements."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from core.llm_client import LLMClient


# ─── LLM Client ───────────────────────────────────────────────────────────────


def test_mock_generate():
    client = LLMClient(provider="mock", model="test-model")
    result = client.generate("Hello world")
    assert "[MOCK:test-model]" in result
    assert "Hello world" in result


def test_mock_generate_empty_prompt():
    client = LLMClient(provider="mock")
    result = client.generate("")
    assert "[MOCK:" in result


def test_mock_structured():
    client = LLMClient(provider="mock")
    schema = {
        "properties": {
            "program_name": {"type": "string", "default": "ORDPRC"},
            "score": {"type": "integer", "default": 8},
        }
    }
    result = client.generate_structured("prompt", schema)
    assert result["program_name"] == "ORDPRC"
    assert result["score"] == 8


def test_ollama_provider_returns_unsupported_error():
    client = LLMClient(provider="ollama", model="nonexistent")
    # We don't assert the model is available; just that unsupported providers raise
    # If we call generate with mock we get a mock response
    client.provider = "unknown_provider"
    from core.exceptions import LLMError
    with pytest.raises(LLMError, match="Unsupported provider"):
        client.generate("test")


def test_llm_client_attributes():
    client = LLMClient(provider="mock", model="llama3.1", base_url="http://x", timeout=60)
    assert client.provider == "mock"
    assert client.model == "llama3.1"
    assert client.base_url == "http://x"
    assert client.timeout == 60


def test_mock_structured_array():
    client = LLMClient(provider="mock")
    schema = {"properties": {"items": {"type": "array", "default": ["a", "b"]}}}
    result = client.generate_structured("", schema)
    assert result["items"] == ["a", "b"]


def test_mock_structured_boolean():
    client = LLMClient(provider="mock")
    schema = {"properties": {"passed": {"type": "boolean", "default": False}}}
    result = client.generate_structured("", schema)
    assert result["passed"] is False


# ─── Ollama availability check ────────────────────────────────────────────────


def test_is_model_available_mock_always_true():
    client = LLMClient(provider="mock", model="any-model")
    assert client.is_model_available() is True


def test_is_model_available_ollama_unreachable(monkeypatch):
    import requests
    client = LLMClient(provider="ollama", model="llama3.1", base_url="http://localhost:19999")
    # Simulate connection error
    class FakeExc(Exception):
        pass
    def fake_get(*args, **kwargs):
        raise requests.RequestException("connection refused")
    import requests as _requests
    monkeypatch.setattr(_requests, "get", fake_get)
    assert client.is_model_available() is False


# ─── Ollama streaming (mock-safe) ─────────────────────────────────────────────


def test_stream_falls_back_to_generate_for_mock():
    client = LLMClient(provider="mock", model="test-model")
    tokens = list(client.stream("hello"))
    # mock provider streams the full response as one token
    assert len(tokens) == 1
    assert "[MOCK:test-model]" in tokens[0]


def test_stream_yields_for_ollama_when_supported():
    client = LLMClient(provider="ollama", model="llama3.1")
    # We can't test real streaming without Ollama, but we verify
    # the method exists and is callable
    import inspect
    assert callable(client.stream)
    sig = inspect.signature(client.stream)
    assert "prompt" in sig.parameters
