"""Pure property editing data model for editor inspector widgets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from engine.editor.ui_core.protocols import PropertyValue


class PropertyKind(Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    COLOR = "color"
    VECTOR2 = "vector2"
    VECTOR3 = "vector3"
    DICT = "dict"
    LIST = "list"
    ASSET = "asset"


def _display_name_from_name(name: str) -> str:
    return name.replace("_", " ").strip().title() or name


@dataclass
class PropertyDescriptor:
    name: str
    kind: PropertyKind
    display_name: str = ""
    value: PropertyValue | object = None
    read_only: bool = False
    tooltip: str = ""

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = _display_name_from_name(self.name)


@dataclass
class PropertyEditResult:
    group_name: str
    prop_name: str
    success: bool
    error: str | None = None
    old_value: PropertyValue | object = None
    new_value: PropertyValue | object = None


CommitContract = Callable[[str, str, PropertyValue | object, PropertyValue | object], PropertyEditResult | bool | None]


class EditTransaction:
    """Tracks staged property edits and commits them atomically per property."""

    def __init__(self, values: dict[str, dict[str, PropertyValue | object]] | None = None) -> None:
        self._values: dict[str, dict[str, PropertyValue | object]] = {
            group: dict(props) for group, props in (values or {}).items()
        }
        self._dirty: dict[str, dict[str, PropertyValue | object]] = {}
        self._originals: dict[str, dict[str, PropertyValue | object]] = {}
        self._commit_callback: CommitContract | None = None

    def set_commit_callback(self, callback: CommitContract | None) -> None:
        self._commit_callback = callback

    def set_value(self, group_name: str, prop_name: str, value: PropertyValue | object) -> None:
        original = self._original_value(group_name, prop_name)
        if value == original:
            self._clear_dirty_property(group_name, prop_name)
            return
        if group_name not in self._originals or prop_name not in self._originals[group_name]:
            self._originals.setdefault(group_name, {})[prop_name] = original
        self._dirty.setdefault(group_name, {})[prop_name] = value

    def get_value(
        self,
        group_name: str,
        prop_name: str,
        default: PropertyValue | object = None,
    ) -> PropertyValue | object:
        if group_name in self._dirty and prop_name in self._dirty[group_name]:
            return self._dirty[group_name][prop_name]
        return self._values.get(group_name, {}).get(prop_name, default)

    def is_dirty(self, group_name: str | None = None, prop_name: str | None = None) -> bool:
        if group_name is None:
            return any(self._dirty.values())
        if prop_name is None:
            return bool(self._dirty.get(group_name))
        return prop_name in self._dirty.get(group_name, {})

    def dirty_groups(self) -> list[str]:
        return [group for group, props in self._dirty.items() if props]

    def dirty_properties(self, group_name: str | None = None) -> list[str] | list[tuple[str, str]]:
        if group_name is not None:
            return list(self._dirty.get(group_name, {}))
        return [(group, prop) for group, props in self._dirty.items() for prop in props]

    def commit(self) -> list[PropertyEditResult]:
        if not self.is_dirty():
            return []

        results: list[PropertyEditResult] = []
        for group_name, prop_name, old_value, new_value in self._iter_dirty_snapshot():
            if self._commit_callback is None:
                result = PropertyEditResult(
                    group_name,
                    prop_name,
                    False,
                    error="No commit callback configured",
                    old_value=old_value,
                    new_value=new_value,
                )
            else:
                result = self._call_commit_callback(group_name, prop_name, old_value, new_value)
            results.append(result)

            if result.success:
                self._values.setdefault(group_name, {})[prop_name] = new_value
                self._clear_dirty_property(group_name, prop_name)

        return results

    def rollback(self) -> None:
        self._dirty.clear()
        self._originals.clear()

    def _original_value(self, group_name: str, prop_name: str) -> PropertyValue | object:
        if group_name in self._originals and prop_name in self._originals[group_name]:
            return self._originals[group_name][prop_name]
        return self._values.get(group_name, {}).get(prop_name)

    def _iter_dirty_snapshot(self) -> list[tuple[str, str, PropertyValue | object, PropertyValue | object]]:
        return [
            (group, prop, self._originals.get(group, {}).get(prop), value)
            for group, props in self._dirty.items()
            for prop, value in props.items()
        ]

    def _call_commit_callback(
        self,
        group_name: str,
        prop_name: str,
        old_value: PropertyValue | object,
        new_value: PropertyValue | object,
    ) -> PropertyEditResult:
        callback = self._commit_callback
        assert callback is not None
        try:
            raw_result = callback(group_name, prop_name, old_value, new_value)
        except Exception as exc:  # pragma: no cover - defensive path still deterministic.
            return PropertyEditResult(group_name, prop_name, False, str(exc), old_value, new_value)

        if isinstance(raw_result, PropertyEditResult):
            if raw_result.old_value is None:
                raw_result.old_value = old_value
            if raw_result.new_value is None:
                raw_result.new_value = new_value
            return raw_result
        return PropertyEditResult(
            group_name,
            prop_name,
            bool(raw_result is None or raw_result),
            None if raw_result is None or raw_result else "Commit rejected",
            old_value,
            new_value,
        )

    def _clear_dirty_property(self, group_name: str, prop_name: str) -> None:
        if group_name in self._dirty:
            self._dirty[group_name].pop(prop_name, None)
            if not self._dirty[group_name]:
                self._dirty.pop(group_name, None)
        if group_name in self._originals:
            self._originals[group_name].pop(prop_name, None)
            if not self._originals[group_name]:
                self._originals.pop(group_name, None)
