from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.ai.capabilities import build_capability_registry, capability_index
from engine.ai.types import AIContextWindow


class ContextAssembler:
    def __init__(self, engine_api, skill_registry, memory_store) -> None:
        self._engine_api = engine_api
        self._skill_registry = skill_registry
        self._memory_store = memory_store

    def assemble(self, prompt: str) -> Dict[str, Any]:
        window = self.assemble_window(prompt)
        project_service = self._engine_api.project_service
        skills = self._skill_registry.match(prompt)
        levels = self._list_relative_paths(project_service.get_project_path("levels"), project_service.project_root)
        prefabs = self._list_relative_paths(project_service.get_project_path("prefabs"), project_service.project_root)
        return {
            "project": project_service.get_project_summary(),
            "scene": {
                "current_scene_path": window.scene_path,
                "entity_count": window.entity_count,
                "entities": self._engine_api.list_entities(),
                "selected_entity": window.selected_entity,
            },
            "assets": self._engine_api.list_project_assets(),
            "levels": levels,
            "prefabs": prefabs,
            "skills": [skill.to_dict() for skill in skills],
            "capabilities": list(window.capabilities),
            "capability_index": capability_index([self._dict_to_descriptor(item) for item in window.capabilities]),
            "memory": dict(window.memory),
            "summary": {
                "asset_count": len(self._engine_api.list_project_assets()),
                "prefab_count": len(prefabs),
                "level_count": len(levels),
                "matched_skill_ids": [skill.id for skill in skills],
                "selected_entity": window.selected_entity,
                "recent_scripts": list(window.recent_scripts),
            },
        }

    def assemble_window(self, prompt: str, tool_results: Optional[List[Dict[str, Any]]] = None) -> AIContextWindow:
        project_service = self._engine_api.project_service
        skills = self._skill_registry.match(prompt)
        capabilities = [descriptor.to_dict() for descriptor in build_capability_registry(project_service, self._engine_api)]
        recent_assets = self._collect_recent_assets(project_service)
        recent_scripts = self._list_recent_scripts(project_service)
        memory = self._memory_store.load()

        game = getattr(self._engine_api, "game", None)
        active_world = getattr(game, "world", None)
        selected_entity = str(getattr(active_world, "selected_entity_name", "") or "")
        scene_path = str(getattr(game, "current_scene_path", "") or "")

        return AIContextWindow(
            prompt=prompt,
            scene_path=scene_path,
            selected_entity=selected_entity,
            entity_count=len(self._engine_api.list_entities()),
            recent_assets=recent_assets,
            recent_scripts=recent_scripts,
            capabilities=capabilities,
            memory=memory,
            tool_results=list(tool_results or []),
            summary={
                "matched_skill_ids": [skill.id for skill in skills],
                "project_name": project_service.project_name if project_service is not None and project_service.has_project else "",
                "asset_count": len(self._engine_api.list_project_assets()),
                "recent_assets": recent_assets[:5],
                "recent_scripts": recent_scripts[:5],
            },
        )

    def _collect_recent_assets(self, project_service) -> List[str]:
        recent: List[str] = []
        if project_service is None or not project_service.has_project:
            return recent
        seen: set[str] = set()
        for category in ("textures", "sprites", "audio", "general"):
            for path in project_service.get_recent_assets(category):
                normalized = str(path).strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    recent.append(normalized)
        if recent:
            return recent[:12]
        assets = self._engine_api.list_project_assets()
        return [str(item.get("path", "")) for item in assets[:12] if str(item.get("path", "")).strip()]

    def _list_recent_scripts(self, project_service) -> List[str]:
        if project_service is None or not project_service.has_project:
            return []
        scripts_root = project_service.get_project_path("scripts")
        if not scripts_root.exists():
            return []
        files = [path for path in scripts_root.rglob("*.py") if path.is_file()]
        files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return [project_service.to_relative_path(path) for path in files[:12]]

    def _list_relative_paths(self, root: Path, project_root: Path) -> List[str]:
        if not root.exists():
            return []
        result: List[str] = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                result.append(path.relative_to(project_root).as_posix())
        return result

    def _dict_to_descriptor(self, payload: Dict[str, Any]):
        from engine.ai.types import CapabilityDescriptor

        return CapabilityDescriptor(
            id=str(payload.get("id", "") or ""),
            name=str(payload.get("name", "") or ""),
            category=str(payload.get("category", "") or ""),
            available=bool(payload.get("available", False)),
            description=str(payload.get("description", "") or ""),
            evidence=[str(item) for item in payload.get("evidence", [])],
            tags=[str(item) for item in payload.get("tags", [])],
        )
