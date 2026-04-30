from __future__ import annotations

import math
from typing import Any

from engine.components.gameplay2d import Collectible2D, Goal2D, Hazard2D, MovingPlatform2D, RespawnPoint2D
from engine.components.playercontroller2d import PlayerController2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World


class Gameplay2DSemanticSystem:
    """Runtime bridge for 2D semantic gameplay components."""

    def __init__(self) -> None:
        self._handled_contacts: set[tuple[str, int, int]] = set()
        self._moving_platform_state: dict[int, dict[str, Any]] = {}

    def reset(self) -> None:
        self._handled_contacts.clear()
        self._moving_platform_state.clear()

    def update_moving_platforms(self, world: World, dt: float, event_bus: Any | None) -> None:
        step_seconds = max(0.0, float(dt))
        if step_seconds <= 0.0:
            return
        if not hasattr(world, "get_entities_with"):
            return
        for entity in world.get_entities_with(Transform, MovingPlatform2D):
            platform = entity.get_component(MovingPlatform2D)
            transform = entity.get_component(Transform)
            if platform is None or transform is None:
                continue
            if not platform.start_active or platform.speed <= 0.0 or len(platform.path) < 2:
                continue

            state = self._moving_platform_state.setdefault(
                int(entity.id),
                {"target_index": 1, "started": False, "completed": False},
            )
            if state.get("completed"):
                continue

            target_index = int(state.get("target_index", 1))
            if target_index < 0 or target_index >= len(platform.path):
                target_index = 1
                state["target_index"] = target_index

            target = platform.path[target_index]
            target_x = float(target.get("x", transform.x))
            target_y = float(target.get("y", transform.y))
            dx = target_x - float(transform.x)
            dy = target_y - float(transform.y)
            distance = math.hypot(dx, dy)
            if distance <= 1e-6:
                self._handle_moving_platform_arrival(
                    entity,
                    platform,
                    state,
                    target_index,
                    target_x,
                    target_y,
                    event_bus,
                )
                continue

            max_distance = platform.speed * step_seconds
            if max_distance >= distance:
                new_x = target_x
                new_y = target_y
            else:
                ratio = max_distance / distance
                new_x = float(transform.x) + dx * ratio
                new_y = float(transform.y) + dy * ratio

            if new_x == transform.x and new_y == transform.y:
                continue
            transform.x = new_x
            transform.y = new_y
            world.touch_transform()
            world.touch_physics()
            if not state.get("started"):
                state["started"] = True
                self._emit_moving_platform_event(
                    event_bus,
                    "moving_platform_started",
                    entity,
                    platform,
                    target_index,
                    new_x,
                    new_y,
                )
            if new_x == target_x and new_y == target_y:
                self._handle_moving_platform_arrival(
                    entity,
                    platform,
                    state,
                    target_index,
                    target_x,
                    target_y,
                    event_bus,
                )

    def update(self, world: World, contacts: Any, event_bus: Any | None) -> None:
        if event_bus is None:
            return
        destroyed_ids: set[int] = set()
        for contact in self._iter_contacts(contacts):
            entity_a = self._entity_from_contact(world, contact, "a")
            entity_b = self._entity_from_contact(world, contact, "b")
            if entity_a is None or entity_b is None:
                continue
            if entity_a.id in destroyed_ids or entity_b.id in destroyed_ids:
                continue
            player, target = self._player_and_target(entity_a, entity_b)
            if player is None or target is None:
                continue
            if self._handle_collectible(world, event_bus, player, target):
                destroyed_ids.add(target.id)
                continue
            self._handle_hazard(world, event_bus, player, target)
            self._handle_goal(event_bus, player, target)

    def _iter_contacts(self, contacts: Any) -> list[Any]:
        if contacts is None:
            return []
        if isinstance(contacts, list):
            return contacts
        try:
            return list(contacts)
        except TypeError:
            return []

    def _entity_from_contact(self, world: World, contact: Any, side: str) -> Entity | None:
        entity_id = getattr(contact, f"entity_{side}_id", None)
        if entity_id is None and isinstance(contact, dict):
            entity_id = contact.get(f"entity_{side}_id")
        entity = None
        if entity_id is not None:
            try:
                entity = world.get_entity(int(entity_id))
            except (TypeError, ValueError):
                entity = None
        if entity is not None:
            return entity if entity.active else None

        entity_name = getattr(contact, f"entity_{side}", None)
        if entity_name is None and isinstance(contact, dict):
            entity_name = contact.get(f"entity_{side}")
        if not entity_name:
            return None
        entity = world.get_entity_by_name(str(entity_name))
        return entity if entity is not None and entity.active else None

    def _player_and_target(self, entity_a: Entity, entity_b: Entity) -> tuple[Entity | None, Entity | None]:
        if self._is_player(entity_a):
            return entity_a, entity_b
        if self._is_player(entity_b):
            return entity_b, entity_a
        return None, None

    def _is_player(self, entity: Entity) -> bool:
        if entity.tag == "Player":
            return True
        controller = entity.get_component(PlayerController2D)
        return bool(controller is not None and getattr(controller, "enabled", True))

    def _handle_collectible(self, world: World, event_bus: Any, player: Entity, target: Entity) -> bool:
        collectible = target.get_component(Collectible2D)
        if collectible is None or not getattr(collectible, "enabled", True):
            return False
        key = ("collectible", int(player.id), int(target.id))
        if key in self._handled_contacts:
            return False
        self._handled_contacts.add(key)
        event_bus.emit(
            collectible.event_name,
            {
                "player": player.name,
                "collectible": target.name,
                "points": collectible.points,
            },
        )
        if collectible.destroy_on_collect:
            world.remove_entity(target.id)
            return True
        return False

    def _handle_hazard(self, world: World, event_bus: Any, player: Entity, target: Entity) -> None:
        hazard = target.get_component(Hazard2D)
        if hazard is None or not getattr(hazard, "enabled", True):
            return
        key = ("hazard", int(player.id), int(target.id))
        if key in self._handled_contacts:
            return
        self._handled_contacts.add(key)
        event_bus.emit(
            hazard.event_name,
            {
                "player": player.name,
                "hazard": target.name,
                "damage": hazard.damage,
            },
        )
        if not hazard.respawn_on_touch:
            return
        respawn = self._first_active_respawn(world)
        if respawn is None:
            event_bus.emit(
                "hazard_respawn_missing",
                {
                    "player": player.name,
                    "hazard": target.name,
                    "damage": hazard.damage,
                    "reason": "no_active_respawn_point",
                },
            )
            return
        self._move_to_respawn(world, player, respawn)

    def _handle_goal(self, event_bus: Any, player: Entity, target: Entity) -> None:
        goal = target.get_component(Goal2D)
        if goal is None or not getattr(goal, "enabled", True):
            return
        key = ("goal", int(player.id), int(target.id))
        if key in self._handled_contacts:
            return
        self._handled_contacts.add(key)
        event_bus.emit(
            goal.event_name,
            {
                "player": player.name,
                "goal": target.name,
                "next_scene": goal.next_scene,
            },
        )

    def _handle_moving_platform_arrival(
        self,
        entity: Entity,
        platform: MovingPlatform2D,
        state: dict[str, Any],
        point_index: int,
        x: float,
        y: float,
        event_bus: Any | None,
    ) -> None:
        self._emit_moving_platform_event(
            event_bus,
            "moving_platform_reached_point",
            entity,
            platform,
            point_index,
            x,
            y,
        )
        if platform.loop:
            state["target_index"] = (point_index + 1) % len(platform.path)
            return
        if point_index >= len(platform.path) - 1:
            state["completed"] = True
            self._emit_moving_platform_event(
                event_bus,
                "moving_platform_completed",
                entity,
                platform,
                point_index,
                x,
                y,
            )
            return
        state["target_index"] = point_index + 1

    def _emit_moving_platform_event(
        self,
        event_bus: Any | None,
        event_name: str,
        entity: Entity,
        platform: MovingPlatform2D,
        point_index: int,
        x: float,
        y: float,
    ) -> None:
        if event_bus is None:
            return
        event_bus.emit(
            event_name,
            {
                "platform": entity.name,
                "point_index": int(point_index),
                "x": float(x),
                "y": float(y),
                "loop": bool(platform.loop),
            },
        )

    def _first_active_respawn(self, world: World) -> Entity | None:
        for entity in world.iter_all_entities():
            if not entity.active:
                continue
            respawn = entity.get_component(RespawnPoint2D)
            transform = entity.get_component(Transform)
            if respawn is None or transform is None:
                continue
            if getattr(respawn, "enabled", True) and respawn.active and getattr(transform, "enabled", True):
                return entity
        return None

    def _move_to_respawn(self, world: World, player: Entity, respawn: Entity) -> None:
        player_transform = player.get_component(Transform)
        respawn_transform = respawn.get_component(Transform)
        if player_transform is None or respawn_transform is None:
            return
        player_transform.x = respawn_transform.x
        player_transform.y = respawn_transform.y
        rigidbody = player.get_component(RigidBody)
        if rigidbody is not None:
            rigidbody.velocity_x = 0.0
            rigidbody.velocity_y = 0.0
        world.touch_transform()
        world.touch_physics()
