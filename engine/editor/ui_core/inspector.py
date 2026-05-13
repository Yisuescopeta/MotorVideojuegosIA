"""Pure inspector data model builders for editor UI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from engine.editor.ui_core.property_widgets import PropertyDescriptor, PropertyKind
from engine.editor.ui_core.protocols import PropertyValue


@dataclass
class InspectorGroup:
    """Named group of editable property descriptors for inspector panels."""

    name: str
    properties: list[PropertyDescriptor] = field(default_factory=list)
    removable: bool = True

    def find_property(self, prop_name: str) -> PropertyDescriptor | None:
        return next((prop for prop in self.properties if prop.name == prop_name), None)


@dataclass
class InspectorModel:
    """Pure inspector snapshot split into serializable property groups."""

    groups: list[InspectorGroup] = field(default_factory=list)

    def find_group(self, group_name: str) -> InspectorGroup | None:
        return next((group for group in self.groups if group.name == group_name), None)

    def find_property(self, group_name: str, prop_name: str) -> PropertyDescriptor | None:
        group = self.find_group(group_name)
        if group is None:
            return None
        return group.find_property(prop_name)


def infer_property_kind(value: PropertyValue | object) -> PropertyKind | None:
    """Return editor widget kind for supported JSON-like property values."""

    if isinstance(value, bool):
        return PropertyKind.BOOL
    if isinstance(value, int):
        return PropertyKind.INT
    if isinstance(value, float):
        return PropertyKind.FLOAT
    if isinstance(value, str):
        return PropertyKind.STR
    if isinstance(value, tuple) and _is_numeric_sequence(value):
        return _numeric_sequence_kind(value)
    if isinstance(value, dict):
        return PropertyKind.DICT
    if isinstance(value, list):
        if _is_numeric_sequence(value):
            vector_kind = _numeric_sequence_kind(value)
            if vector_kind is not None:
                return vector_kind
        return PropertyKind.LIST
    return None


def build_inspector_model_from_dict(entity_data: dict[str, PropertyValue | object]) -> InspectorModel:
    """Build pure inspector model from dict-shaped entity data."""

    groups: list[InspectorGroup] = []
    entity_props = _descriptors_from_mapping(
        {
            key: entity_data[key]
            for key in ("name", "id", "active", "tag", "layer")
            if key in entity_data
        }
    )
    if entity_props:
        groups.append(InspectorGroup("Entity", entity_props, removable=False))

    components = entity_data.get("components", {})
    if isinstance(components, dict):
        for component_name, component_data in components.items():
            if not isinstance(component_data, dict):
                continue
            props = _descriptors_from_mapping(component_data)
            if props:
                groups.append(
                    InspectorGroup(
                        str(component_name),
                        props,
                        removable=str(component_name) != "Transform",
                    )
                )

    return InspectorModel(groups)


def _descriptors_from_mapping(values: dict[str, PropertyValue | object]) -> list[PropertyDescriptor]:
    descriptors: list[PropertyDescriptor] = []
    for name, value in values.items():
        kind = infer_property_kind(value)
        if kind is None:
            continue
        descriptors.append(PropertyDescriptor(str(name), kind, value=value))
    return descriptors


def _is_numeric_sequence(value: Sequence[object]) -> bool:
    return len(value) in (2, 3, 4) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _numeric_sequence_kind(value: Sequence[object]) -> PropertyKind | None:
    if len(value) == 4:
        return PropertyKind.COLOR
    if len(value) == 2:
        return PropertyKind.VECTOR2
    if len(value) == 3:
        return PropertyKind.VECTOR3
    return None
