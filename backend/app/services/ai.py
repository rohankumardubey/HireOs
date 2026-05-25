from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from app.core.config import settings


class LLMGateway:
    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()

    def provider_status(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "external_enabled": bool(
                (self.provider == "openai" and settings.openai_api_key)
                or (self.provider == "ollama" and settings.ollama_base_url)
            ),
        }

    def generate_json(self, prompt: str, fallback_factory: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            if self.provider == "openai" and settings.openai_api_key:
                return self._call_openai(prompt)
            if self.provider == "ollama" and settings.ollama_base_url:
                return self._call_ollama(prompt)
        except Exception:
            return fallback_factory()
        return fallback_factory()

    def _call_openai(self, prompt: str) -> dict[str, Any]:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "Return strictly valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

    def _call_ollama(self, prompt: str) -> dict[str, Any]:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": "llama3.1",
                    "format": "json",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            response.raise_for_status()
            message = response.json()["message"]["content"]
            return json.loads(message)

