from __future__ import annotations

from typing import Any

from engine.components.gameplay2d import (
    Checkpoint2D,
    Collectible2D,
    Goal2D,
    Hazard2D,
    KillZone2D,
    LevelBounds2D,
    RespawnPoint2D,
)
from engine.components.playercontroller2d import PlayerController2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World


class Gameplay2DSemanticSystem:
    """Runtime bridge for data-only 2D semantic gameplay components."""

    def __init__(self) -> None:
        self._handled_contacts: set[tuple[str, int, int]] = set()
        self._bounds_exit_contacts: set[tuple[int, int, str]] = set()
        self._active_respawn_entity_id: int | None = None
        self._active_checkpoint_id: str | None = None

    def reset(self) -> None:
        self._handled_contacts.clear()
        self._bounds_exit_contacts.clear()
        self._active_respawn_entity_id = None
        self._active_checkpoint_id = None

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
            self._handle_checkpoint(world, event_bus, player, target)
            self._handle_hazard(world, event_bus, player, target)
            self._handle_killzone(world, event_bus, player, target)
            self._handle_goal(event_bus, player, target)
        self._handle_level_bounds(world, event_bus)

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

    def _handle_checkpoint(self, world: World, event_bus: Any, player: Entity, target: Entity) -> None:
        checkpoint = target.get_component(Checkpoint2D)
        if checkpoint is None or not getattr(checkpoint, "enabled", True) or not checkpoint.active:
            return
        key = ("checkpoint", int(player.id), int(target.id))
        if key in self._handled_contacts:
            return
        self._handled_contacts.add(key)
        event_bus.emit(
            checkpoint.event_name,
            {
                "player": player.name,
                "checkpoint": target.name,
                "checkpoint_id": checkpoint.checkpoint_id,
            },
        )
        if not checkpoint.set_respawn_on_touch:
            return
        respawn = self._respawn_by_id(world, checkpoint.checkpoint_id) or self._respawn_candidate(target)
        if respawn is None:
            return
        self._active_respawn_entity_id = int(respawn.id)
        self._active_checkpoint_id = checkpoint.checkpoint_id

    def _handle_killzone(self, world: World, event_bus: Any, player: Entity, target: Entity) -> None:
        killzone = target.get_component(KillZone2D)
        if killzone is None or not getattr(killzone, "enabled", True):
            return
        key = ("killzone", int(player.id), int(target.id))
        if key in self._handled_contacts:
            return
        self._handled_contacts.add(key)
        event_bus.emit(
            killzone.event_name,
            {
                "player": player.name,
                "killzone": target.name,
                "damage": killzone.damage,
            },
        )
        if not killzone.respawn_on_touch:
            return
        respawn = self._active_session_respawn(world) or self._first_active_respawn(world)
        if respawn is None:
            event_bus.emit(
                "killzone_respawn_missing",
                {
                    "player": player.name,
                    "killzone": target.name,
                    "damage": killzone.damage,
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

    def _handle_level_bounds(self, world: World, event_bus: Any) -> None:
        players = self._active_players_with_transform(world)
        if not players:
            self._bounds_exit_contacts.clear()
            return

        active_keys: set[tuple[int, int, str]] = set()
        for bounds_entity in self._active_level_bounds(world):
            bounds = bounds_entity.get_component(LevelBounds2D)
            if bounds is None:
                continue
            left = float(bounds.left)
            right = float(bounds.right)
            top = float(bounds.top)
            bottom = float(bounds.bottom)
            for player, transform in players:
                player_x = float(transform.x)
                player_y = float(transform.y)
                sides: list[str] = []
                if player_x < left:
                    sides.append("left")
                elif player_x > right:
                    sides.append("right")
                if player_y < top:
                    sides.append("top")
                elif player_y > bottom:
                    sides.append("bottom")

                for side in sides:
                    key = (int(player.id), int(bounds_entity.id), side)
                    active_keys.add(key)
                    if key in self._bounds_exit_contacts:
                        continue
                    self._bounds_exit_contacts.add(key)
                    self._emit_level_bounds_exit(
                        event_bus,
                        player,
                        bounds_entity,
                        side,
                        player_x,
                        player_y,
                        left,
                        right,
                        top,
                        bottom,
                    )
                    if side in {"left", "right"}:
                        self._clamp_player_horizontal(world, player, transform, left if side == "left" else right)
                    elif side == "bottom":
                        self._respawn_player_from_level_bounds(world, event_bus, player, bounds_entity)

        self._bounds_exit_contacts.intersection_update(active_keys)

    def _active_players_with_transform(self, world: World) -> list[tuple[Entity, Transform]]:
        players: list[tuple[Entity, Transform]] = []
        for entity in world.iter_all_entities():
            if not entity.active or not self._is_player(entity):
                continue
            transform = entity.get_component(Transform)
            if transform is not None and getattr(transform, "enabled", True):
                players.append((entity, transform))
        return players

    def _active_level_bounds(self, world: World) -> list[Entity]:
        bounds_entities: list[Entity] = []
        for entity in world.iter_all_entities():
            if not entity.active:
                continue
            bounds = entity.get_component(LevelBounds2D)
            if bounds is not None and getattr(bounds, "enabled", True):
                bounds_entities.append(entity)
        return bounds_entities

    def _emit_level_bounds_exit(
        self,
        event_bus: Any,
        player: Entity,
        bounds_entity: Entity,
        side: str,
        player_x: float,
        player_y: float,
        left: float,
        right: float,
        top: float,
        bottom: float,
    ) -> None:
        event_bus.emit(
            "level_bounds_exited",
            {
                "player": player.name,
                "bounds_entity": bounds_entity.name,
                "side": side,
                "player_x": player_x,
                "player_y": player_y,
                "left": left,
                "right": right,
                "top": top,
                "bottom": bottom,
            },
        )

    def _clamp_player_horizontal(self, world: World, player: Entity, transform: Transform, x: float) -> None:
        transform.x = x
        rigidbody = player.get_component(RigidBody)
        if rigidbody is not None:
            rigidbody.velocity_x = 0.0
        world.touch_transform()
        world.touch_physics()

    def _respawn_player_from_level_bounds(
        self,
        world: World,
        event_bus: Any,
        player: Entity,
        bounds_entity: Entity,
    ) -> None:
        respawn = self._active_session_respawn(world) or self._first_active_respawn(world)
        if respawn is None:
            event_bus.emit(
                "level_bounds_respawn_missing",
                {
                    "player": player.name,
                    "bounds_entity": bounds_entity.name,
                    "reason": "no_active_respawn_point",
                },
            )
            return
        self._move_to_respawn(world, player, respawn)

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

    def _respawn_by_id(self, world: World, spawn_id: str) -> Entity | None:
        wanted = str(spawn_id or "").strip()
        if not wanted:
            return None
        for entity in world.iter_all_entities():
            if not entity.active:
                continue
            respawn = entity.get_component(RespawnPoint2D)
            transform = entity.get_component(Transform)
            if respawn is None or transform is None:
                continue
            if not (getattr(respawn, "enabled", True) and respawn.active and getattr(transform, "enabled", True)):
                continue
            if respawn.spawn_id == wanted:
                return entity
        return None

    def _respawn_candidate(self, entity: Entity) -> Entity | None:
        transform = entity.get_component(Transform)
        if transform is None or not getattr(transform, "enabled", True):
            return None
        return entity

    def _active_session_respawn(self, world: World) -> Entity | None:
        if self._active_respawn_entity_id is None:
            return None
        respawn = world.get_entity(self._active_respawn_entity_id)
        if respawn is None or not respawn.active:
            return None
        return self._respawn_candidate(respawn)

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
