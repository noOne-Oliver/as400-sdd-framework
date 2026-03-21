"""LLM client supporting mock, Ollama, and OpenAI-compatible APIs."""

from __future__ import annotations

import json
import os
from typing import Any, Iterator, Optional

import requests

from .exceptions import LLMError


class LLMClient:
    """Minimal client wrapper used by agents and judge components.

    Provider "ollama": real local LLM via Ollama REST API.
    Provider "mock": deterministic fake responses for testing.
    Provider "openai" / "openai-compatible": OpenAI-compatible REST API.
    """

    def __init__(
        self,
        provider: str = "mock",
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
    ):
        self.provider = provider.lower()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, **kwargs: Any) -> str:
        if self.provider == "mock":
            return self._mock_generate(prompt, **kwargs)
        if self.provider == "ollama":
            return self._generate_ollama(prompt, **kwargs)
        if self.provider in {"openai", "openai-compatible"}:
            return self._generate_openai_compatible(prompt, **kwargs)
        raise LLMError(f"Unsupported provider: {self.provider}")

    def generate_structured(self, prompt: str, schema: dict) -> dict:
        if self.provider == "mock":
            return self._mock_structured(schema)

        response = self.generate(
            f"{prompt}\n\nReturn a JSON object matching this schema:\n"
            f"{json.dumps(schema, ensure_ascii=True, indent=2)}"
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Structured response was not valid JSON: {exc}") from exc

    def is_model_available(self) -> bool:
        """Check whether the configured model is loaded in Ollama (ping /api/tags)."""
        if self.provider != "ollama":
            return True
        try:
            resp = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10,
            )
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            return any(self.model in m.get("name", "") for m in models)
        except requests.RequestException:
            return False

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Yield response tokens as they arrive. Only supported for ollama provider."""
        if self.provider == "ollama":
            yield from self._stream_ollama(prompt, **kwargs)
        else:
            yield self.generate(prompt, **kwargs)

    def _generate_ollama(self, prompt: str, **kwargs: Any) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        payload.update(kwargs)
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.RequestException as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

    def _stream_ollama(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        payload.update(kwargs)
        try:
            with requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if line:
                        try:
                            token = json.loads(line).get("response", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
        except requests.RequestException as exc:
            raise LLMError(f"Ollama stream request failed: {exc}") from exc

    def _generate_openai_compatible(self, prompt: str, **kwargs: Any) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "mock-api-key")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an AS400 development expert."},
                {"role": "user", "content": prompt},
            ],
            "temperature": kwargs.get("temperature", 0.1),
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            return body["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError) as exc:
            raise LLMError(f"OpenAI-compatible request failed: {exc}") from exc

    def _mock_generate(self, prompt: str, **_: Any) -> str:
        headline = prompt.strip().splitlines()[0] if prompt.strip() else "AS400 prompt"
        return (
            f"[MOCK:{self.model}] {headline}\n"
            "This response was generated in mock mode for deterministic testing."
        )

    def _mock_structured(self, schema: dict) -> dict:
        properties = schema.get("properties", {})
        structured: dict = {}
        for key, definition in properties.items():
            field_type = definition.get("type", "string")
            if field_type == "array":
                structured[key] = definition.get("default", [])
            elif field_type == "boolean":
                structured[key] = definition.get("default", True)
            elif field_type == "integer":
                structured[key] = definition.get("default", 8)
            elif field_type == "object":
                structured[key] = definition.get("default", {})
            else:
                structured[key] = definition.get("default", f"mock-{key}")
        return structured
