from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.components.transform import Transform
from engine.scenes.scene import Scene
from engine.serialization.schema import (
    ResolvedSceneReference,
    build_canonical_scene_payload,
    migrate_scene_data,
    validate_no_session_only_references,
    validate_scene_data,
)

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry


class SceneProjectionService:
    """Technical conversion between serialized scenes and edit worlds."""

    def __init__(self, registry: "ComponentRegistry") -> None:
        self._registry = registry
        self._scene_reference_resolver: Callable[[str], ResolvedSceneReference | None] | None = None

    def set_scene_reference_resolver(
        self,
        resolver: Callable[[str], ResolvedSceneReference | None] | None,
    ) -> None:
        self._scene_reference_resolver = resolver

    @staticmethod
    def validate_payload(data: dict[str, Any]) -> dict[str, Any]:
        payload = migrate_scene_data(data)
        validation_errors = validate_scene_data(payload)
        if validation_errors:
            raise ValueError(f"Invalid scene payload: {'; '.join(validation_errors)}")
        return payload

    def create_scene(
        self,
        data: dict[str, Any],
        *,
        source_path: Optional[str] = None,
        fallback_name: str = "Untitled",
    ) -> Scene:
        payload = self.validate_payload(data)
        return Scene(
            str(payload.get("name", fallback_name) or fallback_name),
            payload,
            source_path=source_path,
        )

    @staticmethod
    def create_empty_scene(name: str = "New Scene") -> Scene:
        return Scene(name)

    def create_world(self, scene: Scene) -> "World":
        return scene.create_world(self._registry)

    def canonicalize_component_payload(
        self,
        component_name: str,
        component_data: dict[str, Any],
    ) -> dict[str, Any]:
        payload = copy.deepcopy(component_data)
        rebuilt_component = self._registry.create(component_name, payload)
        if rebuilt_component is None or not hasattr(rebuilt_component, "to_dict"):
            return payload
        rebuilt_payload = rebuilt_component.to_dict()
        return copy.deepcopy(rebuilt_payload) if isinstance(rebuilt_payload, dict) else payload

    def build_canonical_payload(
        self,
        scene: Scene,
        world_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        scene_snapshot = scene.snapshot().to_dict()
        return build_canonical_scene_payload(
            scene_name=scene.name,
            world_snapshot=copy.deepcopy(world_snapshot),
            rules_data=scene_snapshot.get("rules", []),
            feature_metadata=scene_snapshot.get("feature_metadata", {}),
            scene_reference_resolver=self._scene_reference_resolver,
        )

    def canonicalize_scene_references(self, data: dict[str, Any]) -> dict[str, Any]:
        """Canonicalize persisted cross-scene references through the configured resolver."""
        from engine.serialization.schema import canonicalize_scene_cross_references

        return canonicalize_scene_cross_references(
            data,
            self._scene_reference_resolver or (lambda _path: None),
        )

    @staticmethod
    def validate_persistable_payload(data: dict[str, Any]) -> list[str]:
        """Return diagnostics for identities that cannot cross the session boundary."""
        return validate_no_session_only_references(data)

    def add_entity(
        self,
        scene: Scene,
        world: "World",
        entity_data: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        entity_name = str(entity_data.get("name", "") or "")
        if not scene.add_entity(entity_data):
            return None
        canonical_entity = next(
            (view.to_dict() for view in scene.list_entity_views() if view.name == entity_name),
            None,
        )
        if canonical_entity is None:
            return None
        try:
            scene.materialize_entity(world, self._registry, canonical_entity)
        except Exception:
            scene.remove_entity_by_id(str(canonical_entity.get("id", "") or ""))
            raise
        return canonical_entity

    @staticmethod
    def remove_entity_from_world(world: "World", entity_name: str, entity_id: str) -> None:
        root = world.get_entity_by_serialized_id(entity_id) or world.get_entity_by_name(entity_name)
        targets = [
            entity
            for entity in world.iter_all_entities()
            if entity is root or entity.prefab_root_name == entity_name
        ]
        for entity in reversed(targets):
            transform = entity.get_component(Transform)
            if transform is not None and transform.parent is not None:
                transform.parent = None
            world.remove_entity(entity.id)
