from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, Dict, List, Optional
from urllib import error, request

from engine.ai.types import ProviderPolicy


def _extract_json_object(payload: str) -> Optional[Dict[str, Any]]:
    text = str(payload or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


class ModelProvider(ABC):
    id: str = ""
    provider_kind: str = "local"

    @abstractmethod
    def is_available(self, policy: Optional[ProviderPolicy] = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        raise NotImplementedError

    def list_models(self, policy: ProviderPolicy) -> List[str]:
        return []

    def plan_turn(
        self,
        prompt: str,
        answers: Dict[str, Any],
        policy: ProviderPolicy,
        context: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        session_mode: str,
    ) -> Optional[Dict[str, Any]]:
        return None


class RuleBasedLocalProvider(ModelProvider):
    id = "rule_based_local"
    provider_kind = "local"

    def is_available(self, policy: Optional[ProviderPolicy] = None) -> bool:
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
        self._availability_timeout = 1.5
        self._generation_timeout = 20.0

    def is_available(self, policy: Optional[ProviderPolicy] = None) -> bool:
        try:
            effective_policy = policy or ProviderPolicy(endpoint=self._default_endpoint)
            self._request_json("/api/tags", None, effective_policy, timeout=self._availability_timeout)
            return True
        except Exception:
            return False

    def describe(self) -> str:
        return "Ollama local provider over HTTP for on-device model inference"

    def list_models(self, policy: ProviderPolicy) -> List[str]:
        payload = self._request_json("/api/tags", None, policy, timeout=self._availability_timeout)
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
            timeout=self._generation_timeout,
        )
        return str(payload.get("response", "")).strip()

    def plan_turn(
        self,
        prompt: str,
        answers: Dict[str, Any],
        policy: ProviderPolicy,
        context: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        session_mode: str,
    ) -> Optional[Dict[str, Any]]:
        instruction = self._planning_prompt(prompt, answers, context, available_tools, session_mode)
        completion = self.complete(
            prompt=instruction,
            system_prompt="Return only valid JSON for the requested plan turn.",
            policy=policy,
        )
        return _extract_json_object(completion)

    def _planning_prompt(
        self,
        prompt: str,
        answers: Dict[str, Any],
        context: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        session_mode: str,
    ) -> str:
        return json.dumps(
            {
                "task": "Produce a compact JSON planning turn for a game-authoring assistant.",
                "session_mode": session_mode,
                "prompt": prompt,
                "answers": answers,
                "context_window": {
                    "scene_path": context.get("scene_path", ""),
                    "selected_entity": context.get("selected_entity", ""),
                    "entity_count": context.get("entity_count", 0),
                    "recent_scripts": context.get("recent_scripts", []),
                    "recent_assets": context.get("recent_assets", []),
                    "tool_results": context.get("tool_results", []),
                    "summary": context.get("summary", {}),
                },
                "available_tools": available_tools,
                "rules": [
                    "In build mode, prefer returning concrete tool_calls instead of a generic analysis.",
                    "For new gameplay behaviours, use write_script plus add_script_behaviour when possible.",
                    "Only ask a blocking question if a specific missing entity or asset prevents a reasonable attempt.",
                ],
                "response_schema": {
                    "summary": "string",
                    "reasoning": "string",
                    "project_findings": ["string"],
                    "next_steps": ["string"],
                    "can_build_now": "boolean",
                    "blocking_questions": [{"id": "string", "text": "string", "rationale": "string", "choices": ["string"]}],
                    "tool_calls": [{"tool_name": "string", "summary": "string", "arguments": {}}],
                },
            },
            ensure_ascii=False,
        )

    def _request_json(self, path: str, payload: Optional[dict], policy: ProviderPolicy, timeout: Optional[float] = None) -> dict:
        endpoint = (policy.endpoint or self._default_endpoint).rstrip("/")
        req = request.Request(f"{endpoint}{path}")
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            req.add_header("Content-Type", "application/json")
            req.data = body
        try:
            with request.urlopen(req, timeout=timeout or self._generation_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc


class OpenAICompatibleProvider(ModelProvider):
    id = "openai_compatible_http"
    provider_kind = "hybrid"

    def __init__(self, endpoint: str = "http://127.0.0.1:8000/v1") -> None:
        self._default_endpoint = endpoint.rstrip("/")
        self._availability_timeout = 1.5
        self._generation_timeout = 20.0

    def is_available(self, policy: Optional[ProviderPolicy] = None) -> bool:
        try:
            effective_policy = policy or ProviderPolicy(endpoint=self._default_endpoint)
            self._request_json("/models", None, effective_policy, timeout=self._availability_timeout)
            return True
        except Exception:
            return False

    def describe(self) -> str:
        return "OpenAI-compatible HTTP provider for local or remote chat/completions backends"

    def list_models(self, policy: ProviderPolicy) -> List[str]:
        payload = self._request_json("/models", None, policy, timeout=self._availability_timeout)
        return [str(item.get("id", "")).strip() for item in payload.get("data", []) if str(item.get("id", "")).strip()]

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        model_name = (policy.model_name or "").strip()
        if not model_name:
            models = self.list_models(policy)
            if not models:
                return ""
            model_name = models[0]
        payload = self._request_json(
            "/chat/completions",
            {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            policy,
            timeout=self._generation_timeout,
        )
        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {}) or {}
        return str(message.get("content", "")).strip()

    def plan_turn(
        self,
        prompt: str,
        answers: Dict[str, Any],
        policy: ProviderPolicy,
        context: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        session_mode: str,
    ) -> Optional[Dict[str, Any]]:
        instruction = json.dumps(
            {
                "task": "Produce one JSON planning turn for a game-authoring assistant.",
                "session_mode": session_mode,
                "prompt": prompt,
                "answers": answers,
                "context_window": {
                    "scene_path": context.get("scene_path", ""),
                    "selected_entity": context.get("selected_entity", ""),
                    "entity_count": context.get("entity_count", 0),
                    "recent_scripts": context.get("recent_scripts", []),
                    "recent_assets": context.get("recent_assets", []),
                    "tool_results": context.get("tool_results", []),
                    "summary": context.get("summary", {}),
                },
                "available_tools": available_tools,
                "rules": [
                    "In build mode, prefer returning concrete tool_calls instead of a generic analysis.",
                    "For new gameplay behaviours, use write_script plus add_script_behaviour when possible.",
                    "Only ask a blocking question if a specific missing entity or asset prevents a reasonable attempt.",
                ],
                "response_schema": {
                    "summary": "string",
                    "reasoning": "string",
                    "project_findings": ["string"],
                    "next_steps": ["string"],
                    "can_build_now": "boolean",
                    "blocking_questions": [{"id": "string", "text": "string", "rationale": "string", "choices": ["string"]}],
                    "tool_calls": [{"tool_name": "string", "summary": "string", "arguments": {}}],
                },
            },
            ensure_ascii=False,
        )
        completion = self.complete(
            prompt=instruction,
            system_prompt="Return only valid JSON that matches the requested schema.",
            policy=policy,
        )
        return _extract_json_object(completion)

    def _request_json(self, path: str, payload: Optional[dict], policy: ProviderPolicy, timeout: Optional[float] = None) -> dict:
        endpoint = (policy.endpoint or self._default_endpoint).rstrip("/")
        url = f"{endpoint}{path}"
        req = request.Request(url)
        req.add_header("Content-Type", "application/json")
        api_key = (policy.api_key or "").strip()
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        if payload is not None:
            req.data = json.dumps(payload).encode("utf-8")
        try:
            with request.urlopen(req, timeout=timeout or self._generation_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc


class StubCloudProvider(ModelProvider):
    id = "stub_cloud"
    provider_kind = "cloud"

    def is_available(self, policy: Optional[ProviderPolicy] = None) -> bool:
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
            OpenAICompatibleProvider.id: OpenAICompatibleProvider(),
            StubCloudProvider.id: StubCloudProvider(),
        }

    def list_providers(self) -> List[dict]:
        default_policy = ProviderPolicy()
        return [
            {
                "id": provider.id,
                "kind": provider.provider_kind,
                "available": provider.is_available(default_policy),
                "description": provider.describe(),
            }
            for provider in self._providers.values()
        ]

    def resolve(self, policy: ProviderPolicy) -> ModelProvider:
        preferred = self._providers.get(policy.preferred_provider)
        if preferred is not None and preferred.is_available(policy):
            if preferred.provider_kind == "cloud" and policy.mode == "local":
                pass
            elif preferred.provider_kind == "local" and policy.mode == "cloud":
                pass
            else:
                return preferred

        if policy.mode == "cloud":
            return self._providers[StubCloudProvider.id]

        openai_compatible = self._providers[OpenAICompatibleProvider.id]
        if policy.preferred_provider == OpenAICompatibleProvider.id and openai_compatible.is_available(policy):
            return openai_compatible

        ollama = self._providers[OllamaLocalProvider.id]
        if ollama.is_available(policy):
            return ollama

        if openai_compatible.is_available(policy):
            return openai_compatible

        return self._providers[RuleBasedLocalProvider.id]
