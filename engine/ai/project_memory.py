from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from engine.ai.types import MutationPolicy, ProviderPolicy


class ProjectMemoryStore:
    FILE_NAME = "ai_project_memory.json"

    def __init__(self, project_service) -> None:
        self._project_service = project_service

    @property
    def path(self) -> Path:
        if not self._project_service.has_project:
            return self._project_service.global_state_dir / self.FILE_NAME
        return self._project_service.get_project_path("meta") / self.FILE_NAME

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self.default_memory()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            return self.default_memory()
        return self._normalize(raw)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=4)
        return normalized

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        current = self.load()
        merged = self._deep_merge(current, patch)
        return self.save(merged)

    def default_memory(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "project_name": self._project_service.project_name if self._project_service.has_project else "",
            "game_profile": {
                "genre": "",
                "target_audience": "",
                "visual_style": "",
                "placeholder_strategy": "project_assets_or_placeholders",
            },
            "confirmed_decisions": [],
            "pending_questions": [],
            "conventions": {},
            "important_assets": [],
            "important_prefabs": [],
            "restrictions": {},
            "notes": [],
            "provider_policy": ProviderPolicy().to_dict(),
            "mutation_policy": MutationPolicy().to_dict(),
            "last_plan_summary": "",
        }

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        current = self.default_memory()
        if not isinstance(data, dict):
            return current
        merged = self._deep_merge(current, data)
        merged["provider_policy"] = self._normalize_policy(merged.get("provider_policy", {}), ProviderPolicy().to_dict())
        merged["mutation_policy"] = self._normalize_policy(merged.get("mutation_policy", {}), MutationPolicy().to_dict())
        return merged

    def _normalize_policy(self, raw: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(defaults)
        if not isinstance(raw, dict):
            return result
        for key, value in raw.items():
            if key in result:
                result[key] = value
        return result

    def _deep_merge(self, base: Any, override: Any) -> Any:
        if isinstance(base, dict) and isinstance(override, dict):
            merged = dict(base)
            for key, value in override.items():
                merged[key] = self._deep_merge(merged.get(key), value) if key in merged else value
            return merged
        return override
