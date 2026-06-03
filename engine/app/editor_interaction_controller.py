from __future__ import annotations

import copy
import os
from typing import TYPE_CHECKING, Any, Callable, Optional

import pyray as rl
from engine.components.camera2d import Camera2D
from engine.components.transform import Transform
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.editor_selection import EditorSelectionState
from engine.editor.editor_tools import EditorTool, PivotMode, TransformSpace

if TYPE_CHECKING:
    from engine.ecs.world import World


class EditorInteractionController:
    """Owns scene-view interaction, gizmo orchestration, and cursor intent."""

    def __init__(
        self,
        *,
        get_state: Callable[[], Any],
        get_editor_layout: Callable[[], Any],
        get_editor_selection: Callable[[], Any],
        get_scene_manager: Callable[[], Any],
        get_selection_system: Callable[[], Any],
        get_gizmo_system: Callable[[], Any],
        get_ui_system: Callable[[], Any],
        get_hierarchy_panel: Callable[[], Any],
        get_inspector_system: Callable[[], Any],
        get_history_manager: Callable[[], Any],
        get_current_scene_viewport_size: Callable[[], tuple[float, float]],
        get_current_viewport_size: Callable[[], tuple[float, float]],
    ) -> None:
        self._get_state = get_state
        self._get_editor_layout = get_editor_layout
        self._get_editor_selection = get_editor_selection
        self._get_scene_manager = get_scene_manager
        self._get_selection_system = get_selection_system
        self._get_gizmo_system = get_gizmo_system
        self._get_ui_system = get_ui_system
        self._get_hierarchy_panel = get_hierarchy_panel
        self._get_inspector_system = get_inspector_system
        self._get_history_manager = get_history_manager
        self._get_current_scene_viewport_size = get_current_scene_viewport_size
        self._get_current_viewport_size = get_current_viewport_size
        self._camera_drag_state: dict[str, Any] | None = None

    def _apply_selection(self, active_world: Optional["World"], entity_name: Optional[str]) -> Optional[str]:
        normalized = EditorSelectionState.normalize(entity_name)
        selection_state = self._get_editor_selection()
        if selection_state is not None:
            normalized = selection_state.set(normalized)
        scene_manager = self._get_scene_manager()
        if scene_manager is not None:
            scene_manager.set_selected_entity(normalized)
        elif active_world is not None:
            active_world.selected_entity_name = normalized
        if selection_state is not None and active_world is not None:
            selection_state.apply_to_world(active_world)
        return normalized

    def commit_gizmo_drag(self, drag: Any) -> None:
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
            return
        if getattr(drag, "component_name", "") == "Camera2D":
            scene_manager.apply_edit_to_world(
                drag.entity_name,
                "Camera2D",
                "profile_overrides",
                copy.deepcopy(drag.after_state),
            )
            return
        active_key = scene_manager.active_scene_key
        if not active_key:
            return
        apply_state = scene_manager.apply_transform_state
        if getattr(drag, "component_name", "") == "RectTransform":
            apply_state = scene_manager.apply_rect_transform_state
        apply_state(
            drag.entity_name,
            drag.after_state,
            key_or_path=active_key,
            record_history=True,
            label=drag.label,
        )

    def handle_scene_view_drag_drop(self, active_world: Optional["World"]) -> None:
        state = self._get_state()
        layout = self._get_editor_layout()
        if (
            not state.is_edit()
            or layout is None
            or layout.project_panel is None
            or not layout.project_panel.dragging_file
        ):
            return
        if not rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            return
        if not layout.is_mouse_in_scene_view() or active_world is None:
            return

        file_path = layout.project_panel.dragging_file
        sprite_locator = self._build_project_asset_locator(file_path)
        drop_pos = layout.get_scene_mouse_pos()
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
            return

        if ext.lower() == ".prefab":
            print(f"[DROP] Instantiating Prefab '{name}' from {file_path}")
            from engine.assets.prefab import PrefabManager

            prefab_data = PrefabManager.load_prefab_data(file_path)
            if prefab_data:
                prefab_locator = self._build_prefab_locator(file_path, scene_manager)
                unique_name = name
                count = 1
                while active_world.get_entity_by_name(unique_name):
                    unique_name = f"{name}_{count}"
                    count += 1
                if scene_manager.instantiate_prefab(
                    unique_name,
                    prefab_path=prefab_locator,
                    overrides={"": {"components": {"Transform": {"x": drop_pos.x, "y": drop_pos.y}}}},
                    root_name=prefab_data.get("root_name", unique_name),
                ):
                    self._apply_selection(active_world, unique_name)
            return

        base_name = name
        count = 1
        while active_world.get_entity_by_name(name):
            name = f"{base_name}_{count}"
            count += 1

        print(f"[DROP] Creating Sprite Entity '{name}' from {file_path}")
        if scene_manager is not None:
            created = scene_manager.create_entity(
                name,
                self._build_sprite_entity_payload(sprite_locator, drop_pos.x, drop_pos.y),
            )
            if created:
                self._apply_selection(active_world, name)
        return

    def handle_inspector_drag_drop(self, active_world: Optional["World"] = None) -> None:
        state = self._get_state()
        layout = self._get_editor_layout()
        project_panel = getattr(layout, "project_panel", None) if layout is not None else None
        if (
            not state.is_edit()
            or layout is None
            or project_panel is None
            or not getattr(project_panel, "dragging_file", None)
            or not hasattr(layout, "is_mouse_in_inspector")
            or not layout.is_mouse_in_inspector()
        ):
            return
        if not rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            return

        scene_manager = self._get_scene_manager()
        if scene_manager is None or not hasattr(scene_manager, "apply_edit_to_world"):
            return
        entity_name = self._get_selected_entity_name(active_world)
        if not entity_name:
            return
        edit_target = self._inspector_asset_edit_target(str(project_panel.dragging_file))
        if edit_target is None:
            return
        component_name, property_name, locator = edit_target
        scene_manager.apply_edit_to_world(entity_name, component_name, property_name, locator)

    def handle_selection_and_gizmos(self, active_world: Optional["World"]) -> None:
        state = self._get_state()
        mouse_world = rl.Vector2(0, 0)
        mouse_ui = rl.Vector2(0, 0)
        mouse_in_scene = False
        scene_viewport_size = self._get_current_scene_viewport_size()
        layout = self._get_editor_layout()
        if layout is not None:
            mouse_world = layout.get_scene_mouse_pos()
            mouse_ui = layout.get_scene_overlay_mouse_pos()
            mouse_in_scene = layout.is_mouse_in_scene_view()
            if layout.is_mouse_in_inspector():
                mouse_in_scene = False

        if self._handle_game_camera_edit(active_world):
            return

        ui_system = self._get_ui_system()
        scene_ui_visible = False
        if ui_system is not None and active_world is not None:
            scene_ui_visible = bool(
                ui_system.should_render_scene_view_ui(
                    active_world,
                    allow_runtime=state.allows_gameplay(),
                )
                )
            if scene_ui_visible:
                ui_system.ensure_layout_cache(active_world, scene_viewport_size)

        inspector_system = self._get_inspector_system()
        tilemap_tool_active = bool(
            inspector_system is not None
            and active_world is not None
            and hasattr(inspector_system, "is_tilemap_tool_active")
            and inspector_system.is_tilemap_tool_active(active_world)
        )
        gizmo_system = self._get_gizmo_system()
        tilemap_preview = None
        if tilemap_tool_active and inspector_system is not None and active_world is not None:
            inspector_system.handle_tilemap_scene_input(active_world, mouse_world, mouse_in_scene)
            if hasattr(inspector_system, "get_tilemap_preview_snapshot"):
                tilemap_preview = inspector_system.get_tilemap_preview_snapshot(active_world)
        if gizmo_system is not None and hasattr(gizmo_system, "set_tilemap_preview"):
            gizmo_system.set_tilemap_preview(tilemap_preview)

        scene_manager = self._get_scene_manager()
        if not tilemap_tool_active and gizmo_system is not None and active_world is not None:
            if gizmo_system.is_dragging or mouse_in_scene:
                was_dragging = gizmo_system.is_dragging
                active_tool = layout.active_tool if layout is not None else EditorTool.MOVE
                transform_space = layout.transform_space if layout is not None else TransformSpace.WORLD
                pivot_mode = layout.pivot_mode if layout is not None else PivotMode.PIVOT
                snap_settings = layout.snap_settings if layout is not None else None
                gizmo_system.update(
                    active_world,
                    mouse_world,
                    active_tool,
                    transform_space,
                    pivot_mode,
                    snap_settings,
                    ui_system=ui_system if scene_ui_visible else None,
                    ui_mouse_pos=mouse_ui,
                    ui_viewport_size=scene_viewport_size,
                    camera_profile_id=getattr(layout, "game_view_device_profile", None) if layout is not None else None,
                    camera_viewport_size=self._get_current_viewport_size(),
                )
                if (was_dragging or gizmo_system.is_dragging) and scene_manager is not None:
                    scene_manager.mark_edit_world_dirty(reason="transient_preview")
                drag = gizmo_system.consume_completed_drag()
                if drag is not None:
                    self.commit_gizmo_drag(drag)

        selection_system = self._get_selection_system()
        if selection_system is None or active_world is None:
            return

        gizmo_active = gizmo_system.is_hot() if gizmo_system is not None else False
        hand_tool_active = layout is not None and layout.active_tool == EditorTool.HAND
        if tilemap_tool_active:
            return
        if not hand_tool_active and not gizmo_active and mouse_in_scene and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            ui_hit = None
            if ui_system is not None and scene_ui_visible:
                ui_hit = ui_system.find_topmost_entity_at_point(
                    active_world,
                    float(mouse_ui.x),
                    float(mouse_ui.y),
                    scene_viewport_size,
                )
            if ui_hit is not None:
                self._apply_selection(active_world, ui_hit.name)
            else:
                selected_name = selection_system.update(active_world, mouse_world)
                self._apply_selection(active_world, selected_name)

    def resolve_cursor_state(self, active_world: Optional["World"]) -> CursorVisualState:
        state = CursorVisualState.DEFAULT
        mouse = rl.get_mouse_position()
        layout = self._get_editor_layout()
        runtime_ui_visible = False
        if active_world is not None:
            runtime_ui_visible = bool(self._get_state().allows_gameplay())

        if layout is not None:
            state = max(state, layout.get_cursor_intent())

        hierarchy_panel = self._get_hierarchy_panel()
        if hierarchy_panel is not None:
            state = max(state, hierarchy_panel.get_cursor_intent(mouse))

        if layout is not None and layout.active_bottom_tab == "PROJECT" and layout.project_panel is not None:
            state = max(state, layout.project_panel.get_cursor_intent(mouse))
        if layout is not None and layout.active_bottom_tab == "FLOW" and getattr(layout, "flow_panel", None) is not None:
            state = max(state, layout.flow_panel.get_cursor_intent(mouse))
        if layout is not None and layout.active_tab == "FLOW" and getattr(layout, "flow_workspace_panel", None) is not None:
            state = max(state, layout.flow_workspace_panel.get_cursor_intent(mouse))

        inspector_system = self._get_inspector_system()
        if inspector_system is not None:
            state = max(state, inspector_system.get_cursor_intent(mouse))
            if (
                active_world is not None
                and layout is not None
                and layout.active_tab == "SCENE"
                and rl.check_collision_point_rec(mouse, layout.get_center_view_rect())
                and hasattr(inspector_system, "is_tilemap_tool_active")
                and inspector_system.is_tilemap_tool_active(active_world)
            ):
                state = max(state, CursorVisualState.INTERACTIVE)

        gizmo_system = self._get_gizmo_system()
        if gizmo_system is not None and gizmo_system.is_hot():
            state = max(state, CursorVisualState.INTERACTIVE)

        ui_system = self._get_ui_system()
        if ui_system is not None and active_world is not None and layout is not None:
            view_rect = layout.get_center_view_rect()
            if layout.active_tab in ("SCENE", "GAME") and rl.check_collision_point_rec(mouse, view_rect):
                mouse_ui = layout.get_scene_overlay_mouse_pos()
                viewport_size = (
                    self._get_current_scene_viewport_size()
                    if layout.active_tab == "SCENE"
                    else self._get_current_viewport_size()
                )
                if layout.active_tab == "GAME":
                    state = max(
                        state,
                        ui_system.get_cursor_intent(
                            active_world,
                            viewport_size,
                            float(mouse_ui.x),
                            float(mouse_ui.y),
                            allow_interaction=bool(layout.active_tab == "GAME" and self._get_state().is_running()),
                        ),
                    )
                elif runtime_ui_visible or ui_system.should_render_scene_view_ui(active_world, allow_runtime=False):
                    state = max(
                        state,
                        ui_system.get_cursor_intent(
                            active_world,
                            viewport_size,
                            float(mouse_ui.x),
                            float(mouse_ui.y),
                            allow_interaction=False,
                        ),
                    )

        return state

    def _handle_game_camera_edit(self, active_world: Optional["World"]) -> bool:
        layout = self._get_editor_layout()
        if layout is None:
            return False
        if getattr(layout, "active_tab", "") != "GAME" or getattr(layout, "active_tool", None) != EditorTool.CAMERA:
            self._camera_drag_state = None
            return False
        if active_world is None:
            return True

        scene_manager = self._get_scene_manager()
        profile_id = str(getattr(layout, "game_view_device_profile", "") or "")
        camera_entity = self._find_primary_camera_entity(active_world)
        if camera_entity is None:
            self._camera_drag_state = None
            return True

        if bool(getattr(layout, "request_reset_camera_profile", False)):
            layout.request_reset_camera_profile = False
            self._reset_camera_profile_override(camera_entity, profile_id, scene_manager)
            return True

        mouse_in_game = bool(hasattr(layout, "is_mouse_in_game_view") and layout.is_mouse_in_game_view())
        dragging = self._camera_drag_state is not None
        if not mouse_in_game and not dragging:
            return True

        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and mouse_in_game:
            mouse = rl.get_mouse_position()
            texture_x, texture_y = layout.map_game_view_screen_point_to_texture(float(mouse.x), float(mouse.y))
            self._camera_drag_state = {
                "entity_name": camera_entity.name,
                "profile_id": profile_id,
                "last_x": float(texture_x),
                "last_y": float(texture_y),
            }
            self._ensure_camera_profile_override(camera_entity, profile_id)
            return True

        if self._camera_drag_state is None:
            return True

        if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
            mouse = rl.get_mouse_position()
            texture_x, texture_y = layout.map_game_view_screen_point_to_texture(float(mouse.x), float(mouse.y))
            delta_x = float(texture_x) - float(self._camera_drag_state["last_x"])
            delta_y = float(texture_y) - float(self._camera_drag_state["last_y"])
            self._camera_drag_state["last_x"] = float(texture_x)
            self._camera_drag_state["last_y"] = float(texture_y)
            self._apply_camera_drag_delta(camera_entity, profile_id, delta_x, delta_y)
            if scene_manager is not None:
                scene_manager.mark_edit_world_dirty(reason="transient_preview")
            return True

        if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            self._persist_camera_profile_override(camera_entity, profile_id, scene_manager)
            self._camera_drag_state = None
            return True

        if not rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
            self._camera_drag_state = None
        return True

    @staticmethod
    def _find_primary_camera_entity(active_world: "World") -> Any | None:
        for entity in active_world.get_entities_with(Transform, Camera2D):
            camera = entity.get_component(Camera2D)
            if camera is not None and camera.enabled and camera.is_primary:
                return entity
        return None

    def _ensure_camera_profile_override(self, camera_entity: Any, profile_id: str) -> dict[str, Any]:
        camera = camera_entity.get_component(Camera2D)
        transform = camera_entity.get_component(Transform)
        if camera is None or transform is None:
            return {}
        overrides = self._camera_overrides(camera)
        existing = overrides.get(profile_id)
        if isinstance(existing, dict):
            return existing
        payload: dict[str, Any] = {
            "offset_x": float(camera.offset_x),
            "offset_y": float(camera.offset_y),
            "zoom": float(camera.zoom),
            "rotation": float(camera.rotation),
        }
        if camera.follow_entity:
            payload["target_offset_x"] = 0.0
            payload["target_offset_y"] = 0.0
        else:
            payload["target_x"] = float(transform.x)
            payload["target_y"] = float(transform.y)
        overrides[profile_id] = payload
        camera.profile_overrides = overrides
        return payload

    def _apply_camera_drag_delta(self, camera_entity: Any, profile_id: str, delta_x: float, delta_y: float) -> None:
        camera = camera_entity.get_component(Camera2D)
        if camera is None:
            return
        payload = self._ensure_camera_profile_override(camera_entity, profile_id)
        zoom = max(abs(float(payload.get("zoom", camera.zoom) or camera.zoom or 1.0)), 0.0001)
        world_dx = float(delta_x) / zoom
        world_dy = float(delta_y) / zoom
        if camera.follow_entity:
            payload["target_offset_x"] = float(payload.get("target_offset_x", 0.0) or 0.0) - world_dx
            payload["target_offset_y"] = float(payload.get("target_offset_y", 0.0) or 0.0) - world_dy
        else:
            payload["target_x"] = float(payload.get("target_x", 0.0) or 0.0) - world_dx
            payload["target_y"] = float(payload.get("target_y", 0.0) or 0.0) - world_dy

    def _persist_camera_profile_override(self, camera_entity: Any, profile_id: str, scene_manager: Any) -> None:
        camera = camera_entity.get_component(Camera2D)
        if camera is None or scene_manager is None:
            return
        scene_manager.apply_edit_to_world(
            camera_entity.name,
            "Camera2D",
            "profile_overrides",
            copy.deepcopy(self._camera_overrides(camera)),
        )

    def _reset_camera_profile_override(self, camera_entity: Any, profile_id: str, scene_manager: Any) -> None:
        camera = camera_entity.get_component(Camera2D)
        if camera is None:
            return
        overrides = self._camera_overrides(camera)
        overrides.pop(profile_id, None)
        camera.profile_overrides = overrides
        if scene_manager is not None:
            scene_manager.apply_edit_to_world(
                camera_entity.name,
                "Camera2D",
                "profile_overrides",
                copy.deepcopy(overrides),
            )

    @staticmethod
    def _camera_overrides(camera: Camera2D) -> dict[str, dict[str, Any]]:
        overrides = getattr(camera, "profile_overrides", {})
        if not isinstance(overrides, dict):
            camera.profile_overrides = {}
            return {}
        return overrides

    @staticmethod
    def _build_sprite_entity_payload(file_path: str, x: float, y: float) -> dict[str, dict[str, Any]]:
        return {
            "Transform": {
                "enabled": True,
                "x": x,
                "y": y,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
            "Sprite": {
                "enabled": True,
                "texture_path": file_path,
                "width": 0,
                "height": 0,
                "origin_x": 0.5,
                "origin_y": 0.5,
                "flip_x": False,
                "flip_y": False,
                "tint": [255, 255, 255, 255],
            },
            "Collider": {
                "enabled": True,
                "width": 32,
                "height": 32,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "is_trigger": False,
            },
        }

    def _build_project_asset_locator(self, file_path: str) -> str:
        project_service = self._get_project_service()
        if project_service is None:
            return file_path
        return project_service.to_relative_path(file_path)

    def _build_prefab_locator(self, file_path: str, scene_manager: Any) -> str:
        project_service = self._get_project_service()
        if project_service is None:
            return file_path
        active_scene = scene_manager.get_active_scene_summary() if hasattr(scene_manager, "get_active_scene_summary") else {}
        scene_source_path = str(active_scene.get("path", "")).strip() or None
        return project_service.to_scene_locator(file_path, scene_source_path=scene_source_path)

    def _get_selected_entity_name(self, active_world: Optional["World"]) -> Optional[str]:
        selection_state = self._get_editor_selection()
        selected = getattr(selection_state, "entity_name", None)
        if selected:
            return str(selected)
        if active_world is not None:
            selected = getattr(active_world, "selected_entity_name", None)
            if selected:
                return str(selected)
        return None

    def _inspector_asset_edit_target(self, file_path: str) -> Optional[tuple[str, str, str]]:
        locator = self._build_project_asset_locator(file_path)
        lower = file_path.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".bmp")):
            return ("Sprite", "texture_path", locator)
        if lower.endswith(".py"):
            return ("ScriptBehaviour", "module_path", locator)
        if lower.endswith((".wav", ".ogg", ".mp3", ".flac")):
            return ("AudioSource", "asset_path", locator)
        if lower.endswith((".mat", ".material", ".mtl")):
            return ("RenderStyle2D", "material_path", locator)
        return None

    def _get_project_service(self) -> Any:
        layout = self._get_editor_layout()
        project_panel = getattr(layout, "project_panel", None) if layout is not None else None
        return getattr(project_panel, "project_service", None)
