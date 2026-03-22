from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


class AISnapshotService:
    DIR_NAME = "ai_snapshots"

    def __init__(self, project_service) -> None:
        self._project_service = project_service

    @property
    def snapshots_dir(self) -> Path:
        if not self._project_service.has_project:
            return self._project_service.global_state_dir / self.DIR_NAME
        return self._project_service.get_project_path("meta") / self.DIR_NAME

    def capture(self, engine_api, file_paths: List[str]) -> str:
        snapshot_id = f"snapshot_{uuid4().hex[:12]}"
        payload = {
            "id": snapshot_id,
            "scene": self._capture_scene(engine_api),
            "files": self._capture_files(file_paths),
        }
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshots_dir / f"{snapshot_id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
        return snapshot_id

    def restore(self, engine_api, snapshot_id: str) -> Dict[str, Any]:
        path = self.snapshots_dir / f"{snapshot_id}.json"
        if not path.exists():
            return {"success": False, "message": "Snapshot not found"}
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            return {"success": False, "message": f"Snapshot load failed: {exc}"}

        scene_result = self._restore_scene(engine_api, payload.get("scene", {}) or {})
        file_result = self._restore_files(payload.get("files", []) or [])

        game = getattr(engine_api, "game", None)
        hot_reload = getattr(game, "hot_reload_manager", None)
        if hot_reload is not None:
            hot_reload.scan_directory()

        errors = [item for item in (scene_result.get("error"), file_result.get("error")) if item]
        return {
            "success": len(errors) == 0,
            "message": "Snapshot restored" if not errors else "Snapshot restored with errors",
            "errors": errors,
        }

    def _capture_scene(self, engine_api) -> Dict[str, Any]:
        scene_manager = getattr(engine_api, "scene_manager", None)
        game = getattr(engine_api, "game", None)
        if scene_manager is None or scene_manager.current_scene is None:
            return {}
        current_scene = scene_manager.current_scene
        selected_entity = ""
        active_world = getattr(game, "world", None)
        if active_world is not None:
            selected_entity = str(getattr(active_world, "selected_entity_name", "") or "")
        return {
            "data": current_scene.to_dict(),
            "scene_path": str(getattr(game, "current_scene_path", "") or ""),
            "selected_entity": selected_entity,
            "dirty": bool(getattr(scene_manager, "is_dirty", False)),
        }

    def _capture_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        unique_paths: List[str] = []
        seen: set[str] = set()
        for entry in file_paths:
            normalized = str(entry or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_paths.append(normalized)

        snapshots: List[Dict[str, Any]] = []
        for relative_path in unique_paths:
            resolved = self._project_service.resolve_path(relative_path)
            existed = resolved.exists()
            content = ""
            if existed and resolved.is_file():
                try:
                    content = resolved.read_text(encoding="utf-8")
                except Exception:
                    content = resolved.read_text(encoding="utf-8", errors="ignore")
            snapshots.append(
                {
                    "path": self._project_service.to_relative_path(resolved),
                    "existed": existed,
                    "content": content,
                }
            )
        return snapshots

    def _restore_scene(self, engine_api, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload:
            return {"success": True}
        scene_manager = getattr(engine_api, "scene_manager", None)
        game = getattr(engine_api, "game", None)
        if scene_manager is None:
            return {"success": False, "error": "SceneManager unavailable"}
        try:
            restored = scene_manager.restore_scene_data(payload.get("data", {}) or {})
            if not restored:
                return {"success": False, "error": "Scene restore failed"}
            selected_entity = str(payload.get("selected_entity", "") or "")
            if selected_entity:
                scene_manager.set_selected_entity(selected_entity)
            if game is not None:
                game.current_scene_path = str(payload.get("scene_path", "") or game.current_scene_path)
            if not bool(payload.get("dirty", False)):
                scene_manager.clear_dirty()
        except Exception as exc:
            return {"success": False, "error": f"Scene restore failed: {exc}"}
        return {"success": True}

    def _restore_files(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            for entry in files:
                relative_path = str(entry.get("path", "") or "").strip()
                if not relative_path:
                    continue
                resolved = self._project_service.resolve_path(relative_path)
                existed = bool(entry.get("existed", False))
                if existed:
                    resolved.parent.mkdir(parents=True, exist_ok=True)
                    resolved.write_text(str(entry.get("content", "") or ""), encoding="utf-8")
                elif resolved.exists():
                    resolved.unlink()
        except Exception as exc:
            return {"success": False, "error": f"File restore failed: {exc}"}
        return {"success": True}
