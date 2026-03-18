from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from engine.ai.types import AIDiffSummary, AIToolCall


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    category: str
    read_only: bool
    write_scope: str
    requires_confirmation: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "read_only": self.read_only,
            "write_scope": self.write_scope,
            "requires_confirmation": self.requires_confirmation,
        }


class AuthoringToolRegistry:
    def __init__(self) -> None:
        self._definitions: Dict[str, ToolDefinition] = {
            "inspect_scene": ToolDefinition("inspect_scene", "Inspect the active scene and current selection.", "read", True, "read", False),
            "inspect_entity": ToolDefinition("inspect_entity", "Inspect one entity from the active scene.", "read", True, "read", False),
            "list_assets": ToolDefinition("list_assets", "List project assets matching a search term.", "read", True, "read", False),
            "list_prefabs": ToolDefinition("list_prefabs", "List prefab files in the active project.", "read", True, "read", False),
            "list_scripts": ToolDefinition("list_scripts", "List gameplay script files in the active project.", "read", True, "read", False),
            "create_entity": ToolDefinition("create_entity", "Create an entity in the current scene.", "scene", False, "scene", True),
            "create_child_entity": ToolDefinition("create_child_entity", "Create a child entity under another entity.", "scene", False, "scene", True),
            "add_component": ToolDefinition("add_component", "Add one component to an entity.", "scene", False, "scene", True),
            "edit_component": ToolDefinition("edit_component", "Edit one component property on an entity.", "scene", False, "scene", True),
            "create_camera2d": ToolDefinition("create_camera2d", "Create a serializable 2D camera entity.", "scene", False, "scene", True),
            "create_canvas": ToolDefinition("create_canvas", "Create a UI canvas entity.", "scene", False, "scene", True),
            "create_ui_text": ToolDefinition("create_ui_text", "Create a UI text node.", "scene", False, "scene", True),
            "create_ui_button": ToolDefinition("create_ui_button", "Create a UI button node.", "scene", False, "scene", True),
            "instantiate_prefab": ToolDefinition("instantiate_prefab", "Instantiate a prefab into the current scene.", "prefab", False, "prefab", True),
            "add_script_behaviour": ToolDefinition("add_script_behaviour", "Attach ScriptBehaviour to an entity.", "scene", False, "scene", True),
            "write_script": ToolDefinition("write_script", "Create or replace a gameplay script in scripts/.", "script", False, "script", True),
            "save_asset_metadata": ToolDefinition("save_asset_metadata", "Save editable asset metadata in the project.", "asset", False, "asset_meta", True),
            "set_scene_connection": ToolDefinition("set_scene_connection", "Update scene flow metadata.", "scene", False, "scene", True),
            "validate_play_cycle": ToolDefinition("validate_play_cycle", "Run PLAY -> STEP -> STOP validation.", "validation", True, "read", False),
        }
        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "inspect_scene": self._inspect_scene,
            "inspect_entity": self._inspect_entity,
            "list_assets": self._list_assets,
            "list_prefabs": self._list_prefabs,
            "list_scripts": self._list_scripts,
            "create_entity": self._create_entity,
            "create_child_entity": self._create_child_entity,
            "add_component": self._add_component,
            "edit_component": self._edit_component,
            "create_camera2d": self._create_camera,
            "create_canvas": self._create_canvas,
            "create_ui_text": self._create_ui_text,
            "create_ui_button": self._create_ui_button,
            "instantiate_prefab": self._instantiate_prefab,
            "add_script_behaviour": self._add_script_behaviour,
            "write_script": self._write_script,
            "save_asset_metadata": self._save_asset_metadata,
            "set_scene_connection": self._set_scene_connection,
            "validate_play_cycle": self._validate_play_cycle,
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        return [definition.to_dict() for definition in self._definitions.values()]

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._definitions

    def definition(self, tool_name: str) -> Optional[ToolDefinition]:
        return self._definitions.get(tool_name)

    def execute(
        self,
        engine_api,
        tool_call: AIToolCall,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> Dict[str, Any]:
        definition = self._definitions.get(tool_call.tool_name)
        if definition is None:
            return {"success": False, "message": f"Unknown tool: {tool_call.tool_name}"}

        if definition.write_scope == "script" and not allow_python:
            return {"success": False, "message": "Python change blocked: script writes require explicit approval."}
        if definition.write_scope == "engine":
            return {"success": False, "message": "Engine code changes are outside the assistant write scope."}
        if definition.write_scope == "asset_meta":
            asset_path = str(tool_call.arguments.get("asset_path", "") or "")
            if not self._is_under_project_dir(engine_api, asset_path, "assets"):
                return {"success": False, "message": "Asset metadata writes must stay inside assets/."}
        if definition.write_scope == "script":
            target = str(tool_call.arguments.get("target", "") or "")
            if not self._is_under_project_dir(engine_api, target, "scripts"):
                return {"success": False, "message": "Script writes must stay inside scripts/."}
        if definition.write_scope == "prefab":
            prefab_path = str(tool_call.arguments.get("path", "") or "")
            if prefab_path and not self._is_under_project_dir(engine_api, prefab_path, "prefabs"):
                return {"success": False, "message": "Prefab operations must stay inside prefabs/."}
        if definition.write_scope == "scene" and allow_engine_changes:
            # The engine flag is accepted for compatibility but scene tools never escalate to engine writes.
            allow_engine_changes = False

        handler = self._handlers[tool_call.tool_name]
        result = handler(engine_api, **dict(tool_call.arguments))
        tool_call.result = dict(result)
        tool_call.status = "applied" if bool(result.get("success", False)) else "blocked"
        return result

    def build_diff_summary(self, tool_calls: List[AIToolCall]) -> AIDiffSummary:
        entities: List[str] = []
        files: List[str] = []
        assets: List[str] = []
        tools: List[str] = []
        risks: List[str] = []
        seen_entities: set[str] = set()
        seen_files: set[str] = set()
        seen_assets: set[str] = set()
        seen_risks: set[str] = set()

        for tool_call in tool_calls:
            tools.append(tool_call.tool_name)
            entity_name = str(tool_call.arguments.get("name", "") or tool_call.arguments.get("entity_name", "") or "")
            if entity_name and entity_name not in seen_entities:
                seen_entities.add(entity_name)
                entities.append(entity_name)
            target_file = str(tool_call.arguments.get("target", "") or "")
            if target_file and target_file not in seen_files:
                seen_files.add(target_file)
                files.append(target_file)
            asset_path = str(tool_call.arguments.get("asset_path", "") or tool_call.arguments.get("path", "") or "")
            if asset_path and tool_call.write_scope in {"asset_meta", "prefab"} and asset_path not in seen_assets:
                seen_assets.add(asset_path)
                assets.append(asset_path)
            if tool_call.risk and tool_call.risk not in seen_risks and tool_call.risk != "standard":
                seen_risks.add(tool_call.risk)
                risks.append(tool_call.risk)

        summary = f"{len(tool_calls)} tool call(s) prepared for review."
        return AIDiffSummary(
            summary=summary,
            entities=entities,
            files=files,
            assets=assets,
            tools=tools,
            risk_notes=risks,
        )

    def from_execution_action(
        self,
        action,
        script_content_resolver: Callable[[str], str],
    ) -> AIToolCall:
        if action.action_type == "api_call":
            method_name = str(action.args.get("method", "") or "")
            arguments = dict(action.args.get("kwargs", {}) or {})
            definition = self._definitions.get(method_name)
            read_only = definition.read_only if definition is not None else False
            write_scope = definition.write_scope if definition is not None else "scene"
            return AIToolCall(
                id=action.id,
                tool_name=method_name,
                arguments=arguments,
                summary=action.summary,
                status="planned",
                read_only=read_only,
                write_scope=write_scope,
                risk=action.risk,
                requires_confirmation=action.requires_confirmation,
            )

        if action.action_type == "python_write":
            target = str(action.args.get("target", "") or "")
            return AIToolCall(
                id=action.id,
                tool_name="write_script",
                arguments={"target": target, "content": script_content_resolver(target)},
                summary=action.summary,
                status="planned",
                read_only=False,
                write_scope="script",
                risk=action.risk,
                requires_confirmation=action.requires_confirmation,
            )

        return AIToolCall(
            id=action.id,
            tool_name=action.action_type,
            arguments=dict(action.args or {}),
            summary=action.summary,
            status="planned",
            read_only=False,
            write_scope="scene",
            risk=action.risk,
            requires_confirmation=action.requires_confirmation,
        )

    def _is_under_project_dir(self, engine_api, path_value: str, root_key: str) -> bool:
        project_service = getattr(engine_api, "project_service", None)
        if project_service is None or not path_value:
            return False
        root_dir = project_service.get_project_path(root_key).resolve()
        resolved = project_service.resolve_path(path_value).resolve()
        return root_dir == resolved or root_dir in resolved.parents

    def _create_entity(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.create_entity(str(kwargs.get("name", "") or ""), components=kwargs.get("components"))

    def _create_child_entity(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.create_child_entity(
            str(kwargs.get("parent_name", "") or ""),
            str(kwargs.get("name", "") or ""),
            components=kwargs.get("components"),
        )

    def _add_component(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.add_component(
            str(kwargs.get("entity_name", "") or ""),
            str(kwargs.get("component_name", "") or ""),
            data=kwargs.get("data"),
        )

    def _edit_component(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.edit_component(
            str(kwargs.get("entity_name", "") or ""),
            str(kwargs.get("component_name", "") or kwargs.get("component", "") or ""),
            str(kwargs.get("property_name", "") or kwargs.get("property", "") or ""),
            kwargs.get("value"),
        )

    def _create_camera(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.create_camera2d(
            str(kwargs.get("name", "") or ""),
            transform=kwargs.get("transform"),
            camera=kwargs.get("camera"),
        )

    def _create_canvas(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.create_canvas(
            name=str(kwargs.get("name", "Canvas") or "Canvas"),
            reference_width=int(kwargs.get("reference_width", 800) or 800),
            reference_height=int(kwargs.get("reference_height", 600) or 600),
            sort_order=int(kwargs.get("sort_order", 0) or 0),
        )

    def _create_ui_text(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.create_ui_text(
            name=str(kwargs.get("name", "") or ""),
            text=str(kwargs.get("text", "") or ""),
            parent=str(kwargs.get("parent", "") or ""),
            rect_transform=kwargs.get("rect_transform"),
            font_size=int(kwargs.get("font_size", 24) or 24),
            alignment=str(kwargs.get("alignment", "center") or "center"),
        )

    def _create_ui_button(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.create_ui_button(
            name=str(kwargs.get("name", "") or ""),
            label=str(kwargs.get("label", "") or ""),
            parent=str(kwargs.get("parent", "") or ""),
            rect_transform=kwargs.get("rect_transform"),
            on_click=kwargs.get("on_click"),
        )

    def _instantiate_prefab(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.instantiate_prefab(
            path=str(kwargs.get("path", "") or ""),
            name=str(kwargs.get("name", "") or "") or None,
            parent=str(kwargs.get("parent", "") or "") or None,
            overrides=kwargs.get("overrides"),
        )

    def _add_script_behaviour(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.add_script_behaviour(
            entity_name=str(kwargs.get("entity_name", "") or ""),
            module_path=str(kwargs.get("module_path", "") or ""),
            public_data=kwargs.get("public_data"),
            run_in_edit_mode=bool(kwargs.get("run_in_edit_mode", False)),
            enabled=bool(kwargs.get("enabled", True)),
        )

    def _write_script(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        project_service = getattr(engine_api, "project_service", None)
        if project_service is None or not project_service.has_project:
            return {"success": False, "message": "Project service not ready for script writes."}
        target = str(kwargs.get("target", "") or "").strip()
        content = str(kwargs.get("content", "") or "")
        if not target:
            return {"success": False, "message": "Script target is required."}
        resolved = project_service.resolve_path(target)
        scripts_root = project_service.get_project_path("scripts").resolve()
        if scripts_root != resolved.resolve() and scripts_root not in resolved.resolve().parents:
            return {"success": False, "message": "Script target must stay inside scripts/."}
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        game = getattr(engine_api, "game", None)
        hot_reload = getattr(game, "hot_reload_manager", None)
        if hot_reload is not None:
            hot_reload.scan_directory()
        return {
            "success": True,
            "message": "Script written.",
            "data": {"path": project_service.to_relative_path(resolved)},
        }

    def _save_asset_metadata(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.save_asset_metadata(
            asset_path=str(kwargs.get("asset_path", "") or ""),
            metadata=dict(kwargs.get("metadata", {}) or {}),
        )

    def _set_scene_connection(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        return engine_api.set_scene_connection(
            key=str(kwargs.get("key", "") or ""),
            path=str(kwargs.get("path", "") or ""),
        )

    def _inspect_scene(self, engine_api, **_: Any) -> Dict[str, Any]:
        game = getattr(engine_api, "game", None)
        selected_entity = ""
        active_world = getattr(game, "world", None)
        if active_world is not None:
            selected_entity = str(getattr(active_world, "selected_entity_name", "") or "")
        return {
            "success": True,
            "message": "Scene inspected.",
            "data": {
                "current_scene_path": str(getattr(game, "current_scene_path", "") or ""),
                "selected_entity": selected_entity,
                "entities": engine_api.list_entities(),
            },
        }

    def _inspect_entity(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        entity_name = str(kwargs.get("entity_name", "") or kwargs.get("name", "") or "")
        try:
            entity = engine_api.get_entity(entity_name)
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        return {"success": True, "message": "Entity inspected.", "data": entity}

    def _list_assets(self, engine_api, **kwargs: Any) -> Dict[str, Any]:
        search = str(kwargs.get("search", "") or "")
        return {"success": True, "message": "Assets listed.", "data": engine_api.list_project_assets(search=search)}

    def _list_prefabs(self, engine_api, **_: Any) -> Dict[str, Any]:
        project_service = getattr(engine_api, "project_service", None)
        if project_service is None or not project_service.has_project:
            return {"success": True, "message": "No project loaded.", "data": []}
        prefabs_root = project_service.get_project_path("prefabs")
        items = []
        for path in sorted(prefabs_root.rglob("*.json")):
            if path.is_file():
                items.append(project_service.to_relative_path(path))
        return {"success": True, "message": "Prefabs listed.", "data": items}

    def _list_scripts(self, engine_api, **_: Any) -> Dict[str, Any]:
        project_service = getattr(engine_api, "project_service", None)
        if project_service is None or not project_service.has_project:
            return {"success": True, "message": "No project loaded.", "data": []}
        scripts_root = project_service.get_project_path("scripts")
        items = []
        for path in sorted(scripts_root.rglob("*.py")):
            if path.is_file():
                items.append(project_service.to_relative_path(path))
        return {"success": True, "message": "Scripts listed.", "data": items}

    def _validate_play_cycle(self, engine_api, **_: Any) -> Dict[str, Any]:
        try:
            engine_api.play()
            game = getattr(engine_api, "game", None)
            if game is not None and hasattr(game, "step_frame"):
                engine_api.step(5)
            engine_api.stop()
            return {"success": True, "message": "PLAY -> STOP validation passed."}
        except Exception as exc:
            return {"success": False, "message": f"PLAY cycle failed: {exc}"}
