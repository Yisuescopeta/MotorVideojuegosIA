"""
engine/inspector/inspector_system.py - Dedicated inspector editors.
"""

from __future__ import annotations

import copy

import pyray as rl
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.inspector.component_editor_registry import ComponentEditorRegistry
from engine.levels.component_registry import create_default_registry


PayloadUpdater = Callable[[Dict[str, Any]], None]
CommitCallback = Callable[[Any], bool]


class InspectorSystem:
    """Unity-like inspector with dedicated editors for built-in components."""

    BG_COLOR = rl.Color(30, 30, 30, 255)
    HEADER_COLOR = rl.Color(50, 50, 50, 255)
    FIELD_BG_COLOR = rl.Color(20, 20, 20, 255)
    TEXT_COLOR = rl.Color(220, 220, 220, 255)
    LABEL_COLOR = rl.Color(180, 180, 180, 255)
    HIGHLIGHT_COLOR = rl.Color(60, 100, 150, 255)

    FONT_SIZE: int = 10
    LINE_HEIGHT: int = 18
    MARGIN: int = 4
    LABEL_WIDTH: int = 80

    def __init__(self) -> None:
        self.expanded_components: Set[str] = set()
        self._scene_manager: Any = None

        self.editing_text_field: Optional[str] = None
        self.editing_value_type: str = "float"
        self._editing_commit: Optional[CommitCallback] = None
        self.text_buffer: bytearray = bytearray(128)

        self.show_add_menu: bool = False
        self.registry = create_default_registry()
        self.component_editors = ComponentEditorRegistry()
        self.request_open_sprite_editor_for: Optional[str] = None
        self._register_default_component_editors()

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager

    def open_sprite_editor(self, asset_path: str) -> None:
        self.request_open_sprite_editor_for = asset_path

    def has_dedicated_editor(self, component_name: str) -> bool:
        return self.component_editors.has(component_name)

    def list_dedicated_editors(self) -> list[str]:
        return self.component_editors.list_registered()

    def replace_component_payload(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        component_data: Dict[str, Any],
    ) -> bool:
        payload = copy.deepcopy(component_data)
        if self._scene_manager is not None:
            return self._scene_manager.replace_component_data(entity_name, component_name, payload)

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False

        rebuilt = self.registry.create(component_name, payload)
        if rebuilt is not None:
            entity.add_component(rebuilt)
            return True

        component = self._find_component(entity, component_name)
        if component is None:
            return False
        for key, value in payload.items():
            setattr(component, key, copy.deepcopy(value))
        return True

    def update_component_payload(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        updater: PayloadUpdater,
    ) -> bool:
        payload = self._current_component_payload(world, entity_name, component_name)
        if payload is None:
            return False
        updater(payload)
        return self.replace_component_payload(world, entity_name, component_name, payload)

    def _register_default_component_editors(self) -> None:
        self.component_editors.register("Transform", self._draw_transform_editor)
        self.component_editors.register("Sprite", self._draw_sprite_editor)
        self.component_editors.register("Collider", self._draw_collider_editor)
        self.component_editors.register("RigidBody", self._draw_rigidbody_editor)
        self.component_editors.register("Animator", self._draw_animator_editor)
        self.component_editors.register("Camera2D", self._draw_camera2d_editor)
        self.component_editors.register("AudioSource", self._draw_audio_source_editor)
        self.component_editors.register("InputMap", self._draw_input_map_editor)
        self.component_editors.register("PlayerController2D", self._draw_player_controller_editor)
        self.component_editors.register("ScriptBehaviour", self._draw_script_behaviour_editor)

    def update(self, dt: float, world: "World", is_edit_mode: bool) -> None:
        """Processes keyboard-only inspector input."""
        del dt, world
        if not is_edit_mode:
            self._clear_text_edit()
            return
        if self.editing_text_field and rl.is_key_pressed(rl.KEY_ESCAPE):
            self._clear_text_edit()

    def _commit_text_edit(self, world: "World") -> None:
        """Applies the active text buffer to the current field."""
        if not self.editing_text_field:
            return

        try:
            value_text = self.text_buffer.decode("utf-8").rstrip("\x00")
            if self.editing_value_type == "float":
                value = float(value_text) if value_text else 0.0
            elif self.editing_value_type == "int":
                value = int(float(value_text)) if value_text else 0
            else:
                value = value_text

            if self._editing_commit is not None:
                self._editing_commit(value)
            else:
                self._apply_property_change(world, self.editing_text_field, value)
        except Exception as exc:
            print(f"[INSPECTOR] Failed to commit edit: {exc}")

    def render(self, world: "World", x: int, y: int, width: int, height: int, is_edit_mode: bool) -> None:
        """Draws the inspector."""
        panel_x = x
        panel_y = y
        panel_w = width
        panel_h = height

        unity_header = rl.Color(56, 56, 56, 255)
        unity_tab_bg = rl.Color(42, 42, 42, 255)
        unity_tab_line = rl.Color(58, 121, 187, 255)
        unity_text = rl.Color(200, 200, 200, 255)
        unity_border = rl.Color(25, 25, 25, 255)
        header_height = 22

        rl.begin_scissor_mode(panel_x, panel_y, panel_w, panel_h)
        rl.draw_rectangle(panel_x, panel_y, panel_w, panel_h, self.BG_COLOR)

        header_rect = rl.Rectangle(panel_x, panel_y, panel_w, header_height)
        rl.draw_rectangle_rec(header_rect, unity_header)

        tab_width = 65
        tab_rect = rl.Rectangle(panel_x + 2, panel_y + 2, tab_width, header_height - 4)
        rl.draw_rectangle_rec(tab_rect, unity_tab_bg)
        rl.draw_rectangle(int(panel_x + 2), int(panel_y + header_height - 2), tab_width, 2, unity_tab_line)
        rl.draw_text("Inspector", int(panel_x + 10), int(panel_y + 6), 10, unity_text)
        rl.draw_line(panel_x, int(panel_y + header_height), panel_x + panel_w, int(panel_y + header_height), unity_border)

        content_y = panel_y + header_height + 5
        selected_name = world.selected_entity_name
        if not selected_name:
            rl.draw_text("No selection", int(panel_x + 10), int(content_y + 10), 10, rl.Color(128, 128, 128, 255))
            rl.end_scissor_mode()
            return

        entity = world.get_entity_by_name(selected_name)
        if entity is None:
            rl.end_scissor_mode()
            return

        active_rect = rl.Rectangle(panel_x + 10, content_y, 14, 14)
        rl.draw_rectangle_rec(active_rect, rl.Color(42, 42, 42, 255))
        rl.draw_rectangle_lines_ex(active_rect, 1, rl.Color(80, 80, 80, 255))
        if entity.active:
            rl.draw_rectangle(int(panel_x + 13), int(content_y + 3), 8, 8, rl.Color(70, 130, 200, 255))

        rl.draw_text(entity.name, int(panel_x + 32), int(content_y + 2), 12, rl.Color(230, 230, 230, 255))
        if rl.check_collision_point_rec(rl.get_mouse_position(), active_rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self._apply_property_change(world, f"entity:{entity.id}:active", not entity.active)

        content_y += 22
        rl.draw_line(panel_x, int(content_y), panel_x + panel_w, int(content_y), unity_border)
        content_y += 5

        content_y = self._draw_entity_property("Active", entity.active, f"entity:{entity.id}:active", panel_x, content_y, panel_w, is_edit_mode, world)
        content_y = self._draw_entity_property("Tag", entity.tag, f"entity:{entity.id}:tag", panel_x, content_y, panel_w, is_edit_mode, world)
        content_y = self._draw_entity_property("Layer", entity.layer, f"entity:{entity.id}:layer", panel_x, content_y, panel_w, is_edit_mode, world)
        content_y += 4

        for component in entity.get_all_components():
            content_y = self._draw_component(component, entity.id, panel_x, content_y, panel_w, is_edit_mode, world)
            content_y += 5

        add_btn_rect = rl.Rectangle(panel_x + 10, content_y + 10, panel_w - 20, 24)
        if rl.gui_button(add_btn_rect, "Add Component"):
            self.show_add_menu = not self.show_add_menu

        rl.end_scissor_mode()

        if self.show_add_menu:
            self._draw_add_menu(world, entity, int(panel_x + 10), int(content_y + 35))

    def _draw_component(self, component: Component, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        comp_name = type(component).__name__
        unique_id = f"{entity_id}:{comp_name}"
        is_expanded = unique_id in self.expanded_components
        header_rect = rl.Rectangle(x + 2, y, width - 4, 20)

        mouse_pos = rl.get_mouse_position()
        is_hover = rl.check_collision_point_rec(mouse_pos, header_rect)
        bg_color = rl.Color(70, 70, 70, 255) if is_hover else rl.Color(60, 60, 60, 255)
        rl.draw_rectangle_rec(header_rect, bg_color)

        arrow = "v" if is_expanded else ">"
        rl.draw_text(arrow, int(x + 8), int(y + 5), 10, rl.Color(200, 200, 200, 255))
        rl.draw_text(comp_name, int(x + 22), int(y + 5), 10, rl.Color(220, 220, 220, 255))

        remove_rect = rl.Rectangle(x + width - 20, y + 2, 16, 16)
        remove_hover = False
        if comp_name != "Transform":
            remove_hover = rl.check_collision_point_rec(mouse_pos, remove_rect)
            remove_color = rl.Color(200, 60, 60, 255) if remove_hover else rl.Color(150, 80, 80, 255)
            rl.draw_rectangle_rec(remove_rect, remove_color)
            rl.draw_text("x", int(x + width - 15), int(y + 3), 10, rl.WHITE)

            if remove_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if self._remove_component(world, entity_id, comp_name):
                    return y + 20

        if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and not remove_hover:
            if is_expanded:
                self.expanded_components.discard(unique_id)
            else:
                self.expanded_components.add(unique_id)
            is_expanded = not is_expanded

        current_y = y + 22
        if is_expanded:
            editor = self.component_editors.get(comp_name)
            if editor is not None:
                current_y = editor(component, entity_id, x, current_y, width, is_edit, world)
            else:
                for prop_name, value in self._get_properties(component):
                    full_prop_id = f"{entity_id}:{comp_name}:{prop_name}"
                    current_y = self._draw_property(prop_name, value, full_prop_id, x, current_y, width, is_edit, world)

        return current_y

    def _draw_property(self, label: str, value: Any, prop_id: str, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        if isinstance(value, bool):
            return self._draw_bool_row(label, value, prop_id, x, y, width, is_edit, world)
        if isinstance(value, int) and not isinstance(value, bool):
            return self._draw_int_row(label, int(value), prop_id, x, y, width, is_edit, world)
        if isinstance(value, float):
            return self._draw_float_row(label, float(value), prop_id, x, y, width, is_edit, world)
        if isinstance(value, str):
            return self._draw_text_row(label, value, prop_id, x, y, width, is_edit, world)
        return self._draw_readonly_row(label, str(value), x, y, width)

    def _draw_float_field(
        self,
        value: float,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        self._draw_number_field(f"{value:.2f}", prop_id, x, y, w, h, is_edit, world, "float", on_commit)

    def _draw_int_field(
        self,
        value: int,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        self._draw_number_field(str(value), prop_id, x, y, w, h, is_edit, world, "int", on_commit)

    def _draw_number_field(
        self,
        value_text: str,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        value_type: str,
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        val_rect = rl.Rectangle(x, y + 1, w, h - 2)
        if self.editing_text_field == prop_id:
            self._draw_editing_field(prop_id, value_text, value_type, val_rect, world)
            return

        rl.draw_rectangle_rec(val_rect, rl.Color(42, 42, 42, 255))
        rl.draw_text(value_text, int(x + 5), int(y + 4), 10, rl.Color(200, 200, 200, 255))

        if not is_edit:
            return
        mouse_pos = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse_pos, val_rect):
            rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(70, 130, 200, 255))
            rl.set_mouse_cursor(rl.MOUSE_CURSOR_IBEAM)
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._begin_text_edit(prop_id, value_text, value_type, on_commit)

    def _draw_text_field(
        self,
        value: str,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        val_rect = rl.Rectangle(x, y + 1, w, h - 2)
        if self.editing_text_field == prop_id:
            self._draw_editing_field(prop_id, value, "string", val_rect, world)
            return

        rl.draw_rectangle_rec(val_rect, rl.Color(42, 42, 42, 255))
        rl.draw_text(value, int(x + 5), int(y + 4), 10, rl.Color(200, 200, 200, 255))

        if not is_edit:
            return
        mouse_pos = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse_pos, val_rect):
            rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(70, 130, 200, 255))
            rl.set_mouse_cursor(rl.MOUSE_CURSOR_IBEAM)
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._begin_text_edit(prop_id, value, "string", on_commit)

    def _draw_bool_field(
        self,
        value: bool,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_toggle: Optional[CommitCallback] = None,
    ) -> None:
        del w
        check_rect = rl.Rectangle(x, y + 2, 14, 14)
        rl.draw_rectangle_rec(check_rect, rl.Color(42, 42, 42, 255))
        rl.draw_rectangle_lines_ex(check_rect, 1, rl.Color(80, 80, 80, 255))
        if value:
            inner = rl.Rectangle(x + 3, y + 5, 8, 8)
            rl.draw_rectangle_rec(inner, rl.Color(70, 130, 200, 255))

        if not is_edit:
            return
        mouse_pos = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse_pos, check_rect):
            rl.draw_rectangle_lines_ex(check_rect, 1, rl.Color(100, 150, 220, 255))
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if on_toggle is not None:
                    on_toggle(not value)
                else:
                    self._apply_property_change(world, prop_id, not value)

    def _draw_editing_field(
        self,
        prop_id: str,
        display_value: str,
        value_type: str,
        rect: rl.Rectangle,
        world: "World",
    ) -> None:
        rl.draw_rectangle_rec(rect, rl.Color(30, 30, 30, 255))
        rl.draw_rectangle_lines_ex(rect, 1, rl.Color(0, 200, 255, 255))

        current_text = self.text_buffer.decode("utf-8").rstrip("\x00")
        if not current_text and display_value and self.editing_text_field != prop_id:
            current_text = display_value
        rl.draw_text(f"{current_text}_", int(rect.x + 5), int(rect.y + 3), 10, rl.WHITE)

        key = rl.get_char_pressed()
        while key > 0:
            if 32 <= key <= 125 and len(current_text) < len(self.text_buffer) - 1:
                self.text_buffer[len(current_text)] = key
                current_text += chr(key)
            key = rl.get_char_pressed()

        if rl.is_key_pressed(rl.KEY_BACKSPACE) and current_text:
            self.text_buffer[len(current_text) - 1] = 0

        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self._commit_text_edit(world)
            self._clear_text_edit()
            return

        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            mouse_pos = rl.get_mouse_position()
            if not rl.check_collision_point_rec(mouse_pos, rect):
                self._commit_text_edit(world)
                self._clear_text_edit()

    def _draw_readonly_field(self, value: str, x: int, y: int, w: int, h: int) -> None:
        val_rect = rl.Rectangle(x, y, w, h)
        rl.draw_rectangle_rec(val_rect, rl.Color(36, 36, 36, 255))
        rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(52, 52, 52, 255))
        rl.draw_text(value, int(x + 5), int(y + 4), 10, rl.Color(140, 140, 140, 255))

    def _get_properties(self, component: Any) -> List[Tuple[str, Any]]:
        props: List[Tuple[str, Any]] = []
        if hasattr(component, "to_dict"):
            try:
                data = component.to_dict()
                for key in data.keys():
                    if hasattr(component, key):
                        value = getattr(component, key)
                        if isinstance(value, (bool, int, float, str)):
                            props.append((key, value))
                return props
            except Exception:
                pass

        for attr in dir(component):
            if attr.startswith("_") or callable(getattr(component, attr)):
                continue
            value = getattr(component, attr)
            if isinstance(value, (bool, int, float, str)):
                props.append((attr, value))
        return props

    def _draw_add_menu(self, world: "World", entity: Entity, x: int, y: int) -> None:
        all_components = self.registry.list_registered()
        available: List[str] = []
        for name in all_components:
            component_cls = self.registry.get(name)
            if component_cls is not None and not entity.has_component(component_cls):
                available.append(name)

        item_height = 24
        menu_w = 160
        menu_h = max(1, len(available)) * item_height
        if y + menu_h > rl.get_screen_height():
            y -= menu_h + 30

        menu_rect = rl.Rectangle(x, y, menu_w, menu_h)
        rl.draw_rectangle_rec(menu_rect, rl.Color(40, 40, 40, 255))
        rl.draw_rectangle_lines_ex(menu_rect, 1, rl.Color(80, 80, 80, 255))

        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if not rl.check_collision_point_rec(mouse, menu_rect):
                self.show_add_menu = False
                return

        for index, name in enumerate(available):
            rect = rl.Rectangle(x, y + index * item_height, menu_w, item_height)
            is_hover = rl.check_collision_point_rec(mouse, rect)
            if is_hover:
                rl.draw_rectangle_rec(rect, rl.Color(60, 60, 60, 255))
                if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                    self._add_component(world, entity.id, name)
                    self.show_add_menu = False
            rl.draw_text(name, int(x + 10), int(y + index * item_height + 6), 10, rl.Color(200, 200, 200, 255))

    def _draw_entity_property(
        self,
        label: str,
        value: Any,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        return self._draw_property(label, value, prop_id, x, y, width, is_edit, world)

    def _begin_text_edit(
        self,
        prop_id: str,
        value: Any,
        value_type: str,
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        self.editing_text_field = prop_id
        self.editing_value_type = value_type
        self._editing_commit = on_commit
        self.text_buffer[:] = b"\x00" * len(self.text_buffer)
        encoded = str(value).encode("utf-8")[: len(self.text_buffer) - 1]
        self.text_buffer[: len(encoded)] = encoded

    def _clear_text_edit(self) -> None:
        self.editing_text_field = None
        self.editing_value_type = "float"
        self._editing_commit = None
        self.text_buffer[:] = b"\x00" * len(self.text_buffer)

    def _apply_property_change(self, world: "World", prop_id: str, value: Any) -> bool:
        parts = prop_id.split(":")

        if parts[0] == "entity" and len(parts) >= 3:
            entity = world.get_entity(int(parts[1]))
            if entity is None:
                return False
            property_name = parts[2]
            if self._scene_manager is not None:
                return self._scene_manager.update_entity_property(entity.name, property_name, value)
            setattr(entity, property_name, value)
            return True

        if len(parts) < 3:
            return False

        entity = world.get_entity(int(parts[0]))
        if entity is None:
            return False
        return self._apply_component_property(world, entity.name, parts[1], parts[2], value)

    def _apply_component_property(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        if self._scene_manager is not None:
            return self._scene_manager.apply_edit_to_world(entity_name, component_name, property_name, value)

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        component = self._find_component(entity, component_name)
        if component is None:
            return False
        setattr(component, property_name, value)
        return True

    def _entity_name_from_id(self, world: "World", entity_id: int) -> Optional[str]:
        entity = world.get_entity(entity_id)
        return entity.name if entity is not None else None

    def _current_component_payload(self, world: "World", entity_name: str, component_name: str) -> Optional[Dict[str, Any]]:
        if self._scene_manager is not None and self._scene_manager.current_scene is not None:
            entity_data = self._scene_manager.current_scene.find_entity(entity_name)
            if entity_data is not None:
                components = entity_data.get("components", {})
                if component_name in components:
                    return copy.deepcopy(components[component_name])

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        component = self._find_component(entity, component_name)
        if component is None:
            return None
        if hasattr(component, "to_dict"):
            return copy.deepcopy(component.to_dict())

        payload: Dict[str, Any] = {}
        for attr in dir(component):
            if attr.startswith("_") or callable(getattr(component, attr)):
                continue
            value = getattr(component, attr)
            if isinstance(value, (bool, int, float, str, list, dict, type(None))):
                payload[attr] = copy.deepcopy(value)
        return payload

    def _find_component(self, entity: Entity, component_name: str) -> Optional[Component]:
        for component in entity.get_all_components():
            if type(component).__name__ == component_name:
                return component
        return None

    def _label_and_field_rect(self, label: str, x: int, y: int, width: int) -> Tuple[int, int, int]:
        row_height = self.LINE_HEIGHT
        padding = 5
        rl.gui_label(rl.Rectangle(x + padding, y, self.LABEL_WIDTH, row_height), label)
        field_x = x + self.LABEL_WIDTH + padding
        field_w = width - self.LABEL_WIDTH - (padding * 2)
        return field_x, field_w, row_height

    def _draw_text_row(
        self,
        label: str,
        value: str,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_text_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_commit=on_commit)
        return y + row_height

    def _draw_int_row(
        self,
        label: str,
        value: int,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_int_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_commit=on_commit)
        return y + row_height

    def _draw_float_row(
        self,
        label: str,
        value: float,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_float_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_commit=on_commit)
        return y + row_height

    def _draw_bool_row(
        self,
        label: str,
        value: bool,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_toggle: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_bool_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_toggle=on_toggle)
        return y + row_height

    def _draw_readonly_row(self, label: str, value: str, x: int, y: int, width: int) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_readonly_field(value, field_x, y + 1, field_w, row_height - 2)
        return y + row_height

    def _draw_action_row(
        self,
        label: str,
        button_text: str,
        x: int,
        y: int,
        width: int,
        enabled: bool,
        on_click: Callable[[], None],
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        button_rect = rl.Rectangle(field_x, y + 1, field_w, row_height - 2)
        button_label = button_text if enabled else f"{button_text} (missing asset)"
        if rl.gui_button(button_rect, button_label) and enabled:
            on_click()
        return y + row_height

    def _draw_section_title(self, title: str, x: int, y: int, width: int) -> int:
        rect = rl.Rectangle(x + 4, y, width - 8, self.LINE_HEIGHT)
        rl.draw_rectangle_rec(rect, rl.Color(44, 44, 44, 255))
        rl.draw_text(title, int(x + 10), int(y + 4), 10, rl.Color(200, 200, 200, 255))
        return y + self.LINE_HEIGHT

    def _draw_component_field(
        self,
        label: str,
        value: Any,
        entity_id: int,
        component_name: str,
        property_name: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        prop_id = f"{entity_id}:{component_name}:{property_name}"
        return self._draw_property(label, value, prop_id, x, y, width, is_edit, world)

    def _draw_nullable_float_row(
        self,
        label: str,
        value: Optional[float],
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: CommitCallback,
    ) -> int:
        display_value = "" if value is None else str(value)
        return self._draw_text_row(label, display_value, prop_id, x, y, width, is_edit, world, on_commit=on_commit)

    def _draw_transform_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "Transform", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("X", component.x, entity_id, "Transform", "x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Y", component.y, entity_id, "Transform", "y", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Rotation", component.rotation, entity_id, "Transform", "rotation", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Scale X", component.scale_x, entity_id, "Transform", "scale_x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Scale Y", component.scale_y, entity_id, "Transform", "scale_y", x, current_y, width, is_edit, world)
        return current_y

    def _draw_sprite_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "Sprite", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Texture", component.texture_path, entity_id, "Sprite", "texture_path", x, current_y, width, is_edit, world)
        current_y = self._draw_action_row("Editor", "Open Sprite Editor", x, current_y, width, bool(component.texture_path), lambda: self.open_sprite_editor(component.texture_path))
        current_y = self._draw_component_field("Width", component.width, entity_id, "Sprite", "width", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Height", component.height, entity_id, "Sprite", "height", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Origin X", component.origin_x, entity_id, "Sprite", "origin_x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Origin Y", component.origin_y, entity_id, "Sprite", "origin_y", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Flip X", component.flip_x, entity_id, "Sprite", "flip_x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Flip Y", component.flip_y, entity_id, "Sprite", "flip_y", x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        tint = list(component.tint) if component.tint else [255, 255, 255, 255]
        current_y = self._draw_section_title("Tint", x, current_y, width)
        for index, channel in enumerate(("R", "G", "B", "A")):
            prop_id = f"{entity_id}:Sprite:tint:{index}"

            def on_commit(new_value: Any, index: int = index, entity_name: Optional[str] = entity_name) -> bool:
                if entity_name is None:
                    return False

                def update(payload: Dict[str, Any]) -> None:
                    colors = list(payload.get("tint", [255, 255, 255, 255]))
                    while len(colors) < 4:
                        colors.append(255)
                    colors[index] = max(0, min(255, int(new_value)))
                    payload["tint"] = colors

                return self.update_component_payload(world, entity_name, "Sprite", update)

            current_y = self._draw_int_row(channel, int(tint[index]), prop_id, x, current_y, width, is_edit, world, on_commit=on_commit)
        return current_y

    def _draw_collider_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Width", "width"),
            ("Height", "height"),
            ("Offset X", "offset_x"),
            ("Offset Y", "offset_y"),
            ("Trigger", "is_trigger"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "Collider", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_rigidbody_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Velocity X", "velocity_x"),
            ("Velocity Y", "velocity_y"),
            ("Gravity", "gravity_scale"),
            ("Grounded", "is_grounded"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "RigidBody", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_animator_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "Animator", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Sprite Sheet", component.sprite_sheet, entity_id, "Animator", "sprite_sheet", x, current_y, width, is_edit, world)
        current_y = self._draw_action_row("Editor", "Open Sprite Editor", x, current_y, width, bool(component.sprite_sheet), lambda: self.open_sprite_editor(component.sprite_sheet))
        current_y = self._draw_component_field("Frame Width", component.frame_width, entity_id, "Animator", "frame_width", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Frame Height", component.frame_height, entity_id, "Animator", "frame_height", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Default", component.default_state, entity_id, "Animator", "default_state", x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Current", component.current_state, x, current_y, width)
        current_y = self._draw_readonly_row("Frame", str(component.current_frame), x, current_y, width)
        current_y = self._draw_readonly_row("Finished", str(component.is_finished), x, current_y, width)

        entity_name = self._entity_name_from_id(world, entity_id)
        current_y = self._draw_section_title("States", x, current_y, width)
        if entity_name is not None:
            add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
            if rl.gui_button(add_rect, "Add State"):
                self.update_component_payload(world, entity_name, "Animator", self._add_animator_state)
        current_y += self.LINE_HEIGHT

        animations = component.animations or {}
        for state_name, animation in animations.items():
            current_y = self._draw_animator_state_editor(component, entity_id, entity_name, state_name, animation, x, current_y, width, is_edit, world)
        return current_y

    def _draw_animator_state_editor(
        self,
        component: Any,
        entity_id: int,
        entity_name: Optional[str],
        state_name: str,
        animation: Any,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        del component
        current_y = self._draw_section_title(f"State: {state_name}", x, y, width)
        if entity_name is not None:
            field_x = x + self.LABEL_WIDTH + 5
            make_default_rect = rl.Rectangle(field_x, current_y + 1, 84, self.LINE_HEIGHT - 2)
            remove_rect = rl.Rectangle(field_x + 88, current_y + 1, 62, self.LINE_HEIGHT - 2)
            if rl.gui_button(make_default_rect, "Default"):
                self.update_component_payload(world, entity_name, "Animator", lambda payload, state_name=state_name: self._set_animator_default_state(payload, state_name))
            if rl.gui_button(remove_rect, "Remove"):
                self.update_component_payload(world, entity_name, "Animator", lambda payload, state_name=state_name: self._remove_animator_state(payload, state_name))
        current_y += self.LINE_HEIGHT

        if entity_name is None:
            return current_y

        def update_state(field_name: str, new_value: Any) -> bool:
            return self.update_component_payload(
                world,
                entity_name,
                "Animator",
                lambda payload, field_name=field_name, new_value=new_value, state_name=state_name: self._set_animator_state_field(payload, state_name, field_name, new_value),
            )

        current_y = self._draw_float_row("FPS", float(animation.fps), f"{entity_id}:Animator:{state_name}:fps", x, current_y, width, is_edit, world, on_commit=lambda value: update_state("fps", float(value)))
        current_y = self._draw_bool_row("Loop", bool(animation.loop), f"{entity_id}:Animator:{state_name}:loop", x, current_y, width, is_edit, world, on_toggle=lambda value: update_state("loop", bool(value)))
        current_y = self._draw_text_row("On Complete", animation.on_complete or "", f"{entity_id}:Animator:{state_name}:on_complete", x, current_y, width, is_edit, world, on_commit=lambda value: update_state("on_complete", value or None))

        current_y = self._draw_animator_list_editor(entity_id, entity_name, state_name, "slice_names", [str(item) for item in animation.slice_names], x, current_y, width, is_edit, world)
        current_y = self._draw_animator_list_editor(entity_id, entity_name, state_name, "frames", [int(item) for item in animation.frames], x, current_y, width, is_edit, world)
        return current_y

    def _draw_animator_list_editor(
        self,
        entity_id: int,
        entity_name: str,
        state_name: str,
        field_name: str,
        items: List[Any],
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        current_y = self._draw_section_title(field_name.replace("_", " ").title(), x, y, width)
        add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
        if rl.gui_button(add_rect, "Add Item"):
            default_value: Any = "" if field_name == "slice_names" else 0
            self.update_component_payload(
                world,
                entity_name,
                "Animator",
                lambda payload, state_name=state_name, field_name=field_name, default_value=default_value: self._append_animator_list_item(payload, state_name, field_name, default_value),
            )
        current_y += self.LINE_HEIGHT

        for index, item in enumerate(items):
            row_height = self.LINE_HEIGHT
            value_x = x + self.LABEL_WIDTH + 5
            label = f"#{index}"
            rl.gui_label(rl.Rectangle(x + 5, current_y, self.LABEL_WIDTH - 10, row_height), label)

            value_w = width - self.LABEL_WIDTH - 86
            prop_id = f"{entity_id}:Animator:{state_name}:{field_name}:{index}"

            def commit_value(new_value: Any, index: int = index) -> bool:
                cast_value = str(new_value) if field_name == "slice_names" else int(new_value)
                return self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index, cast_value=cast_value: self._set_animator_list_item(payload, state_name, field_name, index, cast_value),
                )

            if field_name == "slice_names":
                self._draw_text_field(str(item), prop_id, value_x, current_y, value_w, row_height, is_edit, world, on_commit=commit_value)
            else:
                self._draw_int_field(int(item), prop_id, value_x, current_y, value_w, row_height, is_edit, world, on_commit=commit_value)

            up_rect = rl.Rectangle(value_x + value_w + 2, current_y + 1, 24, row_height - 2)
            down_rect = rl.Rectangle(value_x + value_w + 28, current_y + 1, 24, row_height - 2)
            delete_rect = rl.Rectangle(value_x + value_w + 54, current_y + 1, 24, row_height - 2)
            if rl.gui_button(up_rect, "<") and index > 0:
                self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index: self._move_animator_list_item(payload, state_name, field_name, index, index - 1),
                )
            if rl.gui_button(down_rect, ">") and index < len(items) - 1:
                self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index: self._move_animator_list_item(payload, state_name, field_name, index, index + 1),
                )
            if rl.gui_button(delete_rect, "x"):
                self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index: self._remove_animator_list_item(payload, state_name, field_name, index),
                )
            current_y += row_height
        return current_y

    def _draw_camera2d_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Offset X", "offset_x"),
            ("Offset Y", "offset_y"),
            ("Zoom", "zoom"),
            ("Rotation", "rotation"),
            ("Primary", "is_primary"),
            ("Follow", "follow_entity"),
            ("Framing", "framing_mode"),
            ("Dead Zone W", "dead_zone_width"),
            ("Dead Zone H", "dead_zone_height"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "Camera2D", prop_name, x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        for label, prop_name in (
            ("Clamp Left", "clamp_left"),
            ("Clamp Right", "clamp_right"),
            ("Clamp Top", "clamp_top"),
            ("Clamp Bottom", "clamp_bottom"),
        ):
            prop_id = f"{entity_id}:Camera2D:{prop_name}"

            def on_commit(new_value: Any, prop_name: str = prop_name, entity_name: Optional[str] = entity_name) -> bool:
                if entity_name is None:
                    return False
                parsed = None if str(new_value).strip() == "" else float(new_value)
                return self.update_component_payload(
                    world,
                    entity_name,
                    "Camera2D",
                    lambda payload, prop_name=prop_name, parsed=parsed: payload.__setitem__(prop_name, parsed),
                )

            current_y = self._draw_nullable_float_row(label, getattr(component, prop_name), prop_id, x, current_y, width, is_edit, world, on_commit=on_commit)

        current_y = self._draw_component_field("Recenter", component.recenter_on_play, entity_id, "Camera2D", "recenter_on_play", x, current_y, width, is_edit, world)
        return current_y

    def _draw_audio_source_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Asset", "asset_path"),
            ("Volume", "volume"),
            ("Pitch", "pitch"),
            ("Loop", "loop"),
            ("Play Awake", "play_on_awake"),
            ("Spatial", "spatial_blend"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "AudioSource", prop_name, x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Playing", str(component.is_playing), x, current_y, width)
        return current_y

    def _draw_input_map_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Move Left", "move_left"),
            ("Move Right", "move_right"),
            ("Move Up", "move_up"),
            ("Move Down", "move_down"),
            ("Action 1", "action_1"),
            ("Action 2", "action_2"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "InputMap", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_player_controller_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Move Speed", "move_speed"),
            ("Jump Vel", "jump_velocity"),
            ("Air Control", "air_control"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "PlayerController2D", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_script_behaviour_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "ScriptBehaviour", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Module", component.module_path, entity_id, "ScriptBehaviour", "module_path", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Run In Edit", component.run_in_edit_mode, entity_id, "ScriptBehaviour", "run_in_edit_mode", x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        current_y = self._draw_section_title("Public Data", x, current_y, width)
        if entity_name is not None:
            add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
            if rl.gui_button(add_rect, "Add Entry"):
                self.update_component_payload(world, entity_name, "ScriptBehaviour", self._add_script_public_data_entry)
        current_y += self.LINE_HEIGHT

        public_data = dict(component.public_data or {})
        for key, value in public_data.items():
            current_y = self._draw_script_public_data_row(entity_id, entity_name, key, value, x, current_y, width, is_edit, world)
        return current_y

    def _draw_script_public_data_row(
        self,
        entity_id: int,
        entity_name: Optional[str],
        key: str,
        value: Any,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        row_height = self.LINE_HEIGHT
        key_x = x + 5
        key_w = self.LABEL_WIDTH + 10
        value_x = key_x + key_w + 4
        value_w = width - key_w - 42
        delete_x = value_x + value_w + 4

        key_prop_id = f"{entity_id}:ScriptBehaviour:key:{key}"
        value_prop_id = f"{entity_id}:ScriptBehaviour:value:{key}"

        def rename_key(new_key: Any) -> bool:
            if entity_name is None:
                return False
            target_key = str(new_key).strip()
            if not target_key:
                return False
            return self.update_component_payload(
                world,
                entity_name,
                "ScriptBehaviour",
                lambda payload, old_key=key, target_key=target_key: self._rename_script_public_data_key(payload, old_key, target_key),
            )

        self._draw_text_field(key, key_prop_id, key_x, y, key_w, row_height, is_edit, world, on_commit=rename_key)

        if entity_name is not None:
            if isinstance(value, bool):
                self._draw_bool_field(
                    value,
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_toggle=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, bool(new_value)),
                    ),
                )
            elif isinstance(value, int) and not isinstance(value, bool):
                self._draw_int_field(
                    int(value),
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_commit=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, int(new_value)),
                    ),
                )
            elif isinstance(value, float):
                self._draw_float_field(
                    float(value),
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_commit=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, float(new_value)),
                    ),
                )
            elif isinstance(value, str):
                self._draw_text_field(
                    value,
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_commit=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, str(new_value)),
                    ),
                )
            else:
                self._draw_readonly_field(str(value), value_x, y + 1, value_w, row_height - 2)

            delete_rect = rl.Rectangle(delete_x, y + 1, 24, row_height - 2)
            if rl.gui_button(delete_rect, "x"):
                self.update_component_payload(
                    world,
                    entity_name,
                    "ScriptBehaviour",
                    lambda payload, key=key: self._remove_script_public_data_key(payload, key),
                )
        return y + row_height

    def _add_animator_state(self, payload: Dict[str, Any]) -> None:
        animations = payload.setdefault("animations", {})
        suffix = 1
        while f"state_{suffix}" in animations:
            suffix += 1
        state_name = f"state_{suffix}"
        animations[state_name] = {
            "frames": [0],
            "slice_names": [],
            "fps": 8.0,
            "loop": True,
            "on_complete": None,
        }
        if not payload.get("default_state"):
            payload["default_state"] = state_name
        if not payload.get("current_state"):
            payload["current_state"] = state_name

    def _set_animator_default_state(self, payload: Dict[str, Any], state_name: str) -> None:
        payload["default_state"] = state_name
        if payload.get("current_state") not in payload.get("animations", {}):
            payload["current_state"] = state_name

    def _remove_animator_state(self, payload: Dict[str, Any], state_name: str) -> None:
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return
        del animations[state_name]
        if payload.get("default_state") == state_name:
            payload["default_state"] = next(iter(animations.keys()), "")
        if payload.get("current_state") == state_name:
            payload["current_state"] = payload.get("default_state", "")
        for animation in animations.values():
            if animation.get("on_complete") == state_name:
                animation["on_complete"] = None

    def _set_animator_state_field(self, payload: Dict[str, Any], state_name: str, field_name: str, value: Any) -> None:
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return
        animations[state_name][field_name] = value

    def _append_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, value: Any) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        items.append(value)
        state[field_name] = items

    def _set_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, index: int, value: Any) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        while len(items) <= index:
            items.append("" if field_name == "slice_names" else 0)
        items[index] = value
        state[field_name] = items

    def _move_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, from_index: int, to_index: int) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        if from_index < 0 or to_index < 0 or from_index >= len(items) or to_index >= len(items):
            return
        item = items.pop(from_index)
        items.insert(to_index, item)
        state[field_name] = items

    def _remove_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, index: int) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        if 0 <= index < len(items):
            del items[index]
        state[field_name] = items

    def _add_script_public_data_entry(self, payload: Dict[str, Any]) -> None:
        public_data = payload.setdefault("public_data", {})
        suffix = 1
        while f"key_{suffix}" in public_data:
            suffix += 1
        public_data[f"key_{suffix}"] = ""

    def _rename_script_public_data_key(self, payload: Dict[str, Any], old_key: str, new_key: str) -> None:
        public_data = payload.setdefault("public_data", {})
        if old_key not in public_data or (new_key != old_key and new_key in public_data):
            return
        value = public_data.pop(old_key)
        rebuilt: Dict[str, Any] = {}
        rebuilt[new_key] = value
        for existing_key, existing_value in public_data.items():
            rebuilt[existing_key] = existing_value
        payload["public_data"] = rebuilt

    def _set_script_public_data_value(self, payload: Dict[str, Any], key: str, value: Any) -> None:
        public_data = payload.setdefault("public_data", {})
        if key in public_data:
            public_data[key] = value

    def _remove_script_public_data_key(self, payload: Dict[str, Any], key: str) -> None:
        public_data = payload.setdefault("public_data", {})
        public_data.pop(key, None)

    def _remove_component(self, world: "World", entity_id: int, component_name: str) -> bool:
        entity = world.get_entity(entity_id)
        if entity is None:
            return False
        if self._scene_manager is not None:
            removed = self._scene_manager.remove_component_from_entity(entity.name, component_name)
            if removed:
                print(f"[INSPECTOR] Removed {component_name} from {entity.name}")
            return removed

        component = self._find_component(entity, component_name)
        if component is None:
            return False
        entity.remove_component(type(component))
        print(f"[INSPECTOR] Removed {component_name} from {entity.name}")
        return True

    def _add_component(self, world: "World", entity_id: int, component_name: str) -> bool:
        entity = world.get_entity(entity_id)
        if entity is None:
            return False
        if self._scene_manager is not None:
            added = self._scene_manager.add_component_to_entity(entity.name, component_name, {"enabled": True})
            if added:
                print(f"[INSPECTOR] Component {component_name} added to {entity.name}")
            return added

        new_component = self.registry.create(component_name, {"enabled": True})
        if new_component is None:
            return False
        entity.add_component(new_component)
        print(f"[INSPECTOR] Component {component_name} added to {entity.name}")
        return True
