from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Dict
from urllib import error, request

from engine.ai.types import ProviderPolicy


class ModelProvider(ABC):
    id: str = ""
    provider_kind: str = "local"

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        raise NotImplementedError


class RuleBasedLocalProvider(ModelProvider):
    id = "rule_based_local"
    provider_kind = "local"

    def is_available(self) -> bool:
        return True

    def describe(self) -> str:
        return "Rule-based local planner for deterministic authoring flows"

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        return ""


class OllamaLocalProvider(ModelProvider):
    id = "ollama_local"
    provider_kind = "local"

    def __init__(self, endpoint: str = "http://127.0.0.1:11434") -> None:
        self._default_endpoint = endpoint

    def is_available(self) -> bool:
        try:
            self._request_json("/api/tags", None, ProviderPolicy(endpoint=self._default_endpoint))
            return True
        except Exception:
            return False

    def describe(self) -> str:
        return "Ollama local provider over HTTP for on-device model inference"

    def list_models(self, policy: ProviderPolicy) -> list[str]:
        payload = self._request_json("/api/tags", None, policy)
        return [str(item.get("name", "")).strip() for item in payload.get("models", []) if str(item.get("name", "")).strip()]

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        model_name = (policy.model_name or "").strip()
        if not model_name:
            models = self.list_models(policy)
            if not models:
                return ""
            model_name = models[0]
        payload = self._request_json(
            "/api/generate",
            {
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
            },
            policy,
        )
        return str(payload.get("response", "")).strip()

    def _request_json(self, path: str, payload: dict | None, policy: ProviderPolicy) -> dict:
        endpoint = (policy.endpoint or self._default_endpoint).rstrip("/")
        req = request.Request(f"{endpoint}{path}")
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            req.add_header("Content-Type", "application/json")
            req.data = body
        try:
            with request.urlopen(req, timeout=2.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc


class StubCloudProvider(ModelProvider):
    id = "stub_cloud"
    provider_kind = "cloud"

    def is_available(self) -> bool:
        return True

    def describe(self) -> str:
        return "Stub cloud connector reserved for future remote LLM integrations"

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        return ""


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, ModelProvider] = {
            RuleBasedLocalProvider.id: RuleBasedLocalProvider(),
            OllamaLocalProvider.id: OllamaLocalProvider(),
            StubCloudProvider.id: StubCloudProvider(),
        }

    def list_providers(self) -> list[dict]:
        return [
            {
                "id": provider.id,
                "kind": provider.provider_kind,
                "available": provider.is_available(),
                "description": provider.describe(),
            }
            for provider in self._providers.values()
        ]

    def resolve(self, policy: ProviderPolicy) -> ModelProvider:
        preferred = self._providers.get(policy.preferred_provider)
        if preferred is not None and preferred.is_available():
            if preferred.provider_kind == "cloud" and policy.mode == "local":
                pass
            elif preferred.provider_kind == "local" and policy.mode == "cloud":
                pass
            else:
                return preferred

        if policy.mode == "cloud":
            return self._providers[StubCloudProvider.id]
        ollama = self._providers[OllamaLocalProvider.id]
        if ollama.is_available():
            return ollama
        return self._providers[RuleBasedLocalProvider.id]

    def _request_json(self, path: str, payload: dict | None, policy: ProviderPolicy) -> dict:
        provider = self._providers.get(OllamaLocalProvider.id)
        if isinstance(provider, OllamaLocalProvider):
            return provider._request_json(path, payload, policy)
        return {}
