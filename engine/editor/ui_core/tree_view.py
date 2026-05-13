"""Pure tree model helpers for editor hierarchy views."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from engine.editor.ui_core.protocols import EntityLike, WorldLike


@dataclass(frozen=True)
class TreeNode:
    """Immutable hierarchy row data for editor tree views."""

    id: int
    name: str
    depth: int
    entity_type: str
    component_types: list[str]
    children: list["TreeNode"] = field(default_factory=list)
    parent_id: int | None = None
    is_expandable: bool = False


@dataclass(frozen=True)
class TreeModel:
    """Immutable hierarchy snapshot with id lookup and version marker."""

    root_nodes: list[TreeNode]
    node_map: dict[int, TreeNode]
    version: int

    @classmethod
    def build(cls, world: WorldLike | object) -> "TreeModel":
        """Build hierarchy snapshot without mutating ``world``."""

        entities = _iter_entities(world)
        entity_by_id = {int(getattr(entity, "id")): entity for entity in entities if hasattr(entity, "id")}
        entity_by_name = {str(getattr(entity, "name")): entity for entity in entities if getattr(entity, "name", None) is not None}
        parent_by_id = _collect_parent_ids(world, entities, entity_by_name)
        children_by_parent: dict[int | None, list[EntityLike]] = {}
        for entity in entities:
            entity_id = int(getattr(entity, "id"))
            if entity_id not in entity_by_id:
                continue
            parent_id = parent_by_id.get(entity_id)
            if parent_id is not None and parent_id not in entity_by_id:
                parent_id = None
            children_by_parent.setdefault(parent_id, []).append(entity)
        for children in children_by_parent.values():
            children.sort(key=lambda item: int(getattr(item, "id")))

        node_map: dict[int, TreeNode] = {}

        def build_node(entity: EntityLike, depth: int, active_path: set[int]) -> TreeNode:
            entity_id = int(getattr(entity, "id"))
            if entity_id in active_path:
                children: list[TreeNode] = []
            else:
                children = [
                    build_node(child, depth + 1, active_path | {entity_id})
                    for child in children_by_parent.get(entity_id, [])
                ]
            node = TreeNode(
                id=entity_id,
                name=str(getattr(entity, "name", f"Entity {entity_id}")),
                depth=depth,
                entity_type=get_entity_type(entity),
                component_types=_component_type_names(entity),
                children=children,
                parent_id=parent_by_id.get(entity_id),
                is_expandable=bool(children),
            )
            node_map[entity_id] = node
            return node

        roots = [build_node(entity, 0, set()) for entity in children_by_parent.get(None, [])]
        return cls(roots, node_map, _world_version(world))

    def get_visible_rows(self, expanded_ids: set[int]) -> list[tuple[int, int]]:
        rows: list[tuple[int, int]] = []
        for root in self.root_nodes:
            _append_visible_rows(root, expanded_ids, rows)
        return rows


def get_entity_type(entity: EntityLike | object) -> str:
    """Infer display type from entity component names without mutation."""

    component_names = set(_component_type_names(entity))
    if "Camera" in component_names or "Camera2D" in component_names:
        return "Camera"
    if "TileMap" in component_names or "Tilemap" in component_names:
        return "TileMap"
    if "Sprite" in component_names or "SpriteRenderer" in component_names:
        return "Sprite"
    if "RigidBody" in component_names or "Rigidbody" in component_names or "RigidBody2D" in component_names:
        return "RigidBody"
    if any(name.endswith("Collider") or name.endswith("Collider2D") for name in component_names):
        return "Collider"
    if component_names:
        return "ComponentEntity"
    return "Entity"


def get_type_icon(entity_type: str) -> str:
    return {
        "Camera": "search",
        "TileMap": "menu",
        "Sprite": "play",
        "RigidBody": "gear",
        "Collider": "check",
        "ComponentEntity": "gear",
        "Entity": "menu",
    }.get(entity_type, "menu")


def matches_search(node: TreeNode, query: str) -> bool:
    """Return whether node name, type, or components match query text."""

    normalized = query.strip().lower()
    if not normalized:
        return True
    haystack = [node.name, node.entity_type, *node.component_types]
    return any(normalized in value.lower() for value in haystack)


def filter_nodes(model: TreeModel, query: str) -> list[TreeNode]:
    """Return all nodes in model matching query, independent of expansion."""

    return [node for node in model.node_map.values() if matches_search(node, query)]


def filter_visible_rows(model: TreeModel, expanded_ids: set[int], query: str) -> list[tuple[int, int]]:
    """Return visible row ids and depths after expansion/search filtering."""

    normalized = query.strip().lower()
    if not normalized:
        return model.get_visible_rows(expanded_ids)
    rows: list[tuple[int, int]] = []
    for root in model.root_nodes:
        _append_filtered_rows(root, normalized, rows)
    return rows


def _append_visible_rows(node: TreeNode, expanded_ids: set[int], rows: list[tuple[int, int]]) -> None:
    rows.append((node.id, node.depth))
    if node.id not in expanded_ids:
        return
    for child in node.children:
        _append_visible_rows(child, expanded_ids, rows)


def _append_filtered_rows(node: TreeNode, query: str, rows: list[tuple[int, int]]) -> bool:
    child_matched = False
    child_rows: list[tuple[int, int]] = []
    for child in node.children:
        child_matched = _append_filtered_rows(child, query, child_rows) or child_matched
    node_matched = matches_search(node, query)
    if node_matched or child_matched:
        rows.append((node.id, node.depth))
        rows.extend(child_rows)
        return True
    return False


def _iter_entities(world: WorldLike | object) -> list[EntityLike]:
    for attr in ("iter_all_entities", "get_all_entities", "iter_entities"):
        getter = getattr(world, attr, None)
        if callable(getter):
            return [entity for entity in getter() if isinstance(entity, EntityLike)]
    entities = getattr(world, "entities", None)
    if isinstance(entities, dict):
        return [entity for entity in entities.values() if isinstance(entity, EntityLike)]
    if isinstance(entities, Iterable):
        return [entity for entity in entities if isinstance(entity, EntityLike)]
    return []


def _collect_parent_ids(
    world: WorldLike | object,
    entities: list[EntityLike],
    entity_by_name: dict[str, EntityLike],
) -> dict[int, int | None]:
    get_children = getattr(world, "get_children", None)
    if callable(get_children):
        return _collect_parent_ids_from_world_children(get_children)
    transform_owner = {
        transform: entity
        for entity in entities
        if (transform := _get_component_instance(entity, "Transform")) is not None
    }
    parent_by_id: dict[int, int | None] = {}
    for entity in entities:
        parent_id = _parent_id_from_entity(entity, entity_by_name)
        if parent_id is None:
            transform = _get_component_instance(entity, "Transform")
            parent_transform = getattr(transform, "parent", None) if transform is not None else None
            parent_entity = transform_owner.get(parent_transform)
            if parent_transform is not None and parent_entity is not None:
                parent_id = int(getattr(parent_entity, "id"))
        parent_by_id[int(getattr(entity, "id"))] = parent_id
    return parent_by_id


def _collect_parent_ids_from_world_children(
    get_children: Callable[[str | None], Iterable[EntityLike]],
) -> dict[int, int | None]:
    parent_by_id: dict[int, int | None] = {}
    pending: list[tuple[int | None, EntityLike]] = [
        (None, child) for child in list(get_children(None)) if isinstance(child, EntityLike)
    ]
    visited: set[int] = set()
    while pending:
        parent_id, entity = pending.pop(0)
        entity_id = int(getattr(entity, "id"))
        if entity_id in visited:
            continue
        visited.add(entity_id)
        parent_by_id[entity_id] = parent_id
        for child in list(get_children(entity.name)):
            pending.append((entity_id, child))
    return parent_by_id


def _parent_id_from_entity(entity: EntityLike, entity_by_name: dict[str, EntityLike]) -> int | None:
    parent_name = getattr(entity, "parent_name", None)
    if parent_name is None:
        return None
    parent = entity_by_name.get(str(parent_name))
    return int(getattr(parent, "id")) if parent is not None else None


def _component_type_names(entity: EntityLike | object) -> list[str]:
    components = []
    iter_components = getattr(entity, "iter_components", None)
    if callable(iter_components):
        components = list(iter_components())
    else:
        get_all_components = getattr(entity, "get_all_components", None)
        if callable(get_all_components):
            components = list(get_all_components())
    return sorted(type(component).__name__ for component in components)


def _get_component_instance(entity: EntityLike | object, component_name: str) -> object | None:
    get_by_name = getattr(entity, "get_component_by_name", None)
    if callable(get_by_name):
        component = get_by_name(component_name)
        if component is not None:
            return component
    for component in getattr(entity, "_components", {}).values():
        if type(component).__name__ == component_name:
            return component
    return None


def _world_version(world: WorldLike | object) -> int:
    return int(getattr(world, "structure_version", getattr(world, "version", -1)))
