"""Editor-only inspector panel renderer backed by serializable authoring commits."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias, cast, runtime_checkable

import pyray as rl
from engine.editor.ui.inspector import InspectorModel, build_inspector_model_from_dict
from engine.editor.ui.property_widgets import PropertyDescriptor, PropertyKind

PrimitiveValue: TypeAlias = str | int | float | bool | None
SerializableValue: TypeAlias = PrimitiveValue | tuple[object, ...] | list[object] | dict[str, object]
ComponentPayload: TypeAlias = dict[str, SerializableValue]
EntityPayload: TypeAlias = dict[str, object]


@runtime_checkable
class SceneManagerLike(Protocol):
    def update_entity_property(self, entity_name: str, property_name: str, value: object) -> bool: ...

    def apply_edit_to_world(self, entity_name: str, component_name: str, property_name: str, value: object) -> bool: ...


@runtime_checkable
class EngineAPILike(Protocol):
    def get_entity(self, name: str) -> Mapping[str, object]: ...

    def edit_component(self, entity_name: str, component: str, property: str, value: object) -> Mapping[str, object]: ...

    def replace_component_data(self, entity_name: str, component_name: str, data: dict[str, object]) -> Mapping[str, object]: ...


class EntityLike(Protocol):
    name: object
    id: object
    active: object
    tag: object
    layer: object

    def iter_components(self) -> object: ...


class WorldLike(Protocol):
    selected_entity_name: str | None

    def get_entity_by_name(self, name: str) -> object | None: ...


class ComponentLike(Protocol):
    def to_dict(self) -> object: ...


@dataclass(frozen=True)
class InspectorWidgetRect:
    key: str
    group_name: str
    prop_name: str
    x: float
    y: float
    width: float
    height: float
    kind: PropertyKind


class InspectorPanel:
    """Small pure-data inspector view for tests and optional editor rendering."""

    HEADER_HEIGHT = 22
    ROW_HEIGHT = 20
    MARGIN = 8
    LABEL_WIDTH = 92

    def __init__(self, scene_manager: SceneManagerLike | None = None, engine_api: EngineAPILike | None = None) -> None:
        self._scene_manager = scene_manager
        self._engine_api = engine_api
        self.entity_name: str = ""
        self.model: InspectorModel = InspectorModel()
        self.widget_rects: list[InspectorWidgetRect] = []
        self.last_error: str | None = None
        self.editing_key: str | None = None
        self.editing_group: str = ""
        self.editing_prop: str = ""
        self.editing_kind: PropertyKind | None = None
        self.text_buffer: str = ""

    def set_scene_manager(self, scene_manager: SceneManagerLike | None) -> None:
        self._scene_manager = scene_manager

    def set_engine_api(self, engine_api: EngineAPILike | None) -> None:
        self._engine_api = engine_api

    def build_model(
        self,
        world: WorldLike | dict[str, object],
        entity_name: str | None = None,
        selection: str | None = None,
    ) -> InspectorModel:
        selected_name = str(entity_name or selection or getattr(world, "selected_entity_name", "") or "").strip()
        self.entity_name = selected_name
        if not selected_name:
            self.model = InspectorModel()
            return self.model

        entity = self._resolve_entity(world, selected_name)
        if entity is None:
            self.model = InspectorModel()
            return self.model

        self.model = build_inspector_model_from_dict(self._entity_to_dict(entity))
        return self.model

    def render(
        self,
        world: WorldLike | dict[str, object],
        x: int,
        y: int,
        width: int,
        height: int,
        is_edit_mode: bool = True,
        entity_name: str | None = None,
        selection: str | None = None,
    ) -> None:
        del is_edit_mode
        model = self.build_model(world, entity_name=entity_name, selection=selection)
        self.widget_rects = []

        self._draw_panel(x, y, width, height)
        content_y = y + self.HEADER_HEIGHT + self.MARGIN
        if not model.groups:
            self._draw_text("No selection", x + self.MARGIN, content_y, 10, self._color(140, 140, 140, 255))
            return

        for group in model.groups:
            if content_y + self.ROW_HEIGHT > y + height:
                break
            self._draw_group_header(group.name, x + self.MARGIN, content_y, width - self.MARGIN * 2)
            content_y += self.ROW_HEIGHT
            for prop in group.properties:
                if content_y + self.ROW_HEIGHT > y + height:
                    break
                rect = self._register_widget_rect(group.name, prop, x, content_y, width)
                self._draw_property_row(prop, rect)
                content_y += self.ROW_HEIGHT
            content_y += 4

    def toggle_bool(self, group_name: str, prop_name: str) -> bool:
        prop = self.model.find_property(group_name, prop_name)
        if prop is None or prop.kind is not PropertyKind.BOOL:
            return False
        return self.commit_property(group_name, prop_name, not bool(prop.value))

    def begin_text_edit(self, group_name: str, prop_name: str) -> bool:
        prop = self.model.find_property(group_name, prop_name)
        if prop is None or prop.kind not in {PropertyKind.INT, PropertyKind.FLOAT, PropertyKind.STR}:
            return False
        self.editing_group = group_name
        self.editing_prop = prop_name
        self.editing_kind = prop.kind
        self.editing_key = self._widget_key(group_name, prop_name)
        self.text_buffer = str(prop.value)
        return True

    def set_text_buffer(self, value: str) -> None:
        self.text_buffer = str(value)

    def commit_text_edit(self) -> bool:
        if self.editing_key is None or self.editing_kind is None:
            return False
        try:
            value = self._parse_text_value(self.text_buffer, self.editing_kind)
        except (TypeError, ValueError) as exc:
            self.last_error = str(exc)
            return False
        success = self.commit_property(self.editing_group, self.editing_prop, value)
        if success:
            self.cancel_text_edit()
        return success

    def cancel_text_edit(self) -> None:
        self.editing_key = None
        self.editing_group = ""
        self.editing_prop = ""
        self.editing_kind = None
        self.text_buffer = ""

    def handle_key(self, key: int) -> bool:
        if key == getattr(rl, "KEY_ESCAPE", 256):
            self.cancel_text_edit()
            return True
        if key in {getattr(rl, "KEY_ENTER", 257), getattr(rl, "KEY_KP_ENTER", 335)}:
            return self.commit_text_edit()
        return False

    def commit_property(self, group_name: str, prop_name: str, value: object) -> bool:
        self.last_error = None
        if not self.entity_name:
            self.last_error = "No selection"
            return False
        if self._scene_manager is None and self._engine_api is None:
            self.last_error = "No SceneManager or EngineAPI configured"
            return False

        try:
            if self._scene_manager is not None:
                if group_name == "Entity":
                    return bool(self._scene_manager.update_entity_property(self.entity_name, prop_name, value))
                return bool(self._scene_manager.apply_edit_to_world(self.entity_name, group_name, prop_name, value))
            if self._engine_api is not None and group_name != "Entity":
                return self._action_result_success(
                    self._engine_api.edit_component(self.entity_name, group_name, prop_name, value)
                )
        except Exception as exc:  # pragma: no cover - defensive, deterministic failure.
            self.last_error = str(exc)
            return False

        self.last_error = "Authoring API does not support inspector commit"
        return False

    def _register_widget_rect(
        self,
        group_name: str,
        prop: PropertyDescriptor,
        panel_x: int,
        row_y: int,
        panel_w: int,
    ) -> InspectorWidgetRect:
        value_x = panel_x + self.MARGIN + self.LABEL_WIDTH
        rect = InspectorWidgetRect(
            self._widget_key(group_name, prop.name),
            group_name,
            prop.name,
            float(value_x),
            float(row_y + 2),
            float(max(0, panel_w - self.MARGIN * 2 - self.LABEL_WIDTH)),
            float(self.ROW_HEIGHT - 4),
            prop.kind,
        )
        self.widget_rects.append(rect)
        return rect

    def _draw_panel(self, x: int, y: int, width: int, height: int) -> None:
        self._draw_rectangle(x, y, width, height, self._color(30, 30, 30, 255))
        self._draw_rectangle(x, y, width, self.HEADER_HEIGHT, self._color(56, 56, 56, 255))
        self._draw_text("Inspector", x + self.MARGIN, y + 6, 10, self._color(220, 220, 220, 255))

    def _draw_group_header(self, title: str, x: int, y: int, width: int) -> None:
        self._draw_rectangle(x, y, width, self.ROW_HEIGHT - 2, self._color(48, 48, 48, 255))
        self._draw_text(title, x + 5, y + 5, 10, self._color(220, 220, 220, 255))

    def _draw_property_row(self, prop: PropertyDescriptor, rect: InspectorWidgetRect) -> None:
        label_x = int(rect.x - self.LABEL_WIDTH)
        self._draw_text(prop.display_name, label_x, int(rect.y + 3), 10, self._color(180, 180, 180, 255))
        if prop.kind is PropertyKind.BOOL:
            self._draw_bool(prop, rect)
            return
        self._draw_text_value(prop, rect)

    def _draw_bool(self, prop: PropertyDescriptor, rect: InspectorWidgetRect) -> None:
        self._draw_rectangle(int(rect.x), int(rect.y), 14, 14, self._color(42, 42, 42, 255))
        if bool(prop.value):
            self._draw_rectangle(int(rect.x + 3), int(rect.y + 3), 8, 8, self._color(70, 130, 200, 255))

    def _draw_text_value(self, prop: PropertyDescriptor, rect: InspectorWidgetRect) -> None:
        self._draw_rectangle(int(rect.x), int(rect.y), int(rect.width), int(rect.height), self._color(42, 42, 42, 255))
        if prop.kind in {PropertyKind.DICT, PropertyKind.LIST, PropertyKind.COLOR, PropertyKind.VECTOR2, PropertyKind.VECTOR3}:
            value = str(prop.value)
        else:
            value = self.text_buffer if self.editing_key == rect.key else str(prop.value)
        self._draw_text(value, int(rect.x + 5), int(rect.y + 3), 10, self._color(200, 200, 200, 255))

    def _resolve_entity(self, world: WorldLike | dict[str, object], entity_name: str) -> object | None:
        if isinstance(world, dict):
            entities = world.get("entities", {})
            if isinstance(entities, dict):
                return entities.get(entity_name)
        getter = getattr(world, "get_entity_by_name", None)
        if callable(getter):
            return getter(entity_name)
        return None

    def _entity_to_dict(self, entity: object) -> EntityPayload:
        if isinstance(entity, dict):
            return dict(entity)
        entity_like = cast(EntityLike, entity)
        components_data: dict[str, object] = {}
        data: EntityPayload = {
            "name": getattr(entity, "name", self.entity_name),
            "id": getattr(entity, "id", ""),
            "active": getattr(entity, "active", True),
            "tag": getattr(entity, "tag", ""),
            "layer": getattr(entity, "layer", 0),
            "components": components_data,
        }
        iterator = getattr(entity_like, "iter_components", None)
        components = iterator() if callable(iterator) else getattr(entity, "components", [])
        if isinstance(components, dict):
            items: Iterable[tuple[object, object]] = components.items()
        else:
            items = ((type(component).__name__, component) for component in components or [])
        for name, component in items:
            components_data[str(name)] = self._component_to_dict(component)
        return data

    def _component_to_dict(self, component: object) -> ComponentPayload:
        if isinstance(component, dict):
            return dict(component)
        component_like = cast(ComponentLike, component)
        to_dict = getattr(component_like, "to_dict", None)
        if callable(to_dict):
            value = to_dict()
            if isinstance(value, dict):
                return dict(value)
        return {
            key: value
            for key in dir(component)
            if not key.startswith("_")
            for value in [getattr(component, key)]
            if not callable(value) and isinstance(value, (bool, int, float, str, tuple, list, dict))
        }

    def _can_draw(self) -> bool:
        is_ready = getattr(rl, "is_window_ready", None)
        return not callable(is_ready) or bool(is_ready())

    def _parse_text_value(self, text: str, kind: PropertyKind) -> object:
        if kind is PropertyKind.INT:
            return int(float(text)) if text else 0
        if kind is PropertyKind.FLOAT:
            return float(text) if text else 0.0
        return text

    def _action_result_success(self, result: Mapping[str, object]) -> bool:
        return bool(result.get("success", False))

    def _widget_key(self, group_name: str, prop_name: str) -> str:
        return f"{group_name}:{prop_name}"

    def _color(self, r: int, g: int, b: int, a: int) -> object:
        return rl.Color(r, g, b, a)

    def _draw_rectangle(self, x: int, y: int, width: int, height: int, color: object) -> None:
        if not self._can_draw():
            return
        draw = getattr(rl, "draw_rectangle", None)
        if callable(draw):
            draw(x, y, width, height, color)

    def _draw_text(self, text: str, x: int, y: int, size: int, color: object) -> None:
        if not self._can_draw():
            return
        draw = getattr(rl, "draw_text", None)
        if callable(draw):
            draw(text, x, y, size, color)
