from __future__ import annotations

import json
from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.errors import InvalidOperationError, LevelLoadError
from engine.api.types import ActionResult


class SceneWorkspaceAPI(EngineAPIComponent):
    """Scene loading, workspace, and scene-flow endpoints exposed by EngineAPI."""

    def load_level(self, path: str) -> None:
        try:
            if self.scene_manager is None or self.game is None:
                raise RuntimeError("Engine not initialized")
            resolved_path = self.resolve_api_path(path, purpose="load level").as_posix()
            load_target = resolved_path if self._context.sandbox_paths else path
            if not self.game.load_scene_by_path(load_target):
                with open(resolved_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                world = self.scene_manager.load_scene(data, source_path=resolved_path)
                self.game.set_world(world)
                self.game.current_scene_path = resolved_path
                if self.project_service is not None:
                    self.project_service.set_last_scene(resolved_path)
        except Exception as exc:
            raise LevelLoadError(f"Fallo al cargar {path}: {exc}")

    def get_feature_metadata(self) -> Dict[str, Any]:
        if self.scene_manager is None:
            return {}
        return self.scene_manager.get_feature_metadata()

    def get_scene_connections(self) -> Dict[str, str]:
        if self.scene_manager is None:
            return {}
        return self.scene_manager.get_scene_flow()

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        if self.scene_manager is None:
            return []
        return self.scene_manager.list_open_scenes()

    def get_active_scene(self) -> Dict[str, Any]:
        if self.scene_manager is None:
            return {}
        return self.scene_manager.get_active_scene_summary()

    def has_active_scene(self) -> bool:
        """Check if there is an active scene loaded.

        Returns:
            True if a scene is currently active, False otherwise.
        """
        if self.scene_manager is None:
            return False
        return self.scene_manager.get_active_scene_summary().get("path") != ""

    def get_active_scene_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the active scene.

        Returns:
            Dictionary with scene info including:
            - has_scene: bool
            - path: str (scene source path or empty string)
            - name: str (scene name or empty string)
            - key: str (scene key or empty string)
            - dirty: bool (whether scene has unsaved changes)
            - entity_count: int (number of entities in scene)
        """
        if self.scene_manager is None:
            return {
                "has_scene": False,
                "path": "",
                "name": "",
                "key": "",
                "dirty": False,
                "entity_count": 0,
            }
        summary = self.scene_manager.get_active_scene_summary()
        return {
            "has_scene": summary.get("path", "") != "",
            "path": summary.get("path", ""),
            "name": summary.get("name", ""),
            "key": summary.get("key", ""),
            "dirty": summary.get("dirty", False),
            "entity_count": summary.get("entity_count", 0),
        }

    def activate_scene(self, key_or_path: str) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.activate_scene_workspace_tab(self.resolve_scene_reference(key_or_path))
        return self.ok("Scene activated", self.get_active_scene()) if success else self.fail("Scene activation failed")

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> ActionResult:
        if self.game is None or self.scene_manager is None:
            return self.fail("Engine not initialized")
        resolved_ref = self.resolve_scene_reference(key_or_path)
        if not discard_changes:
            entry = self.scene_manager.resolve_entry(resolved_ref)
            if entry is not None and entry.dirty:
                return self.fail("Scene has unsaved changes")
        success = self.game.close_scene_workspace_tab(resolved_ref, discard_changes=discard_changes)
        return self.ok("Scene closed", {"open_scenes": self.list_open_scenes()}) if success else self.fail("Scene close failed")

    def save_scene(self, key_or_path: Optional[str] = None, path: Optional[str] = None) -> ActionResult:
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        target = self.resolve_scene_reference(key_or_path or self.scene_manager.active_scene_key)
        entry = self.scene_manager.resolve_entry(target)
        if entry is None:
            return self.fail("Scene not found")
        target_path = path or entry.source_path
        if not target_path:
            return self.fail("Scene has no save path")
        try:
            if path:
                target_path = self.resolve_api_path(path, purpose="save scene").as_posix()
        except InvalidOperationError as exc:
            return self.fail(str(exc))
        success = self.scene_manager.save_scene_to_file(target_path, key=entry.key)
        if not success:
            return self.fail("Scene save failed")
        if self.game is not None:
            self.game.sync_scene_workspace(apply_view_state=True)
        return self.ok("Scene saved", {"path": target_path, "scene": self.get_active_scene()})

    def copy_entity_to_scene(self, entity_name: str, target_scene: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        if not self.scene_manager.copy_entity_subtree(entity_name):
            return self.fail("Entity copy failed")
        if not self.scene_manager.paste_copied_entities(self.resolve_scene_reference(target_scene)):
            return self.fail("Entity paste failed")
        if self.game is not None:
            self.game.sync_scene_workspace(apply_view_state=False)
        return self.ok("Entity copied to scene", {"entity": entity_name, "target_scene": target_scene})

    def set_scene_link(
        self,
        entity_name: str,
        target_path: str,
        flow_key: str = "",
        preview_label: str = "",
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None or self.project_service is None:
            return self.fail("SceneManager not ready")
        normalized_target = self.project_service.to_relative_path(target_path) if target_path else ""
        payload = {
            "enabled": True,
            "target_path": normalized_target,
            "flow_key": str(flow_key or "").strip(),
            "preview_label": str(preview_label or "").strip(),
        }
        entity = self.scene_manager.find_entity_data(entity_name)
        if entity is None:
            return self.fail("Entity not found")
        has_link = "SceneLink" in entity.get("components", {})
        success = (
            self.scene_manager.replace_component_data(entity_name, "SceneLink", payload)
            if has_link
            else self.scene_manager.add_component_to_entity(entity_name, "SceneLink", payload)
        )
        return self.ok("SceneLink updated", {"entity": entity_name, "target_path": normalized_target}) if success else self.fail("SceneLink update failed")

    def set_scene_connection(self, key: str, path: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        normalized = ""
        if path and self.project_service is not None:
            normalized = self.project_service.to_relative_path(path)
        success = self.scene_manager.set_scene_flow_target(key, normalized)
        return self.ok("Scene connection updated", {"key": key, "path": normalized}) if success else self.fail("Scene connection update failed")

    def set_next_scene(self, path: str) -> ActionResult:
        return self.set_scene_connection("next_scene", path)

    def set_menu_scene(self, path: str) -> ActionResult:
        return self.set_scene_connection("menu_scene", path)

    def set_previous_scene(self, path: str) -> ActionResult:
        return self.set_scene_connection("previous_scene", path)

    def load_scene(self, path: str) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.load_scene_by_path(path)
        return self.ok("Scene loaded", {"path": self.game.current_scene_path}) if success else self.fail("Scene load failed")

    def create_scene(self, name: str) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.create_scene(name)
        return self.ok("Scene created", {"path": self.game.current_scene_path}) if success else self.fail("Scene creation failed")

    def open_scene(self, path: str) -> ActionResult:
        return self.load_scene(path)

    def load_next_scene(self) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.load_scene_flow_target("next_scene")
        return self.ok("Next scene loaded", {"path": self.game.current_scene_path}) if success else self.fail("Next scene is not configured")

    def load_menu_scene(self) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.load_scene_flow_target("menu_scene")
        return self.ok("Menu scene loaded", {"path": self.game.current_scene_path}) if success else self.fail("Menu scene is not configured")

    def load_scene_flow_target(self, key: str) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self.fail("Scene flow key is required")
        success = self.game.load_scene_flow_target(normalized_key)
        if not success:
            return self.fail(f"Scene flow target '{normalized_key}' is not configured")
        return self.ok(
            "Scene flow target loaded",
            {
                "key": normalized_key,
                "path": self.game.current_scene_path,
            },
        )

    def instantiate_prefab(
        self,
        path: str,
        name: Optional[str] = None,
        parent: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None or self.project_service is None:
            return self.fail("SceneManager not ready")
        from engine.assets.prefab import PrefabManager

        try:
            resolved_path = self.resolve_api_path(path, purpose="instantiate prefab")
        except InvalidOperationError as exc:
            return self.fail(str(exc))
        prefab_data = PrefabManager.load_prefab_data(resolved_path.as_posix())
        if prefab_data is None:
            return self.fail("Prefab not found")
        entity_name = name or prefab_data.get("root_name", "Prefab")
        active_scene = self.scene_manager.get_active_scene_summary()
        scene_source_path = str(active_scene.get("path", "")).strip() or None
        prefab_locator = self.project_service.to_scene_locator(
            resolved_path,
            scene_source_path=scene_source_path,
        )
        success = self.scene_manager.instantiate_prefab(
            entity_name,
            prefab_path=prefab_locator,
            parent=parent,
            overrides=overrides,
            root_name=prefab_data.get("root_name", entity_name),
        )
        return self.ok("Prefab instantiated", {"entity": entity_name}) if success else self.fail("Prefab instantiation failed")

    def unpack_prefab(self, entity_name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.unpack_prefab(entity_name)
        return self.ok("Prefab unpacked", {"entity": entity_name}) if success else self.fail("Prefab unpack failed")

    def apply_prefab_overrides(self, entity_name: str) -> ActionResult:
        self.ensure_edit_mode()
        if self.scene_manager is None:
            return self.fail("SceneManager not ready")
        success = self.scene_manager.apply_prefab_overrides(entity_name)
        return self.ok("Prefab overrides applied", {"entity": entity_name}) if success else self.fail("Prefab apply failed")
