from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


@dataclass(frozen=True)
class SceneStructuralAuthoringContext:
    get_active_entry: Callable[[], Optional[SceneWorkspaceEntry]]
    resolve_entry: Callable[[Optional[str]], Optional[SceneWorkspaceEntry]]
    flush_pending_edit_world: Callable[..., bool]
    rebuild_edit_world: Callable[[SceneWorkspaceEntry], None]
    record_scene_change: Callable[[SceneWorkspaceEntry, str, dict[str, Any]], None]
    sync_scene_links_from_feature_metadata: Callable[[SceneWorkspaceEntry], None]
    create_entity: Callable[[str, Optional[dict[str, dict[str, Any]]]], bool]
    create_entity_from_data: Callable[[dict[str, Any]], bool]
    update_entity_property: Callable[[str, str, Any], bool]
    unique_entity_name: Callable[[set[str], str], str]


@dataclass
class SceneHierarchyAuthoring:
    context: SceneStructuralAuthoringContext
    _clipboard: list[dict[str, Any]] = field(default_factory=list)
    _clipboard_root_name: str = ""

    def reset_state(self) -> None:
        self._clipboard.clear()
        self._clipboard_root_name = ""

    def remove_entity(self, entity_name: str) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.is_playing:
            return False
        self.context.flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())

        deleted_data = entry.scene.find_entity(entity_name)
        grandparent = deleted_data.get("parent") if deleted_data is not None else None
        for child_data in list(entry.scene.entities_data):
            if child_data.get("parent") != entity_name:
                continue
            child_name = child_data.get("name", "")
            child_world = self.compute_world_transform_from_scene_data(entry, child_name)
            child_data["parent"] = grandparent
            if child_world is None:
                continue
            cwx, cwy, cwr, cwsx, cwsy = child_world
            if grandparent is not None:
                gp_world = self.compute_world_transform_from_scene_data(entry, grandparent)
                if gp_world is not None:
                    gpx, gpy, gpr, gpsx, gpsy = gp_world
                    cwx -= gpx
                    cwy -= gpy
                    cwr -= gpr
                    cwsx = cwsx / gpsx if gpsx != 0 else cwsx
                    cwsy = cwsy / gpsy if gpsy != 0 else cwsy
            child_transform = child_data.get("components", {}).get("Transform")
            if child_transform is None:
                continue
            child_transform["x"] = cwx
            child_transform["y"] = cwy
            child_transform["rotation"] = cwr
            child_transform["scale_x"] = cwsx
            child_transform["scale_y"] = cwsy

        if not self.remove_single_entity(entry, entity_name):
            return False
        self.context.sync_scene_links_from_feature_metadata(entry)
        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"remove_entity:{entity_name}", before)
        return True

    def validate_parent(self, entry: SceneWorkspaceEntry, entity_name: str, parent_name: str) -> bool:
        if entity_name == parent_name:
            return False
        target = entry.scene.find_entity(entity_name)
        parent = entry.scene.find_entity(parent_name)
        if target is None or parent is None:
            return False
        visited = {entity_name}
        current: str | None = parent_name
        while current is not None:
            if current in visited:
                return False
            visited.add(current)
            current_entity = entry.scene.find_entity(current)
            current_parent = current_entity.get("parent") if current_entity is not None else None
            current = str(current_parent) if current_parent is not None else None
        return True

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.is_playing:
            return False
        if parent_name is not None and not self.validate_parent(entry, entity_name, parent_name):
            return False
        self.context.flush_pending_edit_world(entry)
        before = copy.deepcopy(entry.scene.to_dict())
        world_tx = self.compute_world_transform_from_scene_data(entry, entity_name)
        if world_tx is None:
            return self.context.update_entity_property(entity_name, "parent", parent_name)

        wx, wy, w_rot, w_sx, w_sy = world_tx
        if not entry.scene.update_entity_property(entity_name, "parent", parent_name):
            return False

        if parent_name is not None:
            parent_world = self.compute_world_transform_from_scene_data(entry, parent_name)
            if parent_world is not None:
                px, py, p_rot, p_sx, p_sy = parent_world
                new_local_x = wx - px
                new_local_y = wy - py
                new_local_rot = w_rot - p_rot
                new_local_sx = w_sx / p_sx if p_sx != 0 else w_sx
                new_local_sy = w_sy / p_sy if p_sy != 0 else w_sy
            else:
                new_local_x, new_local_y = wx, wy
                new_local_rot, new_local_sx, new_local_sy = w_rot, w_sx, w_sy
        else:
            new_local_x, new_local_y = wx, wy
            new_local_rot, new_local_sx, new_local_sy = w_rot, w_sx, w_sy

        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is not None:
            transform_data = entity_data.get("components", {}).get("Transform")
            if transform_data is not None:
                transform_data["x"] = new_local_x
                transform_data["y"] = new_local_y
                transform_data["rotation"] = new_local_rot
                transform_data["scale_x"] = new_local_sx
                transform_data["scale_y"] = new_local_sy

        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"reparent:{entity_name}", before)
        return True

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[dict[str, dict[str, Any]]] = None,
    ) -> bool:
        if not self.context.create_entity(name, components):
            return False
        return self.context.update_entity_property(name, "parent", parent_name)

    def duplicate_entity_subtree(self, entity_name: str, new_root_name: Optional[str] = None) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None:
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        new_root_name = new_root_name or f"{root.name}_copy"
        mapping = {root.name: new_root_name}
        for entity in subtree[1:]:
            suffix = entity.name[len(root.name):] if entity.name.startswith(root.name) else f"_{entity.name}"
            mapping[entity.name] = f"{new_root_name}{suffix}"
        for entity in subtree:
            payload = entity.to_dict()
            payload.pop("id", None)
            payload["name"] = mapping[entity.name]
            if payload.get("parent") in mapping:
                payload["parent"] = mapping[payload["parent"]]
            if payload.get("prefab_root_name") in mapping:
                payload["prefab_root_name"] = mapping[payload["prefab_root_name"]]
            entry.scene.add_entity(payload)
        self.context.sync_scene_links_from_feature_metadata(entry)
        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"duplicate_entity:{entity_name}", before)
        return True

    def copy_entity_subtree(self, entity_name: str) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None:
            return False
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        mapping = {entity.name: {key: value for key, value in entity.to_dict().items() if key != "id"} for entity in subtree}
        self._clipboard = [mapping[entity.name] for entity in subtree]
        self._clipboard_root_name = root.name
        return True

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        entry = self.context.resolve_entry(target_scene_key)
        if entry is None or entry.is_playing or not self._clipboard:
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        names_in_scene = {item.get("name", "") for item in entry.scene.entities_data}
        mapping: dict[str, str] = {}
        for payload in self._clipboard:
            original_name = str(payload.get("name", "") or "Entity")
            candidate = (
                original_name
                if original_name not in names_in_scene
                else self.context.unique_entity_name(names_in_scene, f"{original_name}_copy")
            )
            mapping[original_name] = candidate
            names_in_scene.add(candidate)
        for payload in self._clipboard:
            cloned = copy.deepcopy(payload)
            cloned["name"] = mapping[str(payload.get("name", ""))]
            if cloned.get("parent") in mapping:
                cloned["parent"] = mapping[str(cloned["parent"])]
            entry.scene.add_entity(cloned)
        self.context.sync_scene_links_from_feature_metadata(entry)
        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"paste_entity:{self._clipboard_root_name}", before)
        return True

    def remove_entity_subtree(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        entities = entry.scene.data.get("entities", [])
        names_to_remove = {entity_name}
        changed = True
        while changed:
            changed = False
            for entity_data in entities:
                child_name = entity_data.get("name")
                if entity_data.get("parent") not in names_to_remove or child_name in names_to_remove:
                    continue
                names_to_remove.add(child_name)
                changed = True
        before_count = len(entities)
        entry.scene.data["entities"] = [entity_data for entity_data in entities if entity_data.get("name") not in names_to_remove]
        changed = len(entry.scene.data["entities"]) != before_count
        if changed:
            entry.scene._rebuild_entity_index()
        return changed

    def compute_world_transform_from_scene_data(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[tuple[float, float, float, float, float]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return None
        transform = entity_data.get("components", {}).get("Transform")
        if transform is None:
            return None
        tx = float(transform.get("x", 0.0))
        ty = float(transform.get("y", 0.0))
        t_rot = float(transform.get("rotation", 0.0))
        t_sx = float(transform.get("scale_x", 1.0))
        t_sy = float(transform.get("scale_y", 1.0))
        parent_name = entity_data.get("parent")
        visited: set[str] = {entity_name}
        while parent_name is not None:
            if parent_name in visited:
                break
            visited.add(parent_name)
            parent_data = entry.scene.find_entity(parent_name)
            if parent_data is None:
                break
            parent_transform = parent_data.get("components", {}).get("Transform")
            if parent_transform is None:
                break
            tx += float(parent_transform.get("x", 0.0))
            ty += float(parent_transform.get("y", 0.0))
            t_rot += float(parent_transform.get("rotation", 0.0))
            t_sx *= float(parent_transform.get("scale_x", 1.0))
            t_sy *= float(parent_transform.get("scale_y", 1.0))
            parent_name = parent_data.get("parent")
        return tx, ty, t_rot, t_sx, t_sy

    def remove_single_entity(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        entities = entry.scene.data.get("entities", [])
        before_count = len(entities)
        entry.scene.data["entities"] = [entity_data for entity_data in entities if entity_data.get("name") != entity_name]
        changed = len(entry.scene.data["entities"]) != before_count
        if changed:
            entry.scene._rebuild_entity_index()
        return changed


@dataclass
class ScenePrefabAuthoring:
    context: SceneStructuralAuthoringContext
    hierarchy: SceneHierarchyAuthoring

    def create_prefab(
        self,
        entity_name: str,
        prefab_path: str,
        *,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
        prefab_locator: Optional[str] = None,
    ) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        self.context.flush_pending_edit_world(entry)

        from engine.assets.prefab import PrefabManager

        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None:
            return False
        root_instance_name = str(instance_name or entity_name or root.name)
        if replace_original and root_instance_name != entity_name and entry.scene.find_entity(root_instance_name) is not None:
            return False
        if not PrefabManager.save_prefab(root, prefab_path, world=entry.edit_world):
            return False
        if not replace_original:
            return True

        root_parent = root.parent_name
        root_prefab_name = root.prefab_instance.get("root_name") if root.prefab_instance else None
        before = copy.deepcopy(entry.scene.to_dict())

        if not self.hierarchy.remove_entity_subtree(entry, entity_name):
            return False

        payload = {
            "name": root_instance_name,
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "parent": root_parent,
            "prefab_instance": {
                "prefab_path": prefab_locator or prefab_path,
                "root_name": root_prefab_name or root.name,
                "overrides": {},
            },
            "components": {},
            "component_metadata": {},
        }
        if not entry.scene.add_entity(payload):
            return False

        self.context.sync_scene_links_from_feature_metadata(entry)
        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"create_prefab:{entity_name}", before)
        return True

    def instantiate_prefab(
        self,
        name: str,
        prefab_path: str,
        parent: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        root_name: Optional[str] = None,
    ) -> bool:
        return self.context.create_entity_from_data(
            {
                "name": name,
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "parent": parent,
                "prefab_instance": {
                    "prefab_path": prefab_path,
                    "root_name": root_name or name,
                    "overrides": copy.deepcopy(overrides or {}),
                },
                "components": {},
                "component_metadata": {},
            }
        )

    def unpack_prefab(self, entity_name: str) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None or root.prefab_instance is None:
            return False
        before = copy.deepcopy(entry.scene.to_dict())
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        explicit_entities = []
        for entity in subtree:
            payload = entity.to_dict()
            payload.pop("id", None)
            payload.pop("prefab_instance", None)
            payload.pop("prefab_source_path", None)
            payload.pop("prefab_root_name", None)
            explicit_entities.append(payload)
        if not self.hierarchy.remove_entity_subtree(entry, entity_name):
            return False
        for payload in explicit_entities:
            entry.scene.add_entity(payload)
        self.context.sync_scene_links_from_feature_metadata(entry)
        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"unpack_prefab:{entity_name}", before)
        return True

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        entry = self.context.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        from engine.assets.prefab import PrefabManager

        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None or root.prefab_instance is None:
            return False
        prefab_path = root.prefab_instance.get("prefab_path", "")
        resolved_path = (
            (Path(entry.scene.source_path).resolve().parent / prefab_path).resolve().as_posix()
            if entry.scene.source_path
            else prefab_path
        )
        before = copy.deepcopy(entry.scene.to_dict())
        if not PrefabManager.save_prefab(root, resolved_path, world=entry.edit_world):
            return False
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return False
        entity_data["prefab_instance"]["overrides"] = {}
        self.context.rebuild_edit_world(entry)
        entry.dirty = True
        self.context.record_scene_change(entry, f"apply_prefab_overrides:{entity_name}", before)
        return True

    def update_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        resolved = self._resolve_prefab_override_target(entry, entity_name)
        if resolved is None:
            return False
        root_scene_data, target_path = resolved
        overrides = self.ensure_prefab_override_ops(root_scene_data)
        self.upsert_prefab_override_operation(
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
        return True

    def update_prefab_entity_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        resolved = self._resolve_prefab_override_target(entry, entity_name)
        if resolved is None:
            return False
        root_scene_data, target_path = resolved
        overrides = self.ensure_prefab_override_ops(root_scene_data)
        self.upsert_prefab_override_operation(
            overrides,
            {
                "op": "set_entity_property",
                "target": target_path,
                "field": property_name,
                "value": copy.deepcopy(value),
            },
            match_keys=("op", "target", "field"),
        )
        return True

    def replace_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        resolved = self._resolve_prefab_override_target(entry, entity_name)
        if resolved is None:
            return False
        root_scene_data, target_path = resolved
        overrides = self.ensure_prefab_override_ops(root_scene_data)
        self.upsert_prefab_override_operation(
            overrides,
            {
                "op": "replace_component",
                "target": target_path,
                "component": component_name,
                "data": copy.deepcopy(component_data),
            },
            match_keys=("op", "target", "component"),
        )
        return True

    def remove_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> bool:
        resolved = self._resolve_prefab_override_target(entry, entity_name)
        if resolved is None:
            return False
        root_scene_data, target_path = resolved
        overrides = self.ensure_prefab_override_ops(root_scene_data)
        self.remove_prefab_override_operations(overrides, target=target_path, component=component_name)
        overrides.setdefault("operations", []).append(
            {
                "op": "remove_component",
                "target": target_path,
                "component": component_name,
            }
        )
        return True

    def ensure_prefab_override_ops(self, root_scene_data: dict[str, Any]) -> dict[str, Any]:
        prefab_instance = root_scene_data.setdefault("prefab_instance", {})
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

    def upsert_prefab_override_operation(
        self,
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

    def remove_prefab_override_operations(
        self,
        overrides: dict[str, Any],
        *,
        target: str,
        component: str | None = None,
    ) -> None:
        operations = overrides.setdefault("operations", [])
        filtered = []
        for operation in operations:
            if not isinstance(operation, dict):
                filtered.append(operation)
                continue
            if operation.get("target") != target:
                filtered.append(operation)
                continue
            if component is not None and operation.get("component") != component:
                filtered.append(operation)
                continue
        overrides["operations"] = filtered

    def _resolve_prefab_override_target(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[tuple[dict[str, Any], str]]:
        if entry.edit_world is None:
            return None
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None or entity.prefab_root_name is None:
            return None
        root_scene_data = entry.scene.find_entity(entity.prefab_root_name)
        if root_scene_data is None:
            root = entry.edit_world.get_entity_by_name(entity.prefab_root_name)
            root_id = getattr(root, "serialized_id", None) if root is not None else None
            if isinstance(root_id, str) and root_id.strip():
                root_scene_data = entry.scene.find_entity_by_id(root_id.strip())
        if root_scene_data is None or "prefab_instance" not in root_scene_data:
            return None
        return root_scene_data, str(entity.prefab_source_path or "")


class SceneStructuralAuthoring:
    def __init__(self, context: SceneStructuralAuthoringContext) -> None:
        self._hierarchy = SceneHierarchyAuthoring(context)
        self._prefabs = ScenePrefabAuthoring(context, self._hierarchy)

    def reset_state(self) -> None:
        self._hierarchy.reset_state()

    def remove_entity(self, entity_name: str) -> bool:
        return self._hierarchy.remove_entity(entity_name)

    def validate_parent(self, entry: SceneWorkspaceEntry, entity_name: str, parent_name: str) -> bool:
        return self._hierarchy.validate_parent(entry, entity_name, parent_name)

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        return self._hierarchy.set_entity_parent(entity_name, parent_name)

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[dict[str, dict[str, Any]]] = None,
    ) -> bool:
        return self._hierarchy.create_child_entity(parent_name, name, components)

    def duplicate_entity_subtree(self, entity_name: str, new_root_name: Optional[str] = None) -> bool:
        return self._hierarchy.duplicate_entity_subtree(entity_name, new_root_name)

    def copy_entity_subtree(self, entity_name: str) -> bool:
        return self._hierarchy.copy_entity_subtree(entity_name)

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        return self._hierarchy.paste_copied_entities(target_scene_key)

    def remove_entity_subtree(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        return self._hierarchy.remove_entity_subtree(entry, entity_name)

    def compute_world_transform_from_scene_data(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[tuple[float, float, float, float, float]]:
        return self._hierarchy.compute_world_transform_from_scene_data(entry, entity_name)

    def remove_single_entity(self, entry: SceneWorkspaceEntry, entity_name: str) -> bool:
        return self._hierarchy.remove_single_entity(entry, entity_name)

    def instantiate_prefab(
        self,
        name: str,
        prefab_path: str,
        parent: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        root_name: Optional[str] = None,
    ) -> bool:
        return self._prefabs.instantiate_prefab(name, prefab_path, parent, overrides, root_name)

    def create_prefab(
        self,
        entity_name: str,
        prefab_path: str,
        *,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
        prefab_locator: Optional[str] = None,
    ) -> bool:
        return self._prefabs.create_prefab(
            entity_name,
            prefab_path,
            replace_original=replace_original,
            instance_name=instance_name,
            prefab_locator=prefab_locator,
        )

    def unpack_prefab(self, entity_name: str) -> bool:
        return self._prefabs.unpack_prefab(entity_name)

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        return self._prefabs.apply_prefab_overrides(entity_name)

    def update_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._prefabs.update_prefab_component_override(entry, entity_name, component_name, property_name, value)

    def update_prefab_entity_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._prefabs.update_prefab_entity_override(entry, entity_name, property_name, value)

    def replace_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        return self._prefabs.replace_prefab_component_override(entry, entity_name, component_name, component_data)

    def remove_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> bool:
        return self._prefabs.remove_prefab_component_override(entry, entity_name, component_name)

    def ensure_prefab_override_ops(self, root_scene_data: dict[str, Any]) -> dict[str, Any]:
        return self._prefabs.ensure_prefab_override_ops(root_scene_data)

    def upsert_prefab_override_operation(
        self,
        overrides: dict[str, Any],
        operation: dict[str, Any],
        *,
        match_keys: tuple[str, ...],
    ) -> None:
        self._prefabs.upsert_prefab_override_operation(overrides, operation, match_keys=match_keys)

    def remove_prefab_override_operations(
        self,
        overrides: dict[str, Any],
        *,
        target: str,
        component: str | None = None,
    ) -> None:
        self._prefabs.remove_prefab_override_operations(overrides, target=target, component=component)
