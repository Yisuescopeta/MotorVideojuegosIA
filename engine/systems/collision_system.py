"""
engine/systems/collision_system.py - Sistema de deteccion de colisiones
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.spatial_hash import SpatialHash2D

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus

AABB = tuple[float, float, float, float]


@dataclass
class CollisionInfo:
    entity_a: Entity
    entity_b: Entity
    is_trigger: bool


@dataclass(frozen=True)
class _CollisionEntry:
    entity: Entity
    collider: Collider
    rigidbody: Optional[RigidBody]
    aabb: AABB


class CollisionSystem:
    """Sistema de deteccion de colisiones AABB."""

    def __init__(self, event_bus: Optional["EventBus"] = None, *, deterministic_debug: bool = False) -> None:
        self._collisions: list[CollisionInfo] = []
        self._event_bus: Optional["EventBus"] = event_bus
        self._step_metrics: dict[str, int] = {
            "candidate_pairs": 0,
            "narrow_phase_pairs": 0,
            "actual_collisions": 0,
        }
        self._query_buffer: set[int] = set()
        self._spatial_hash_cell_size: float = 128.0
        self.deterministic_debug: bool = bool(deterministic_debug)
        self._grid: SpatialHash2D = SpatialHash2D(cell_size=self._spatial_hash_cell_size)
        self._entries_by_id: dict[int, _CollisionEntry] = {}
        self._checked_pairs: set[int] = set()

    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus

    def update(self, world: World) -> None:
        self._collisions.clear()
        self._reset_step_metrics()
        self._query_buffer.clear()
        grid = self._prepare_grid()
        entries_by_id = self._entries_by_id
        entries_by_id.clear()

        for entity in world.get_entities_with(Transform, Collider):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            if transform is None or collider is None or not collider.enabled:
                continue
            entry = _CollisionEntry(
                entity=entity,
                collider=collider,
                rigidbody=entity.get_component(RigidBody),
                aabb=collider.get_bounds(transform.x, transform.y),
            )
            entries_by_id[int(entity.id)] = entry
            grid.insert(entity.id, entry.aabb)

        checked_pairs = self._checked_pairs
        checked_pairs.clear()
        pair_shift = self._pair_shift(entries_by_id)
        entry_items = (
            ((entity_id, entries_by_id[entity_id]) for entity_id in sorted(entries_by_id))
            if self.deterministic_debug
            else entries_by_id.items()
        )
        for entity_id, entry_a in entry_items:
            query_result = grid.query_into(entry_a.aabb, self._query_buffer)
            candidate_ids = sorted(query_result) if self.deterministic_debug else query_result
            for entity_b_id in candidate_ids:
                if entity_b_id <= entity_id:
                    continue
                pair_key = self._pair_key(entity_id, entity_b_id, pair_shift)
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                self._step_metrics["candidate_pairs"] += 1

                entry_b = entries_by_id.get(entity_b_id)
                if entry_b is None or not self._can_check_pair(world, entry_a, entry_b):
                    continue

                self._step_metrics["narrow_phase_pairs"] += 1
                if not self._aabbs_overlap(entry_a.aabb, entry_b.aabb):
                    continue

                collision = CollisionInfo(
                    entity_a=entry_a.entity,
                    entity_b=entry_b.entity,
                    is_trigger=bool(entry_a.collider.is_trigger or entry_b.collider.is_trigger),
                )
                self._collisions.append(collision)
                self._step_metrics["actual_collisions"] += 1
                self._emit_collision_event(collision)

    def _reset_step_metrics(self) -> None:
        self._step_metrics["candidate_pairs"] = 0
        self._step_metrics["narrow_phase_pairs"] = 0
        self._step_metrics["actual_collisions"] = 0

    def _prepare_grid(self) -> SpatialHash2D:
        if self._grid.cell_size != max(float(self._spatial_hash_cell_size), 1.0):
            self._grid = SpatialHash2D(cell_size=self._spatial_hash_cell_size)
        else:
            self._grid.clear()
        return self._grid

    def _pair_shift(self, entries_by_id: dict[int, _CollisionEntry]) -> int:
        if not entries_by_id:
            return 1
        return max(1, max(entries_by_id).bit_length())

    def _pair_key(self, entity_a_id: int, entity_b_id: int, pair_shift: int) -> int:
        if entity_a_id > entity_b_id:
            entity_a_id, entity_b_id = entity_b_id, entity_a_id
        return (entity_a_id << pair_shift) | entity_b_id

    def _emit_collision_event(self, collision: CollisionInfo) -> None:
        if self._event_bus is None:
            return
        event_name = "on_trigger_enter" if collision.is_trigger else "on_collision"
        self._event_bus.emit(
            event_name,
            {
                "entity_a": collision.entity_a.name,
                "entity_b": collision.entity_b.name,
                "entity_a_id": collision.entity_a.id,
                "entity_b_id": collision.entity_b.id,
                "is_trigger": collision.is_trigger,
            },
        )

    def _can_check_pair(self, world: World, entry_a: _CollisionEntry, entry_b: _CollisionEntry) -> bool:
        if not self._layers_can_collide(world, entry_a.entity.layer, entry_b.entity.layer):
            return False
        if not self._is_simulated(entry_a.rigidbody) and not self._is_simulated(entry_b.rigidbody):
            return False
        return self._allows_contact(entry_a.rigidbody, entry_b.rigidbody)

    def _aabbs_overlap(self, aabb_a: AABB, aabb_b: AABB) -> bool:
        left_a, top_a, right_a, bottom_a = aabb_a
        left_b, top_b, right_b, bottom_b = aabb_b
        return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b

    def _layers_can_collide(self, world: World, layer_a: str, layer_b: str) -> bool:
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{layer_a}|{layer_b}", True))

    def _is_simulated(self, rigidbody: Optional[RigidBody]) -> bool:
        if rigidbody is None:
            return True
        return rigidbody.enabled and rigidbody.simulated

    def _allows_contact(self, rigidbody_a: Optional[RigidBody], rigidbody_b: Optional[RigidBody]) -> bool:
        if rigidbody_a is None and rigidbody_b is None:
            return True
        if rigidbody_a is not None and rigidbody_b is None:
            return rigidbody_a.body_type != "kinematic" or rigidbody_a.use_full_kinematic_contacts
        if rigidbody_b is not None and rigidbody_a is None:
            return rigidbody_b.body_type != "kinematic" or rigidbody_b.use_full_kinematic_contacts
        if rigidbody_a is None or rigidbody_b is None:
            return True
        if rigidbody_a.body_type == "kinematic" and rigidbody_b.body_type == "kinematic":
            return rigidbody_a.use_full_kinematic_contacts or rigidbody_b.use_full_kinematic_contacts
        if rigidbody_a.body_type == "kinematic" and rigidbody_b.body_type == "static":
            return rigidbody_a.use_full_kinematic_contacts
        if rigidbody_b.body_type == "kinematic" and rigidbody_a.body_type == "static":
            return rigidbody_b.use_full_kinematic_contacts
        return True

    def get_collisions(self) -> list[CollisionInfo]:
        return self._collisions.copy()

    def get_step_metrics(self) -> dict[str, int]:
        return dict(self._step_metrics)

    def get_collisions_for(self, entity: Entity) -> list[CollisionInfo]:
        return [col for col in self._collisions if col.entity_a.id == entity.id or col.entity_b.id == entity.id]

    def has_collision(self, entity: Entity) -> bool:
        return len(self.get_collisions_for(entity)) > 0
