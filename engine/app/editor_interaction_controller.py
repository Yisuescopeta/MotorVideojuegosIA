from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, Optional

import pyray as rl

from engine.editor.cursor_manager import CursorVisualState
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
        self._get_scene_manager = get_scene_manager
        self._get_selection_system = get_selection_system
        self._get_gizmo_system = get_gizmo_system
        self._get_ui_system = get_ui_system
        self._get_hierarchy_panel = get_hierarchy_panel
        self._get_inspector_system = get_inspector_system
        self._get_history_manager = get_history_manager
        self._get_current_scene_viewport_size = get_current_scene_viewport_size
        self._get_current_viewport_size = get_current_viewport_size

    def commit_gizmo_drag(self, drag: Any) -> None:
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
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

        if ext.lower() == ".prefab":
            print(f"[DROP] Instantiating Prefab '{name}' from {file_path}")
            from engine.assets.prefab import PrefabManager

            prefab_data = PrefabManager.load_prefab_data(file_path)
            if prefab_data and scene_manager is not None:
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
                    scene_manager.set_selected_entity(unique_name)
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
                scene_manager.set_selected_entity(name)
            return

        new_entity = active_world.create_entity(name)
        from engine.components.collider import Collider
        from engine.components.sprite import Sprite
        from engine.components.transform import Transform

        new_entity.add_component(Transform(drop_pos.x, drop_pos.y))
        new_entity.add_component(Sprite(file_path))
        new_entity.add_component(Collider(32, 32))
        active_world.selected_entity_name = name

    def handle_selection_and_gizmos(self, active_world: Optional["World"]) -> None:
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

        ui_system = self._get_ui_system()
        if ui_system is not None and active_world is not None:
            ui_system.ensure_layout_cache(active_world, scene_viewport_size)

        gizmo_system = self._get_gizmo_system()
        scene_manager = self._get_scene_manager()
        if gizmo_system is not None and active_world is not None:
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
                    ui_system=ui_system,
                    ui_mouse_pos=mouse_ui,
                    ui_viewport_size=scene_viewport_size,
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
        if not hand_tool_active and not gizmo_active and mouse_in_scene and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            ui_hit = None
            if ui_system is not None:
                ui_hit = ui_system.find_topmost_entity_at_point(
                    active_world,
                    float(mouse_ui.x),
                    float(mouse_ui.y),
                    scene_viewport_size,
                )
            if ui_hit is not None:
                if scene_manager is not None:
                    scene_manager.set_selected_entity(ui_hit.name)
                else:
                    active_world.selected_entity_name = ui_hit.name
            else:
                selected_name = selection_system.update(active_world, mouse_world)
                if scene_manager is not None:
                    scene_manager.set_selected_entity(selected_name)

    def resolve_cursor_state(self, active_world: Optional["World"]) -> CursorVisualState:
        state = CursorVisualState.DEFAULT
        mouse = rl.get_mouse_position()
        layout = self._get_editor_layout()

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
                state = max(
                    state,
                    ui_system.get_cursor_intent(
                        active_world,
                        viewport_size,
                        float(mouse_ui.x),
                        float(mouse_ui.y),
                    ),
                )

        return state

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

    def _get_project_service(self) -> Any:
        layout = self._get_editor_layout()
        project_panel = getattr(layout, "project_panel", None) if layout is not None else None
        return getattr(project_panel, "project_service", None)
