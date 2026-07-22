"""Immutable hierarchy read models for the editor surface."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.scenes.refs import EntityRef, OpenSceneRef

if TYPE_CHECKING:
    from engine.scenes.scene import Scene


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    ref: EntityRef
    name: str
    parent: EntityRef | None
    children: tuple[EntityRef, ...]
    depth: int
    component_types: tuple[str, ...]
    is_match: bool = True


@dataclass(frozen=True, slots=True)
class HierarchySnapshot:
    scene: OpenSceneRef
    scene_revision: int
    roots: tuple[EntityRef, ...]
    nodes: tuple[HierarchyNode, ...]
    search: str = ""

    @property
    def by_id(self) -> dict[str, HierarchyNode]:
        return {node.ref.entity_id: node for node in self.nodes}


class HierarchyQueries:
    """Build hierarchy DTOs directly from immutable Scene views."""

    def __init__(self, scene: "Scene", scene_ref: OpenSceneRef) -> None:
        self._scene = scene
        self._scene_ref = scene_ref

    @property
    def scene_ref(self) -> OpenSceneRef:
        return self._scene_ref

    def snapshot(self, search: str = "") -> HierarchySnapshot:
        normalized_search = str(search or "").strip().casefold()
        views = self._scene.list_entity_views()
        refs = {
            view.entity_id: EntityRef(self._scene_ref, view.entity_id)
            for view in views
            if view.entity_id
        }
        parent_by_id: dict[str, EntityRef | None] = {}
        names: dict[str, str] = {}
        components_by_id: dict[str, tuple[str, ...]] = {}
        for view in views:
            if not view.entity_id:
                continue
            names[view.entity_id] = view.name
            raw_parent_id = view.get("parent_id")
            parent_by_id[view.entity_id] = refs.get(raw_parent_id) if isinstance(raw_parent_id, str) else None
            components = view.get("components", {})
            components_by_id[view.entity_id] = tuple(sorted(components)) if isinstance(components, Mapping) else ()

        children_by_parent: dict[str | None, list[str]] = {}
        for entity_id, parent in parent_by_id.items():
            parent_id = parent.entity_id if parent is not None else None
            children_by_parent.setdefault(parent_id, []).append(entity_id)
        for children in children_by_parent.values():
            children.sort(key=lambda entity_id: (names.get(entity_id, "").casefold(), entity_id))

        nodes: list[HierarchyNode] = []

        def build(entity_id: str, depth: int, path: frozenset[str]) -> None:
            if entity_id in path:
                return
            children = tuple(
                refs[child_id]
                for child_id in children_by_parent.get(entity_id, [])
                if child_id in refs
            )
            component_types = components_by_id.get(entity_id, ())
            haystack = " ".join((names.get(entity_id, ""), *component_types)).casefold()
            nodes.append(
                HierarchyNode(
                    ref=refs[entity_id],
                    name=names.get(entity_id, ""),
                    parent=parent_by_id.get(entity_id),
                    children=children,
                    depth=depth,
                    component_types=component_types,
                    is_match=not normalized_search or normalized_search in haystack,
                )
            )
            for child in children:
                build(child.entity_id, depth + 1, path | {entity_id})

        root_ids = tuple(
            EntityRef(self._scene_ref, entity_id)
            for entity_id in children_by_parent.get(None, [])
            if entity_id in refs
        )
        for root in root_ids:
            build(root.entity_id, 0, frozenset())
        return HierarchySnapshot(
            scene=self._scene_ref,
            scene_revision=self._scene.revision,
            roots=root_ids,
            nodes=tuple(nodes),
            search=normalized_search,
        )


__all__ = ["HierarchyNode", "HierarchyQueries", "HierarchySnapshot"]
