"""Safe facade used by Qt panels to access engine authoring APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from editor_qt.viewmodels import (
    normalize_agent_provider,
    normalize_agent_session,
    normalize_animator_info,
    normalize_asset_summary,
    normalize_entity_snapshot,
    normalize_flow_connections,
    normalize_project_manifest,
    normalize_scene_summary,
)

ActionResult = dict[str, Any]


class EditorEngineFacade:
    """Single Qt-facing entrypoint into the engine.

    Widgets must depend on this facade instead of reaching into World,
    SceneManager, or runtime systems directly.
    """

    def __init__(
        self,
        engine_api: Any | None = None,
        project_root: str | Path | None = None,
        *,
        auto_ensure_project: bool = True,
        read_only: bool = False,
    ) -> None:
        self._api = engine_api
        self._owns_api = engine_api is None
        self._project_root = Path(project_root).expanduser().resolve() if project_root is not None else Path.cwd()
        self._auto_ensure_project = auto_ensure_project
        self._read_only = read_only
        self._selected_entity_name: str | None = None
        self.last_error: str | None = None

    @property
    def selected_entity_name(self) -> str | None:
        return self._selected_entity_name

    @property
    def project_root(self) -> Path:
        return self._project_root

    def list_entities(self) -> list[dict[str, Any]]:
        try:
            entities = self._engine_api().list_entities()
        except Exception as exc:
            self.last_error = str(exc)
            return []
        return [normalize_entity_snapshot(entity) for entity in entities if isinstance(entity, dict)]

    def get_entity(self, entity_name: str) -> dict[str, Any] | None:
        if not entity_name:
            return None
        try:
            entity = self._engine_api().get_entity(entity_name)
        except Exception as exc:
            self.last_error = str(exc)
            return None
        return normalize_entity_snapshot(entity) if isinstance(entity, dict) else None

    def get_project_manifest(self) -> dict[str, Any]:
        payload = self._call_read("get_project_manifest", {})
        return normalize_project_manifest(payload if isinstance(payload, dict) else {})

    def get_active_scene_info(self) -> dict[str, Any]:
        payload = self._call_read("get_active_scene_info", {})
        return normalize_scene_summary(payload if isinstance(payload, dict) else {})

    def list_project_scenes(self) -> list[dict[str, Any]]:
        payload = self._call_read("list_project_scenes", [])
        return [normalize_scene_summary(scene) for scene in payload if isinstance(scene, dict)]

    def list_project_assets(self) -> list[dict[str, Any]]:
        payload = self._call_read("list_project_assets", [])
        return [normalize_asset_summary(asset) for asset in payload if isinstance(asset, dict)]

    def list_project_scripts(self) -> list[str]:
        payload = self._call_read("list_project_scripts", [])
        return [str(item) for item in payload]

    def list_project_prefabs(self) -> list[str]:
        payload = self._call_read("list_project_prefabs", [])
        return [str(item) for item in payload]

    def list_recent_projects(self) -> list[dict[str, Any]]:
        payload = self._call_read("list_recent_projects", [])
        return [normalize_project_manifest(project) for project in payload if isinstance(project, dict)]

    def list_open_scenes(self) -> list[dict[str, Any]]:
        payload = self._call_read("list_open_scenes", [])
        return [normalize_scene_summary(scene) for scene in payload if isinstance(scene, dict)]

    def open_project(self, path: str) -> ActionResult:
        result = self._call_action("open_project", path, failure_message="Project open failed")
        if result.get("success"):
            self._selected_entity_name = None
            data = result.get("data")
            root = data.get("path") if isinstance(data, dict) else path
            if root:
                self._project_root = Path(str(root)).expanduser().resolve()
        return result

    def create_project(self, path: str, name: str = "") -> ActionResult:
        result = self._call_action("create_project", path, name, failure_message="Project creation failed")
        if result.get("success"):
            self._selected_entity_name = None
            data = result.get("data")
            root = data.get("path") if isinstance(data, dict) else path
            if root:
                self._project_root = Path(str(root)).expanduser().resolve()
        return result

    def migrate_legacy_project(self, path: str) -> ActionResult:
        """Create project.json in an existing folder that has scene data but no project manifest."""
        import json
        from pathlib import Path

        target = Path(path).expanduser().resolve()
        manifest_path = target / "project.json"

        if manifest_path.exists():
            return {"success": True, "message": "Project already exists", "data": {"path": str(target)}}

        # Check for legacy content
        levels_dir = target / "levels"
        has_levels = levels_dir.exists() and any(levels_dir.rglob("*.json"))
        if not has_levels:
            return self._failure("No scene files found. Not a valid legacy project folder.")

        try:
            # Try EngineAPI first
            return self._call_action("create_project", str(target), str(target.name),
                                     failure_message="Legacy project migration failed")
        except Exception:
            # Fallback: create project.json manually
            try:
                manifest = {
                    "name": target.name,
                    "version": "1.0.0",
                    "engine_version": "0.1.0",
                    "template": "empty",
                    "paths": {
                        "assets": "assets",
                        "levels": "levels",
                        "scripts": "scripts",
                        "prefabs": "prefabs",
                        "settings": "project"
                    }
                }
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

                # Create required directories
                for subdir in ("assets", "scripts", "prefabs", "project"):
                    (target / subdir).mkdir(exist_ok=True)

                # Create default settings
                settings_path = target / "project" / "settings.json"
                if not settings_path.exists():
                    settings_path.parent.mkdir(parents=True, exist_ok=True)
                    settings_path.write_text(json.dumps({"startup_scene": ""}, indent=2), encoding="utf-8")

                return {"success": True, "message": "Legacy project imported",
                        "data": {"path": str(target), "manifest": str(manifest_path)}}
            except Exception as exc:
                return self._failure(f"Legacy project migration failed: {exc}")

    def load_default_scene(self) -> ActionResult:
        return self._load_scene_for_runtime_inspection("")

    def load_scene(self, scene_ref: str) -> ActionResult:
        return self._load_scene_for_runtime_inspection(scene_ref)

    def create_scene(self, name: str) -> ActionResult:
        result = self._call_action("create_scene", name, failure_message="Scene creation failed")
        if result.get("success"):
            self._selected_entity_name = None
        return result

    def select_entity(self, entity_name: str) -> dict[str, Any] | None:
        self._selected_entity_name = entity_name or None
        return self.get_entity(entity_name) if entity_name else None

    def update_component_property(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> ActionResult:
        return self._call_action(
            "edit_component",
            entity_name,
            component_name,
            property_name,
            value,
            failure_message="Component property update failed",
        )

    def create_entity(self, name: str) -> ActionResult:
        return self._call_action("create_entity", name, failure_message="Entity creation failed")

    def create_canvas(self, name: str = "Canvas") -> ActionResult:
        return self._call_action("create_canvas", name, failure_message="Canvas creation failed")

    def create_ui_text(self, name: str = "Text", text: str = "Text", parent: str = "Canvas") -> ActionResult:
        return self._call_action("create_ui_text", name, text, parent, failure_message="Text creation failed")

    def create_ui_button(self, name: str = "Button", label: str = "Button", parent: str = "Canvas") -> ActionResult:
        return self._call_action("create_ui_button", name, label, parent, failure_message="Button creation failed")

    def delete_entity(self, entity_name: str) -> ActionResult:
        result = self._call_action("delete_entity", entity_name, failure_message="Entity deletion failed")
        if result.get("success") and self._selected_entity_name == entity_name:
            self._selected_entity_name = None
        return result

    def set_entity_parent(self, entity_name: str, parent_name: str | None) -> ActionResult:
        """Set or clear the parent entity of an entity."""
        return self._call_action(
            "set_entity_parent", entity_name, parent_name,
            failure_message="Entity parent update failed",
        )

    def create_child_entity(self, parent_name: str, name: str) -> ActionResult:
        """Create a new entity as a child of an existing parent."""
        return self._call_action(
            "create_child_entity", parent_name, name,
            failure_message="Child entity creation failed",
        )

    def add_component(self, entity_name: str, component_name: str, data: dict[str, Any] | None = None) -> ActionResult:
        """Attach a new component to an existing entity."""
        return self._call_action(
            "add_component", entity_name, component_name, data,
            failure_message="Component add failed",
        )

    def remove_component(self, entity_name: str, component_name: str) -> ActionResult:
        """Remove a component from an entity."""
        return self._call_action(
            "remove_component", entity_name, component_name,
            failure_message="Component remove failed",
        )

    def replace_component_data(self, entity_name: str, component_name: str, data: dict[str, Any]) -> ActionResult:
        """Fully replace the data payload of an existing component."""
        return self._call_action(
            "replace_component_data", entity_name, component_name, data,
            failure_message="Component replace failed",
        )

    def duplicate_entity(self, entity_name: str) -> ActionResult:
        """Duplicate an entity with all its components in the active scene."""
        original = self.get_entity(entity_name)
        if original is None:
            return self._failure(f"Entity '{entity_name}' not found for duplication")
        base_name = str(original.get("name", entity_name))
        new_name = base_name
        counter = 1
        existing = self.list_entities()
        existing_names = {str(e.get("name", "")) for e in existing}
        while new_name in existing_names:
            new_name = f"{base_name}_{counter}"
            counter += 1
        components = dict(original.get("components", {}))
        components.pop("prefab_instance", None)
        parent_name = original.get("parent")
        if parent_name:
            return self._call_action(
                "create_child_entity", str(parent_name), new_name, components,
                failure_message="Entity duplication failed",
            )
        return self._call_action(
            "create_entity", new_name, components,
            failure_message="Entity duplication failed",
        )

    def refresh_assets(self) -> ActionResult:
        return self._call_action("refresh_asset_catalog", failure_message="Asset refresh failed")

    def get_scene_connections(self) -> list[dict[str, str]]:
        payload = self._call_read("get_scene_connections", {})
        return normalize_flow_connections(payload if isinstance(payload, dict) else {})

    def set_scene_connection(self, key: str, path: str) -> ActionResult:
        return self._call_action("set_scene_connection", key, path, failure_message="Scene flow update failed")

    def get_animator_info(self, entity_name: str) -> dict[str, Any]:
        payload = self._call_read_args("get_animator_info", {}, entity_name)
        return normalize_animator_info(payload if isinstance(payload, dict) else {})

    def list_animator_states(self, entity_name: str) -> list[dict[str, Any]]:
        payload = self._call_read_args("list_animator_states", [], entity_name)
        return [dict(state) for state in payload if isinstance(state, dict)]

    def ensure_animator(self, entity_name: str, sprite_sheet: str = "") -> ActionResult:
        info = self.get_animator_info(entity_name)
        if info.get("exists"):
            if sprite_sheet:
                return self.set_animator_sprite_sheet(entity_name, sprite_sheet)
            return {"success": True, "message": "Animator already exists", "data": {"entity": entity_name, "created": False}}
        payload: dict[str, Any] = {"enabled": True, "speed": 1.0}
        if sprite_sheet:
            payload["sprite_sheet"] = sprite_sheet
        return self._call_action("add_component", entity_name, "Animator", payload, failure_message="Animator creation failed")

    def set_animator_sprite_sheet(self, entity_name: str, asset_path: str) -> ActionResult:
        return self._call_action(
            "set_animator_sprite_sheet",
            entity_name,
            asset_path,
            failure_message="Animator sprite sheet update failed",
        )

    def upsert_animator_state(
        self,
        entity_name: str,
        state_name: str,
        slice_names: list[str],
        fps: float,
        loop: bool,
        on_complete: str | None = None,
        set_default: bool = False,
    ) -> ActionResult:
        return self._call_action(
            "upsert_animator_state",
            entity_name,
            state_name,
            slice_names,
            fps,
            loop,
            on_complete,
            set_default,
            failure_message="Animator state update failed",
        )

    def remove_animator_state(self, entity_name: str, state_name: str) -> ActionResult:
        return self._call_action(
            "remove_animator_state",
            entity_name,
            state_name,
            failure_message="Animator state remove failed",
        )

    def set_animator_speed(self, entity_name: str, speed: float) -> ActionResult:
        return self._call_action("set_animator_speed", entity_name, speed, failure_message="Animator speed update failed")

    def set_animator_flip(self, entity_name: str, flip_x: bool, flip_y: bool) -> ActionResult:
        return self._call_action(
            "set_animator_flip",
            entity_name,
            flip_x,
            flip_y,
            failure_message="Animator flip update failed",
        )

    def list_agent_providers(self) -> list[dict[str, Any]]:
        payload = self._call_read("list_agent_providers", [])
        return [normalize_agent_provider(provider) for provider in payload if isinstance(provider, dict)]

    def list_agent_tools(self) -> list[dict[str, Any]]:
        payload = self._call_read("list_agent_tools", [])
        return [dict(tool) for tool in payload if isinstance(tool, dict)]

    def create_agent_session(self) -> ActionResult:
        result = self._call_action(
            "create_agent_session",
            "confirm_actions",
            "Qt Editor Agent",
            "fake",
            failure_message="Agent session creation failed",
        )
        if result.get("success") and isinstance(result.get("data"), dict):
            result["data"] = normalize_agent_session(result["data"])
        return result

    def send_agent_message(self, session_id: str, message: str) -> ActionResult:
        result = self._call_action(
            "send_agent_message",
            session_id,
            message,
            failure_message="Agent message failed",
        )
        if result.get("success") and isinstance(result.get("data"), dict):
            result["data"] = normalize_agent_session(result["data"])
        return result

    def approve_agent_action(self, session_id: str, action_id: str, approved: bool) -> ActionResult:
        result = self._call_action(
            "approve_agent_action",
            session_id,
            action_id,
            bool(approved),
            failure_message="Agent action approval failed",
        )
        if result.get("success") and isinstance(result.get("data"), dict):
            result["data"] = normalize_agent_session(result["data"])
        return result

    def instantiate_prefab(
        self,
        path: str,
        name: str,
        x: float = 0.0,
        y: float = 0.0,
    ) -> ActionResult:
        """Instantiate a prefab at a world position in the active scene."""
        overrides = {"": {"components": {"Transform": {"x": x, "y": y}}}}
        return self._call_action(
            "instantiate_prefab", path, name, None, overrides,
            failure_message="Prefab instantiation failed",
        )

    def get_sprite_metadata(self, asset_path: str) -> dict[str, Any]:
        """Read sprite metadata for an asset through the engine API."""
        return self._call_read_args("get_sprite_metadata", {}, asset_path)

    def save_sprite_metadata(self, asset_path: str, metadata: dict[str, Any]) -> ActionResult:
        """Persist sprite metadata for an asset through the engine API."""
        return self._call_action(
            "save_asset_metadata", asset_path, metadata,
            failure_message="Sprite metadata save failed",
        )

    def save_scene(self) -> ActionResult:
        return self._call_action("save_scene", failure_message="Scene save failed")

    def undo(self) -> ActionResult:
        return self._call_action("undo", failure_message="Undo failed")

    def redo(self) -> ActionResult:
        return self._call_action("redo", failure_message="Redo failed")

    def has_unsaved_changes(self) -> bool:
        return bool(self.get_active_scene_info().get("dirty", False))

    def shutdown(self) -> None:
        if not self._owns_api or self._api is None:
            return
        shutdown = getattr(self._api, "shutdown", None)
        if callable(shutdown):
            shutdown()
        self._api = None

    def _engine_api(self) -> Any:
        if self._api is None:
            from engine.api import EngineAPI

            self._api = EngineAPI(
                project_root=self._project_root.as_posix(),
                auto_ensure_project=self._auto_ensure_project,
                read_only=self._read_only,
            )
        return self._api

    def _load_scene_for_runtime_inspection(self, scene_ref: str) -> ActionResult:
        result = self._call_action(
            "load_scene_for_runtime_inspection",
            scene_ref,
            failure_message="Scene load failed",
        )
        if result.get("success"):
            self._selected_entity_name = None
        return result

    def _call_read(self, method_name: str, default: Any) -> Any:
        try:
            return getattr(self._engine_api(), method_name)()
        except Exception as exc:
            self.last_error = str(exc)
            return default

    def _call_read_args(self, method_name: str, default: Any, *args: Any) -> Any:
        try:
            return getattr(self._engine_api(), method_name)(*args)
        except Exception as exc:
            self.last_error = str(exc)
            return default

    def _call_action(self, method_name: str, *args: Any, failure_message: str) -> ActionResult:
        try:
            result = getattr(self._engine_api(), method_name)(*args)
        except Exception as exc:
            self.last_error = str(exc)
            return self._failure(f"{failure_message}: {exc}")
        if isinstance(result, dict) and "success" in result:
            return dict(result)
        return {"success": True, "message": method_name, "data": result}

    def _failure(self, message: str) -> ActionResult:
        return {"success": False, "message": message, "data": None}
