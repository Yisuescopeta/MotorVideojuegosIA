from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from engine.ai.capabilities import build_capability_registry, capability_index


class ContextAssembler:
    def __init__(self, engine_api, skill_registry, memory_store) -> None:
        self._engine_api = engine_api
        self._skill_registry = skill_registry
        self._memory_store = memory_store

    def assemble(self, prompt: str) -> Dict[str, Any]:
        project_service = self._engine_api.project_service
        assets = self._engine_api.list_project_assets()
        skills = self._skill_registry.match(prompt)
        capabilities = build_capability_registry(project_service, self._engine_api)
        levels = self._list_relative_paths(project_service.get_project_path("levels"), project_service.project_root)
        prefabs = self._list_relative_paths(project_service.get_project_path("prefabs"), project_service.project_root)
        scene_entities = self._engine_api.list_entities()
        memory = self._memory_store.load()
        return {
            "project": project_service.get_project_summary(),
            "scene": {
                "current_scene_path": self._engine_api.game.current_scene_path if self._engine_api.game is not None else "",
                "entity_count": len(scene_entities),
                "entities": scene_entities,
            },
            "assets": assets,
            "levels": levels,
            "prefabs": prefabs,
            "skills": [skill.to_dict() for skill in skills],
            "capabilities": [capability.to_dict() for capability in capabilities],
            "capability_index": capability_index(capabilities),
            "memory": memory,
            "summary": {
                "asset_count": len(assets),
                "prefab_count": len(prefabs),
                "level_count": len(levels),
                "matched_skill_ids": [skill.id for skill in skills],
            },
        }

    def _list_relative_paths(self, root: Path, project_root: Path) -> List[str]:
        if not root.exists():
            return []
        result: List[str] = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                result.append(path.relative_to(project_root).as_posix())
        return result
