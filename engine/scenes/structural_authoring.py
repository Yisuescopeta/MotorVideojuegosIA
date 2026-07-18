from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from engine.scenes.contracts import (
    PrefabOverridePort,
    SceneSerializableEntityPort,
    SceneSerializableTransactionPort,
)
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


@dataclass
class SceneHierarchyAuthoring:
    workspace: SceneWorkspace
    pipeline: SceneSerializableTransactionPort
    serializable_entities: SceneSerializableEntityPort
    _clipboard: list[dict[str, Any]] = field(default_factory=list)
    _clipboard_root_name: str = ""

    def reset_state(self) -> None:
        self._clipboard.clear()
        self._clipboard_root_name = ""

    def remove_entity(self, entity_name: str) -> bool:
        entry = self.workspace.get_active_entry()
        if entry is None or entry.is_playing:
            return False
        label = f"remove_entity:{entity_name}"
        transaction = self.pipeline.begin(
            entry,
            failure_context=label,
            clone_world=True,
        )
        if transaction is None:
            return False
        token, before = transaction
        try:
            deleted_data = entry.scene.find_entity(entity_name)
            if deleted_data is None:
                self.pipeline.rollback(entry, token)
                return False
            grandparent = deleted_data.get("parent")
            child_updates: list[tuple[str, dict[str, float] | None]] = []
            for child_data in entry.scene.entities_data:
                if not isinstance(child_data, dict) or child_data.get("parent") != entity_name:
                    continue
                child_name = str(child_data.get("name", ""))
                child_world = self.compute_world_transform_from_scene_data(entry, child_name)
                transform_update: dict[str, float] | None = None
                if child_world is not None:
                    cwx, cwy, cwr, cwsx, cwsy = child_world
                    if isinstance(grandparent, str):
                        gp_world = self.compute_world_transform_from_scene_data(entry, grandparent)
                        if gp_world is not None:
                            gpx, gpy, gpr, gpsx, gpsy = gp_world
                            cwx -= gpx
                            cwy -= gpy
                            cwr -= gpr
                            cwsx = cwsx / gpsx if gpsx != 0 else cwsx
                            cwsy = cwsy / gpsy if gpsy != 0 else cwsy
                    transform_update = {
                        "x": cwx,
                        "y": cwy,
                        "rotation": cwr,
                        "scale_x": cwsx,
                        "scale_y": cwsy,
                    }
                child_updates.append((child_name, transform_update))
            for child_name, transform_update in child_updates:
                if not entry.scene.update_entity_property(child_name, "parent", grandparent):
                    self.pipeline.rollback(entry, token)
                    return False
                if transform_update is not None and not entry.scene.update_component_properties(
                    child_name,
                    "Transform",
                    transform_update,
                ):
                    self.pipeline.rollback(entry, token)
                    return False
            if not entry.scene.remove_entity(entity_name):
                self.pipeline.rollback(entry, token)
                return False
            self.workspace.sync_feature_metadata_from_scene_links(entry)
        except Exception:
            self.pipeline.rollback(entry, token)
            raise
        return self.pipeline.commit_snapshot(entry, token, before, label=label)

    @staticmethod
    def validate_parent(
        entry: SceneWorkspaceEntry,
        entity_name: str,
        parent_name: str,
    ) -> bool:
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
        entry = self.workspace.get_active_entry()
        if entry is None or entry.is_playing:
            return False
        label = f"reparent:{entity_name}"
        transaction = self.pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entry.scene.find_entity(entity_name) is None:
                self.pipeline.rollback(entry, token)
                return False
            if parent_name is not None and not self.validate_parent(
                entry,
                entity_name,
                parent_name,
            ):
                self.pipeline.rollback(entry, token)
                return False
            world_tx = self.compute_world_transform_from_scene_data(entry, entity_name)
            parent_world = (
                self.compute_world_transform_from_scene_data(entry, parent_name)
                if parent_name is not None
                else None
            )
            if not entry.scene.update_entity_property(entity_name, "parent", parent_name):
                self.pipeline.rollback(entry, token)
                return False
            if world_tx is not None:
                wx, wy, w_rot, w_sx, w_sy = world_tx
                if parent_world is not None:
                    px, py, p_rot, p_sx, p_sy = parent_world
                    transform_update = {
                        "x": wx - px,
                        "y": wy - py,
                        "rotation": w_rot - p_rot,
                        "scale_x": w_sx / p_sx if p_sx != 0 else w_sx,
                        "scale_y": w_sy / p_sy if p_sy != 0 else w_sy,
                    }
                else:
                    transform_update = {
                        "x": wx,
                        "y": wy,
                        "rotation": w_rot,
                        "scale_x": w_sx,
                        "scale_y": w_sy,
                    }
                if not entry.scene.update_component_properties(
                    entity_name,
                    "Transform",
                    transform_update,
                ):
                    self.pipeline.rollback(entry, token)
                    return False
        except Exception:
            self.pipeline.rollback(entry, token)
            raise
        return self.pipeline.commit_snapshot(entry, token, before, label=label)

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[dict[str, dict[str, Any]]] = None,
    ) -> bool:
        if not self.serializable_entities.create_entity(name, components):
            return False
        entry = self.workspace.get_active_entry()
        if entry is None or not self.validate_parent(entry, name, parent_name):
            return False
        return self.serializable_entities.update_entity_property(name, "parent", parent_name)

    def duplicate_entity_subtree(
        self,
        entity_name: str,
        new_root_name: Optional[str] = None,
    ) -> bool:
        entry = self.workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        label = f"duplicate_entity:{entity_name}"
        transaction = self.pipeline.begin(
            entry,
            failure_context=label,
            clone_world=True,
        )
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entry.edit_world is None:
                self.pipeline.rollback(entry, token)
                return False
            root = entry.edit_world.get_entity_by_name(entity_name)
            if root is None:
                self.pipeline.rollback(entry, token)
                return False
            subtree = [root] + entry.edit_world.get_descendants(root.name)
            target_root_name = new_root_name or f"{root.name}_copy"
            mapping = {root.name: target_root_name}
            for entity in subtree[1:]:
                suffix = (
                    entity.name[len(root.name):]
                    if entity.name.startswith(root.name)
                    else f"_{entity.name}"
                )
                mapping[entity.name] = f"{target_root_name}{suffix}"
            existing_names = {
                str(item.get("name", ""))
                for item in entry.scene.entities_data
                if isinstance(item, dict)
            }
            if len(set(mapping.values())) != len(mapping) or any(
                name in existing_names for name in mapping.values()
            ):
                self.pipeline.rollback(entry, token)
                return False
            payloads: list[dict[str, Any]] = []
            for entity in subtree:
                payload = entity.to_dict()
                payload.pop("id", None)
                payload["name"] = mapping[entity.name]
                if payload.get("parent") in mapping:
                    payload["parent"] = mapping[str(payload["parent"])]
                if payload.get("prefab_root_name") in mapping:
                    payload["prefab_root_name"] = mapping[str(payload["prefab_root_name"])]
                payloads.append(payload)
            for payload in payloads:
                if not entry.scene.add_entity(payload):
                    self.pipeline.rollback(entry, token)
                    return False
            self.workspace.sync_feature_metadata_from_scene_links(entry)
        except Exception:
            self.pipeline.rollback(entry, token)
            raise
        return self.pipeline.commit_snapshot(entry, token, before, label=label)

    def copy_entity_subtree(self, entity_name: str) -> bool:
        entry = self.workspace.get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        root = entry.edit_world.get_entity_by_name(entity_name)
        if root is None:
            return False
        subtree = [root] + entry.edit_world.get_descendants(root.name)
        self._clipboard = [
            {key: value for key, value in entity.to_dict().items() if key != "id"}
            for entity in subtree
        ]
        self._clipboard_root_name = root.name
        return True

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        entry = self.workspace.resolve_entry(target_scene_key)
        if entry is None or entry.is_playing or not self._clipboard:
            return False
        label = f"paste_entity:{self._clipboard_root_name}"
        transaction = self.pipeline.begin(
            entry,
            failure_context=label,
            clone_world=True,
        )
        if transaction is None:
            return False
        token, before = transaction
        try:
            names_in_scene = {
                str(item.get("name", ""))
                for item in entry.scene.entities_data
                if isinstance(item, dict)
            }
            mapping: dict[str, str] = {}
            for payload in self._clipboard:
                original_name = str(payload.get("name", "") or "Entity")
                candidate = (
                    original_name
                    if original_name not in names_in_scene
                    else self._unique_entity_name(names_in_scene, f"{original_name}_copy")
                )
                mapping[original_name] = candidate
                names_in_scene.add(candidate)
            payloads: list[dict[str, Any]] = []
            for payload in self._clipboard:
                cloned = copy.deepcopy(payload)
                cloned["name"] = mapping[str(payload.get("name", ""))]
                if cloned.get("parent") in mapping:
                    cloned["parent"] = mapping[str(cloned["parent"])]
                payloads.append(cloned)
            for payload in payloads:
                if not entry.scene.add_entity(payload):
                    self.pipeline.rollback(entry, token)
                    return False
            self.workspace.sync_feature_metadata_from_scene_links(entry)
        except Exception:
            self.pipeline.rollback(entry, token)
            raise
        return self.pipeline.commit_snapshot(entry, token, before, label=label)

    @staticmethod
    def compute_world_transform_from_scene_data(
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[tuple[float, float, float, float, float]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return None
        transform = entity_data.get("components", {}).get("Transform")
        if not isinstance(transform, dict):
            return None
        tx = float(transform.get("x", 0.0))
        ty = float(transform.get("y", 0.0))
        t_rot = float(transform.get("rotation", 0.0))
        t_sx = float(transform.get("scale_x", 1.0))
        t_sy = float(transform.get("scale_y", 1.0))
        parent_name = entity_data.get("parent")
        visited: set[str] = {entity_name}
        while isinstance(parent_name, str):
            if parent_name in visited:
                break
            visited.add(parent_name)
            parent_data = entry.scene.find_entity(parent_name)
            if parent_data is None:
                break
            parent_transform = parent_data.get("components", {}).get("Transform")
            if not isinstance(parent_transform, dict):
                break
            tx += float(parent_transform.get("x", 0.0))
            ty += float(parent_transform.get("y", 0.0))
            t_rot += float(parent_transform.get("rotation", 0.0))
            t_sx *= float(parent_transform.get("scale_x", 1.0))
            t_sy *= float(parent_transform.get("scale_y", 1.0))
            parent_name = parent_data.get("parent")
        return tx, ty, t_rot, t_sx, t_sy

    @staticmethod
    def _unique_entity_name(existing_names: set[str], base_name: str) -> str:
        candidate = base_name
        suffix = 1
        while candidate in existing_names:
            candidate = f"{base_name}_{suffix}"
            suffix += 1
        return candidate


@dataclass
class ScenePrefabAuthoring:
    workspace: SceneWorkspace
    pipeline: SceneSerializableTransactionPort
    serializable_entities: SceneSerializableEntityPort

    def create_prefab(
        self,
        entity_name: str,
        prefab_path: str,
        *,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
        prefab_locator: Optional[str] = None,
    ) -> bool:
        entry = self.workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False

        from engine.assets.prefab import PrefabManager

        if not replace_original:
            if not self.pipeline.flush_pending(
                entry,
                failure_context=f"create_prefab:{entity_name}",
            ):
                return False
            if entry.edit_world is None:
                return False
            root = entry.edit_world.get_entity_by_name(entity_name)
            if root is None:
                return False
            return PrefabManager.save_prefab(root, prefab_path, world=entry.edit_world)

        label = f"create_prefab:{entity_name}"
        transaction = self.pipeline.begin(
            entry,
            failure_context=label,
            clone_world=True,
        )
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entry.edit_world is None:
                self.pipeline.rollback(entry, token)
                return False
            root = entry.edit_world.get_entity_by_name(entity_name)
            if root is None:
                self.pipeline.rollback(entry, token)
                return False
            root_instance_name = str(instance_name or entity_name or root.name)
            if (
                root_instance_name != entity_name
                and entry.scene.find_entity(root_instance_name) is not None
            ):
                self.pipeline.rollback(entry, token)
                return False
            root_parent = root.parent_name
            root_prefab_name = (
                root.prefab_instance.get("root_name")
                if root.prefab_instance
                else None
            )
            if not PrefabManager.save_prefab(root, prefab_path, world=entry.edit_world):
                self.pipeline.rollback(entry, token)
                return False
            if not entry.scene.remove_entity_subtree(entity_name):
                self.pipeline.rollback(entry, token)
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
                self.pipeline.rollback(entry, token)
                return False
            self.workspace.sync_feature_metadata_from_scene_links(entry)
        except Exception:
            self.pipeline.rollback(entry, token)
            raise
        return self.pipeline.commit_snapshot(entry, token, before, label=label)

    def instantiate_prefab(
        self,
        name: str,
        prefab_path: str,
        parent: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        root_name: Optional[str] = None,
    ) -> bool:
        return self.serializable_entities.create_entity_from_data(
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
        entry = self.workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        label = f"unpack_prefab:{entity_name}"
        transaction = self.pipeline.begin(
            entry,
            failure_context=label,
            clone_world=True,
        )
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entry.edit_world is None:
                self.pipeline.rollback(entry, token)
                return False
            root = entry.edit_world.get_entity_by_name(entity_name)
            if root is None or root.prefab_instance is None:
                self.pipeline.rollback(entry, token)
                return False
            subtree = [root] + entry.edit_world.get_descendants(root.name)
            explicit_entities: list[dict[str, Any]] = []
            for entity in subtree:
                payload = entity.to_dict()
                payload.pop("id", None)
                payload.pop("prefab_instance", None)
                payload.pop("prefab_source_path", None)
                payload.pop("prefab_root_name", None)
                explicit_entities.append(payload)
            if not entry.scene.remove_entity_subtree(entity_name):
                self.pipeline.rollback(entry, token)
                return False
            for payload in explicit_entities:
                if not entry.scene.add_entity(payload):
                    self.pipeline.rollback(entry, token)
                    return False
            self.workspace.sync_feature_metadata_from_scene_links(entry)
        except Exception:
            self.pipeline.rollback(entry, token)
            raise
        return self.pipeline.commit_snapshot(entry, token, before, label=label)

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        entry = self.workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        label = f"apply_prefab_overrides:{entity_name}"
        transaction = self.pipeline.begin(
            entry,
            failure_context=label,
            clone_world=True,
        )
        if transaction is None:
            return False
        token, before = transaction

        from engine.assets.prefab import PrefabManager

        try:
            if entry.edit_world is None:
                self.pipeline.rollback(entry, token)
                return False
            root = entry.edit_world.get_entity_by_name(entity_name)
            entity_data = entry.scene.find_entity(entity_name)
            if root is None or root.prefab_instance is None or entity_data is None:
                self.pipeline.rollback(entry, token)
                return False
            prefab_instance = entity_data.get("prefab_instance")
            if not isinstance(prefab_instance, dict):
                self.pipeline.rollback(entry, token)
                return False
            updated_prefab_instance = copy.deepcopy(prefab_instance)
            updated_prefab_instance["overrides"] = {}
            raw_entity_id = entity_data.get("id")
            entity_id = (
                raw_entity_id.strip()
                if isinstance(raw_entity_id, str) and raw_entity_id.strip()
                else None
            )
            prefab_path = str(root.prefab_instance.get("prefab_path", ""))
            resolved_path = (
                (Path(entry.scene.source_path).resolve().parent / prefab_path).resolve().as_posix()
                if entry.scene.source_path
                else prefab_path
            )
            if not PrefabManager.save_prefab(root, resolved_path, world=entry.edit_world):
                self.pipeline.rollback(entry, token)
                return False
            changed = (
                entry.scene.update_entity_property_by_id(
                    entity_id,
                    "prefab_instance",
                    updated_prefab_instance,
                )
                if entity_id is not None
                else entry.scene.update_entity_property(
                    entity_name,
                    "prefab_instance",
                    updated_prefab_instance,
                )
            )
            if not changed:
                self.pipeline.rollback(entry, token)
                return False
        except Exception:
            self.pipeline.rollback(entry, token)
            return False
        try:
            return self.pipeline.commit_snapshot(entry, token, before, label=label)
        except Exception:
            self.pipeline.rollback(entry, token)
            return False


class SceneStructuralAuthoring:
    def __init__(
        self,
        workspace: SceneWorkspace,
        pipeline: SceneSerializableTransactionPort,
        serializable_entities: SceneSerializableEntityPort,
        prefab_overrides: PrefabOverridePort,
    ) -> None:
        self._serializable_entities = serializable_entities
        self._hierarchy = SceneHierarchyAuthoring(
            workspace,
            pipeline,
            serializable_entities,
        )
        self._prefabs = ScenePrefabAuthoring(
            workspace,
            pipeline,
            serializable_entities,
        )
        self._prefab_overrides = prefab_overrides

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

    def compute_world_transform_from_scene_data(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[tuple[float, float, float, float, float]]:
        return self._hierarchy.compute_world_transform_from_scene_data(entry, entity_name)

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
        return self._prefab_overrides.update_component_property(
            entry,
            entity_name,
            component_name,
            property_name,
            value,
        )

    def update_prefab_entity_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._prefab_overrides.update_entity_property(
            entry,
            entity_name,
            property_name,
            value,
        )

    def replace_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        return self._prefab_overrides.replace_component(
            entry,
            entity_name,
            component_name,
            component_data,
        )

    def remove_prefab_component_override(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> bool:
        return self._prefab_overrides.remove_component(
            entry,
            entity_name,
            component_name,
        )
