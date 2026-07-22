from __future__ import annotations

import copy
from typing import Any

from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


class PrefabOverrideService:
    """Records serializable edits against expanded prefab instance targets."""

    def update_component_property(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        resolved = self._resolve_target(entry, entity_name)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._upsert_operation(
            overrides,
            {
                "op": "set_field",
                "target": target_path,
                "component": component_name,
                "field": property_name,
                "value": copy.deepcopy(value),
            },
            match_keys=("op", "target", "component", "field"),
        )
        return self._install_prefab_instance(
            entry,
            root_id,
            root_name,
            prefab_instance,
        )

    def update_entity_property(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        resolved = self._resolve_target(entry, entity_name)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._upsert_operation(
            overrides,
            {
                "op": "set_entity_property",
                "target": target_path,
                "field": property_name,
                "value": copy.deepcopy(value),
            },
            match_keys=("op", "target", "field"),
        )
        return self._install_prefab_instance(
            entry,
            root_id,
            root_name,
            prefab_instance,
        )

    def replace_component(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        resolved = self._resolve_target(entry, entity_name)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._upsert_operation(
            overrides,
            {
                "op": "replace_component",
                "target": target_path,
                "component": component_name,
                "data": copy.deepcopy(component_data),
            },
            match_keys=("op", "target", "component"),
        )
        return self._install_prefab_instance(
            entry,
            root_id,
            root_name,
            prefab_instance,
        )

    def remove_component(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> bool:
        resolved = self._resolve_target(entry, entity_name)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._remove_operations(
            overrides,
            target=target_path,
            component=component_name,
        )
        overrides.setdefault("operations", []).append(
            {
                "op": "remove_component",
                "target": target_path,
                "component": component_name,
            }
        )
        return self._install_prefab_instance(
            entry,
            root_id,
            root_name,
            prefab_instance,
        )

    def replace_component_by_id(
        self,
        entry: SceneWorkspaceEntry,
        entity_id: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        resolved = self._resolve_target_by_id(entry, entity_id)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._upsert_operation(
            overrides,
            {
                "op": "replace_component",
                "target": target_path,
                "target_id": entity_id,
                "component": component_name,
                "data": copy.deepcopy(component_data),
            },
            match_keys=("op", "target", "component"),
        )
        return self._install_prefab_instance(entry, root_id, root_name, prefab_instance)

    def update_component_property_by_id(
        self,
        entry: SceneWorkspaceEntry,
        entity_id: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        resolved = self._resolve_target_by_id(entry, entity_id)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._upsert_operation(
            overrides,
            {
                "op": "set_field",
                "target": target_path,
                "target_id": entity_id,
                "component": component_name,
                "field": property_name,
                "value": copy.deepcopy(value),
            },
            match_keys=("op", "target", "component", "field"),
        )
        return self._install_prefab_instance(entry, root_id, root_name, prefab_instance)

    def remove_component_by_id(
        self,
        entry: SceneWorkspaceEntry,
        entity_id: str,
        component_name: str,
    ) -> bool:
        resolved = self._resolve_target_by_id(entry, entity_id)
        if resolved is None:
            return False
        root_id, root_name, prefab_instance, target_path = resolved
        overrides = self._ensure_operations(prefab_instance)
        self._remove_operations(
            overrides,
            target=target_path,
            target_id=entity_id,
            component=component_name,
        )
        overrides.setdefault("operations", []).append(
            {
                "op": "remove_component",
                "target": target_path,
                "target_id": entity_id,
                "component": component_name,
            }
        )
        return self._install_prefab_instance(entry, root_id, root_name, prefab_instance)

    @staticmethod
    def _ensure_operations(prefab_instance: dict[str, Any]) -> dict[str, Any]:
        overrides = prefab_instance.setdefault("overrides", {})
        if "operations" in overrides:
            return overrides
        operations: list[dict[str, Any]] = []
        for target_path, payload in list(overrides.items()):
            if not isinstance(payload, dict):
                continue
            for field_name in ("active", "tag", "layer", "groups", "parent"):
                if field_name in payload:
                    operations.append(
                        {
                            "op": "set_entity_property",
                            "target": target_path,
                            "field": field_name,
                            "value": copy.deepcopy(payload[field_name]),
                        }
                    )
            components = payload.get("components", {})
            if not isinstance(components, dict):
                continue
            for component_name, component_payload in components.items():
                operations.append(
                    {
                        "op": "replace_component",
                        "target": target_path,
                        "component": component_name,
                        "data": copy.deepcopy(component_payload),
                    }
                )
        prefab_instance["overrides"] = {"operations": operations}
        return prefab_instance["overrides"]

    @staticmethod
    def _install_prefab_instance(
        entry: SceneWorkspaceEntry,
        root_id: str | None,
        root_name: str,
        prefab_instance: dict[str, Any],
    ) -> bool:
        try:
            if root_id is not None:
                return entry.scene.update_entity_property_by_id(
                    root_id,
                    "prefab_instance",
                    prefab_instance,
                )
            return entry.scene.update_entity_property(
                root_name,
                "prefab_instance",
                prefab_instance,
            )
        except Exception:
            return False

    @staticmethod
    def _upsert_operation(
        overrides: dict[str, Any],
        operation: dict[str, Any],
        *,
        match_keys: tuple[str, ...],
    ) -> None:
        operations = overrides.setdefault("operations", [])
        for index, existing in enumerate(operations):
            if not isinstance(existing, dict):
                continue
            if all(existing.get(key) == operation.get(key) for key in match_keys):
                operations[index] = operation
                return
        operations.append(operation)

    @staticmethod
    def _remove_operations(
        overrides: dict[str, Any],
        *,
        target: str,
        target_id: str | None = None,
        component: str | None = None,
    ) -> None:
        operations = overrides.setdefault("operations", [])
        filtered = []
        for operation in operations:
            if not isinstance(operation, dict):
                filtered.append(operation)
                continue
            if operation.get("target") != target and (
                target_id is None or operation.get("target_id") != target_id
            ):
                filtered.append(operation)
                continue
            if component is not None and operation.get("component") != component:
                filtered.append(operation)
                continue
        overrides["operations"] = filtered

    @staticmethod
    def _resolve_target(
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> tuple[str | None, str, dict[str, Any], str] | None:
        if entry.edit_world is None:
            return None
        entity = entry.edit_world.get_entity_by_name(entity_name)
        return PrefabOverrideService._resolve_target_for_entity(entry, entity)

    @staticmethod
    def _resolve_target_by_id(
        entry: SceneWorkspaceEntry,
        entity_id: str,
    ) -> tuple[str | None, str, dict[str, Any], str] | None:
        if entry.edit_world is None:
            return None
        entity = entry.edit_world.get_entity_by_serialized_id(entity_id)
        return PrefabOverrideService._resolve_target_for_entity(entry, entity)

    @staticmethod
    def _resolve_target_for_entity(
        entry: SceneWorkspaceEntry,
        entity: Any,
    ) -> tuple[str | None, str, dict[str, Any], str] | None:
        if entity is None or entity.prefab_root_name is None:
            return None
        root_scene_data = entry.scene.find_entity(entity.prefab_root_name)
        if root_scene_data is None:
            root = entry.edit_world.get_entity_by_name(entity.prefab_root_name)
            root_id = getattr(root, "serialized_id", None) if root is not None else None
            if isinstance(root_id, str) and root_id.strip():
                root_scene_data = entry.scene.find_entity_by_id(root_id.strip())
        if root_scene_data is None:
            return None
        prefab_instance = root_scene_data.get("prefab_instance")
        root_name = root_scene_data.get("name")
        if not isinstance(prefab_instance, dict) or not isinstance(root_name, str):
            return None
        raw_root_id = root_scene_data.get("id")
        root_id = raw_root_id.strip() if isinstance(raw_root_id, str) and raw_root_id.strip() else None
        return (
            root_id,
            root_name,
            copy.deepcopy(prefab_instance),
            str(entity.prefab_source_path or ""),
        )
