from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from engine.api._context import EngineAPIComponent
from engine.api.errors import InvalidOperationError, LevelLoadError
from engine.api.types import ActionResult


class SceneWorkspaceAPI(EngineAPIComponent):
    """Scene loading, workspace, and scene-flow endpoints exposed by EngineAPI."""

    def load_level(self, path: str) -> None:
        """Load a scene by file path into the runtime, from JSON or engine cache.

        If the scene is already cached in the runtime, it is loaded directly.
        Otherwise the JSON file is parsed, deserialized into a World, and
        attached to the engine.

        Args:
            path: Absolute or relative path to a .scene file or scene identifier.

        Raises:
            LevelLoadError: If the scene cannot be loaded from the given path.
        """
        try:
            runtime = self.runtime
            workspace = self.scene_workspace
            if workspace is None or runtime is None:
                raise RuntimeError("Engine not initialized")
            resolved_path = self.resolve_api_path(path, purpose="load level").as_posix()
            load_target = resolved_path if self._context.sandbox_paths else path
            if not runtime.load_scene_by_path(load_target):
                with open(resolved_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                world = workspace.load_scene(data, source_path=resolved_path)
                runtime.set_world(world)
                runtime.current_scene_path = resolved_path
                if self.project_service is not None:
                    self.project_service.set_last_scene(resolved_path)
        except Exception as exc:
            raise LevelLoadError(f"Fallo al cargar {path}: {exc}")

    def get_feature_metadata(self) -> Dict[str, Any]:
        """Retrieve the active scene's feature metadata dictionary.

        Returns:
            Dictionary of scene-wide settings (render_2d, physics_2d, signals,
            etc.), or empty dict if no scene is active.
        """
        authoring = self.scene_authoring
        if authoring is None:
            return {}
        return authoring.get_feature_metadata()

    def get_scene_connections(self) -> Dict[str, str]:
        """Get the scene flow connections (next, menu, previous) for the active scene.

        Returns:
            Dictionary mapping flow keys (e.g. "next_scene", "menu_scene") to
            target scene paths.
        """
        workspace = self.scene_workspace
        if workspace is None:
            return {}
        return workspace.get_scene_flow()

    def list_open_scenes(self) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """List all scenes currently open in the workspace.

        Returns:
            List of scene summary dictionaries.
        """
        workspace = self.scene_workspace
        if workspace is None:
            return []
        return workspace.list_open_scenes()

    def get_active_scene(self) -> Dict[str, Any]:
        """Get summary information about the currently active scene.

        Returns:
            Dictionary with active scene metadata, or empty dict if none.
        """
        workspace = self.scene_workspace
        if workspace is None:
            return {}
        return workspace.get_active_scene_summary()

    def has_active_scene(self) -> bool:
        """Check if there is an active scene loaded.

        Returns:
            True if a scene is currently active, False otherwise.
        """
        workspace = self.scene_workspace
        if workspace is None:
            return False
        return bool(workspace.get_active_scene_summary().get("path"))

    def get_active_scene_info(self) -> Dict[str, Union[str, int, float, bool, list, dict, None]]:
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
        workspace = self.scene_workspace
        if workspace is None:
            return {
                "has_scene": False,
                "path": "",
                "name": "",
                "key": "",
                "dirty": False,
                "entity_count": 0,
            }
        summary = workspace.get_active_scene_summary()
        runtime = self.runtime
        world = runtime.world if runtime is not None else None
        return {
            "has_scene": summary.get("path", "") != "",
            "path": summary.get("path", ""),
            "name": summary.get("name", ""),
            "key": summary.get("key", ""),
            "dirty": summary.get("dirty", False),
            "entity_count": world.entity_count() if world is not None else 0,
        }

    def load_scene_for_runtime_inspection(self, scene_ref: str = "") -> ActionResult:
        """Load a project scene into the current headless projection without persistence.

        Searches for a loadable scene from explicit reference, editor state, or
        project settings. The loaded scene is attached to the runtime for
        read-only inspection.

        Args:
            scene_ref: Explicit scene path or reference. If empty, searches in
                editor state (active_scene, last_scene), project settings
                (startup_scene), and levels directory.

        Returns:
            ActionResult with the loaded scene path, source field, name, and
            entity count.
        """
        runtime = self.runtime
        scene_manager = self.scene_manager
        project_service = self.project_service
        if runtime is None or scene_manager is None or project_service is None:
            return self.fail("Engine not initialized")
        if not project_service.has_project:
            return self.fail("Project manifest not loaded")

        candidates = (
            [(scene_ref, "explicit_scene")]
            if str(scene_ref or "").strip()
            else self._runtime_inspection_scene_candidates()
        )
        for candidate_ref, source_field in candidates:
            resolved_path = project_service.resolve_path(candidate_ref)
            if not resolved_path.exists() or not resolved_path.is_file():
                continue
            world = scene_manager.load_scene_from_file(resolved_path.as_posix(), activate=True)
            if world is None:
                continue
            runtime.set_world(world)
            runtime.current_scene_path = resolved_path.as_posix()
            scene = scene_manager.current_scene
            relative_path = project_service.to_relative_path(resolved_path)
            return self.ok(
                "Scene loaded for read-only runtime inspection",
                {
                    "path": relative_path,
                    "source_field": source_field,
                    "name": scene.name if scene is not None else Path(relative_path).stem,
                    "entity_count": world.entity_count(),
                },
            )
        return self.fail("No loadable scene found for runtime inspection")

    def _runtime_inspection_scene_candidates(self) -> list[tuple[str, str]]:
        project_service = self.project_service
        if project_service is None:
            return []

        candidates: list[tuple[str, str]] = []
        seen: set[str] = set()

        def add(scene_ref: Any, source_field: str) -> None:
            value = str(scene_ref or "").strip()
            if not value:
                return
            key = value.replace("\\", "/")
            if key in seen:
                return
            seen.add(key)
            candidates.append((value, source_field))

        editor_state = project_service.load_editor_state()
        add(editor_state.get("active_scene"), "editor_state.active_scene")
        add(editor_state.get("last_scene"), "editor_state.last_scene")
        add(project_service.load_project_settings().get("startup_scene"), "settings.startup_scene")

        for scene in project_service.list_project_scenes():
            add(scene.get("path"), "levels.first_scene")
            break

        return candidates

    def activate_scene(self, key_or_path: str) -> ActionResult:
        """Activate a scene tab in the multi-scene workspace.

        Args:
            key_or_path: Scene identifier key or file path.

        Returns:
            ActionResult with the activated scene's summary, or failure if
            activation failed.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.activate_scene_workspace_tab(self.resolve_scene_reference(key_or_path))
        return self.ok("Scene activated", self.get_active_scene()) if success else self.fail("Scene activation failed")

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> ActionResult:
        """Close a scene tab in the workspace.

        Args:
            key_or_path: Scene identifier key or file path.
            discard_changes: If True, close even with unsaved changes. If False,
                refuses to close a dirty scene.

        Returns:
            ActionResult confirming closure or reporting unsaved changes.
        """
        runtime = self.runtime
        workspace = self.scene_workspace
        if runtime is None or workspace is None:
            return self.fail("Engine not initialized")
        resolved_ref = self.resolve_scene_reference(key_or_path)
        if not discard_changes:
            entry = workspace.resolve_entry(resolved_ref)
            if entry is not None and entry.dirty:
                return self.fail("Scene has unsaved changes")
        success = runtime.close_scene_workspace_tab(resolved_ref, discard_changes=discard_changes)
        return self.ok("Scene closed", {"open_scenes": self.list_open_scenes()}) if success else self.fail("Scene close failed")

    def save_scene(self, key_or_path: Optional[str] = None, path: Optional[str] = None) -> ActionResult:
        """Persist a scene to a file.

        Args:
            key_or_path: Scene identifier key or file path. Defaults to active scene.
            path: Override save destination path. Defaults to the scene's existing
                source path.

        Returns:
            ActionResult confirming the save with the target path and scene summary.
        """
        workspace = self.scene_workspace
        if workspace is None:
            return self.fail("SceneManager not ready")
        target = self.resolve_scene_reference(key_or_path or workspace.active_scene_key)
        entry = workspace.resolve_entry(target)
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
        success = workspace.save_scene_to_file(target_path, key=entry.key)
        if not success:
            return self.fail("Scene save failed")
        runtime = self.runtime
        if runtime is not None:
            runtime.sync_scene_workspace(apply_view_state=True)
        return self.ok("Scene saved", {"path": target_path, "scene": self.get_active_scene()})

    def copy_entity_to_scene(self, entity_name: str, target_scene: str) -> ActionResult:
        """Copy an entity subtree from the active scene to another open scene.

        Args:
            entity_name: Name of the entity to copy (including children).
            target_scene: Target scene key or path.

        Returns:
            ActionResult confirming the copy-paste operation.
        """
        self.ensure_edit_mode()
        workspace = self.scene_workspace
        if workspace is None:
            return self.fail("SceneManager not ready")
        if not workspace.copy_entity_subtree(entity_name):
            return self.fail("Entity copy failed")
        if not workspace.paste_copied_entities(self.resolve_scene_reference(target_scene)):
            return self.fail("Entity paste failed")
        runtime = self.runtime
        if runtime is not None:
            runtime.sync_scene_workspace(apply_view_state=False)
        return self.ok("Entity copied to scene", {"entity": entity_name, "target_scene": target_scene})

    def set_scene_link(
        self,
        entity_name: str,
        target_path: str,
        flow_key: str = "",
        preview_label: str = "",
    ) -> ActionResult:
        """Attach a SceneLink component to an entity for scene flow navigation.

        Args:
            entity_name: Name of the entity to attach the link to.
            target_path: Target scene path or relative path.
            flow_key: Scene flow key (e.g. "next_scene", "menu_scene").
            preview_label: Display label shown in editor for the link.

        Returns:
            ActionResult confirming the SceneLink was created or updated.
        """
        self.ensure_edit_mode()
        authoring = self.scene_authoring
        if authoring is None or self.project_service is None:
            return self.fail("SceneManager not ready")
        normalized_target = self.project_service.to_relative_path(target_path) if target_path else ""
        payload = {
            "enabled": True,
            "target_path": normalized_target,
            "flow_key": str(flow_key or "").strip(),
            "preview_label": str(preview_label or "").strip(),
        }
        entity = authoring.find_entity_data(entity_name)
        if entity is None:
            return self.fail("Entity not found")
        has_link = "SceneLink" in entity.get("components", {})
        success = (
            authoring.replace_component_data(entity_name, "SceneLink", payload)
            if has_link
            else authoring.add_component_to_entity(entity_name, "SceneLink", payload)
        )
        return self.ok("SceneLink updated", {"entity": entity_name, "target_path": normalized_target}) if success else self.fail("SceneLink update failed")

    def set_scene_connection(self, key: str, path: str) -> ActionResult:
        """Configure a named scene flow connection for the active scene.

        Args:
            key: Flow key (e.g. "next_scene", "menu_scene", "previous_scene").
            path: Target scene path (relative to project root).

        Returns:
            ActionResult confirming the connection was set.
        """
        self.ensure_edit_mode()
        workspace = self.scene_workspace
        if workspace is None:
            return self.fail("SceneManager not ready")
        normalized = ""
        if path and self.project_service is not None:
            normalized = self.project_service.to_relative_path(path)
        success = workspace.set_scene_flow_target(key, normalized)
        return self.ok("Scene connection updated", {"key": key, "path": normalized}) if success else self.fail("Scene connection update failed")

    def set_next_scene(self, path: str) -> ActionResult:
        """Set the next scene in the scene flow (shortcut for set_scene_connection).

        Args:
            path: Target scene path.

        Returns:
            ActionResult confirming the connection.
        """
        return self.set_scene_connection("next_scene", path)

    def set_menu_scene(self, path: str) -> ActionResult:
        """Set the menu scene in the scene flow (shortcut for set_scene_connection).

        Args:
            path: Target scene path.

        Returns:
            ActionResult confirming the connection.
        """
        return self.set_scene_connection("menu_scene", path)

    def set_previous_scene(self, path: str) -> ActionResult:
        """Set the previous scene in the scene flow (shortcut for set_scene_connection).

        Args:
            path: Target scene path.

        Returns:
            ActionResult confirming the connection.
        """
        return self.set_scene_connection("previous_scene", path)

    def load_scene(self, path: str) -> ActionResult:
        """Load a scene from the engine's scene cache by path.

        Unlike load_level, this uses the runtime's internal scene cache.

        Args:
            path: Scene file path or identifier.

        Returns:
            ActionResult with the loaded scene path.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.load_scene_by_path(path)
        return self.ok("Scene loaded", {"path": runtime.current_scene_path}) if success else self.fail("Scene load failed")

    def create_scene(self, name: str) -> ActionResult:
        """Create a new empty scene with the given name.

        Args:
            name: Name for the new scene.

        Returns:
            ActionResult with the new scene's file path.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.create_scene(name)
        if not success:
            return self.fail("Scene creation failed")
        path = runtime.current_scene_path
        if path and self.project_service:
            self.project_service.set_last_scene(path)
        return self.ok("Scene created", {"path": path})

    def open_scene(self, path: str) -> ActionResult:
        """Alias for load_scene. Opens a scene by path.

        Args:
            path: Scene file path or identifier.

        Returns:
            ActionResult with the loaded scene path.
        """
        return self.load_scene(path)

    def load_next_scene(self) -> ActionResult:
        """Load the scene configured as 'next_scene' in the scene flow.

        Returns:
            ActionResult with the loaded scene path, or failure if next_scene
            is not configured.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.load_scene_flow_target("next_scene")
        return self.ok("Next scene loaded", {"path": runtime.current_scene_path}) if success else self.fail("Next scene is not configured")

    def load_menu_scene(self) -> ActionResult:
        """Load the scene configured as 'menu_scene' in the scene flow.

        Returns:
            ActionResult with the loaded scene path, or failure if menu_scene
            is not configured.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.load_scene_flow_target("menu_scene")
        return self.ok("Menu scene loaded", {"path": runtime.current_scene_path}) if success else self.fail("Menu scene is not configured")

    def load_scene_flow_target(self, key: str) -> ActionResult:
        """Load the scene associated with an arbitrary flow key.

        Args:
            key: Flow key name (e.g. "next_scene", "menu_scene", or custom).

        Returns:
            ActionResult with the loaded scene path and key, or failure if the
            key is not configured.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return self.fail("Scene flow key is required")
        success = runtime.load_scene_flow_target(normalized_key)
        if not success:
            return self.fail(f"Scene flow target '{normalized_key}' is not configured")
        return self.ok(
            "Scene flow target loaded",
            {
                "key": normalized_key,
                "path": runtime.current_scene_path,
            },
        )

    def instantiate_prefab(
        self,
        path: str,
        name: Optional[str] = None,
        parent: Optional[str] = None,
        overrides: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
    ) -> ActionResult:
        """Instantiate a prefab asset into the active scene.

        Args:
            path: Path to the .prefab file.
            name: Custom entity name for the instance. Defaults to the prefab's
                root name.
            parent: Optional parent entity name.
            overrides: Optional property overrides for the instance.

        Returns:
            ActionResult confirming the prefab was instantiated.
        """
        self.ensure_edit_mode()
        authoring = self.scene_authoring
        workspace = self.scene_workspace
        if authoring is None or workspace is None or self.project_service is None:
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
        active_scene = workspace.get_active_scene_summary()
        scene_source_path = str(active_scene.get("path", "")).strip() or None
        prefab_locator = self.project_service.to_scene_locator(
            resolved_path,
            scene_source_path=scene_source_path,
        )
        success = authoring.instantiate_prefab(
            entity_name,
            prefab_path=prefab_locator,
            parent=parent,
            overrides=overrides,
            root_name=prefab_data.get("root_name", entity_name),
        )
        return self.ok("Prefab instantiated", {"entity": entity_name}) if success else self.fail("Prefab instantiation failed")

    def create_prefab(
        self,
        entity_name: str,
        path: str,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
    ) -> ActionResult:
        """Create a prefab asset from an existing entity in the scene.

        Args:
            entity_name: Name of the entity to convert into a prefab.
            path: Output path for the .prefab file.
            replace_original: If True, replace the original entity with a prefab
                instance pointing to the newly created prefab.
            instance_name: Custom name for the replacement instance (only used
                when replace_original=True).

        Returns:
            ActionResult confirming the prefab was created.
        """
        self.ensure_edit_mode()
        authoring = self.scene_authoring
        workspace = self.scene_workspace
        if authoring is None or workspace is None or self.project_service is None:
            return self.fail("SceneManager not ready")

        try:
            resolved_path = self.resolve_api_path(path, purpose="create prefab")
        except InvalidOperationError as exc:
            return self.fail(str(exc))

        active_scene = workspace.get_active_scene_summary()
        scene_source_path = str(active_scene.get("path", "")).strip() or None
        prefab_locator = self.project_service.to_scene_locator(
            resolved_path,
            scene_source_path=scene_source_path,
        )
        success = authoring.create_prefab(
            entity_name,
            resolved_path.as_posix(),
            replace_original=replace_original,
            instance_name=instance_name,
            prefab_locator=prefab_locator,
        )
        if not success:
            return self.fail("Prefab creation failed")
        data = {
            "entity": entity_name,
            "prefab_path": self.project_service.to_relative_path(resolved_path),
            "replace_original": bool(replace_original),
        }
        if replace_original:
            data["instance"] = instance_name or entity_name
        return self.ok("Prefab created", data)

    def unpack_prefab(self, entity_name: str) -> ActionResult:
        """Unpack a prefab instance into a regular entity hierarchy.

        Args:
            entity_name: Name of the prefab instance entity.

        Returns:
            ActionResult confirming the prefab was unpacked.
        """
        self.ensure_edit_mode()
        authoring = self.scene_authoring
        if authoring is None:
            return self.fail("SceneManager not ready")
        success = authoring.unpack_prefab(entity_name)
        return self.ok("Prefab unpacked", {"entity": entity_name}) if success else self.fail("Prefab unpack failed")

    def apply_prefab_overrides(self, entity_name: str) -> ActionResult:
        """Re-apply prefab overrides from the source prefab to a modified instance.

        Args:
            entity_name: Name of the prefab instance entity.

        Returns:
            ActionResult confirming the overrides were applied.
        """
        self.ensure_edit_mode()
        authoring = self.scene_authoring
        if authoring is None:
            return self.fail("SceneManager not ready")
        success = authoring.apply_prefab_overrides(entity_name)
        return self.ok("Prefab overrides applied", {"entity": entity_name}) if success else self.fail("Prefab apply failed")
