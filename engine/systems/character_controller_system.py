from __future__ import annotations

from typing import Any, Optional

from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.inputmap import InputMap
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World


class CharacterControllerSystem:
    """Ejecuta movimiento de personaje data-driven sin depender del editor."""

    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._emitted_contacts: set[tuple[int, int]] = set()

    def set_event_bus(self, event_bus: Optional[Any]) -> None:
        self._event_bus = event_bus

    def update(self, world: World, delta_time: float) -> None:
        self._emitted_contacts = set()
        solids = [
            entity
            for entity in world.get_entities_with(Transform, Collider)
            if entity.active
            and entity.get_component(Collider) is not None
            and entity.get_component(Collider).enabled
            and not entity.get_component(Collider).is_trigger
        ]
        for entity in world.get_entities_with(Transform, Collider, CharacterController2D):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            controller = entity.get_component(CharacterController2D)
            input_map = entity.get_component(InputMap)
            if transform is None or collider is None or controller is None:
                continue
            if not entity.active or not collider.enabled or not controller.enabled:
                continue
            self._apply_inputs(controller, input_map)
            self._move_entity(world, entity, transform, collider, controller, solids, float(delta_time))

    def _apply_inputs(self, controller: CharacterController2D, input_map: InputMap | None) -> None:
        controller.collision_normal_x = 0.0
        controller.collision_normal_y = 0.0
        controller.last_hit_entity = ""
        if input_map is None or not input_map.enabled or not controller.use_input_map:
            return

        horizontal = float(input_map.last_state.get("horizontal", 0.0))
        control = 1.0 if controller.on_floor else controller.air_control
        controller.velocity_x = horizontal * controller.move_speed * control

        jump_pressed = float(input_map.last_state.get("action_1", 0.0)) > 0.5
        if jump_pressed and not controller._jump_was_pressed and controller.on_floor:
            controller.velocity_y = controller.jump_velocity
            controller.on_floor = False
        controller._jump_was_pressed = jump_pressed

    def _move_entity(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        controller: CharacterController2D,
        solids: list[Entity],
        delta_time: float,
    ) -> None:
        if not controller.on_floor:
            controller.velocity_y = min(controller.max_fall_speed, controller.velocity_y + controller.gravity * delta_time)

        delta_x = controller.velocity_x * delta_time
        transform.x += self._sweep_horizontal(world, entity, transform, collider, controller, solids, delta_x)

        controller.on_floor = False
        delta_y = controller.velocity_y * delta_time
        transform.y += self._sweep_vertical(world, entity, transform, collider, controller, solids, delta_y)

        if not controller.on_floor and abs(controller.velocity_y) <= 1e-5 and controller.floor_snap_distance > 0.0:
            snap_distance = self._floor_snap(world, entity, transform, collider, controller, solids)
            if snap_distance is not None:
                transform.y += snap_distance
                controller.on_floor = True

    def _sweep_horizontal(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        controller: CharacterController2D,
        solids: list[Entity],
        delta_x: float,
    ) -> float:
        if abs(delta_x) <= 1e-6:
            return 0.0
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_x
        hit_entity: Entity | None = None
        for other in solids:
            if other.id == entity.id:
                continue
            if not self._layers_can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            if not (top < o_bottom and bottom > o_top):
                continue
            if delta_x > 0:
                gap = o_left - right
                if 0.0 <= gap <= safe_delta:
                    safe_delta = max(0.0, gap)
                    hit_entity = other
                    controller.collision_normal_x = -1.0
            else:
                gap = o_right - left
                if safe_delta <= gap <= 0.0:
                    safe_delta = min(0.0, gap)
                    hit_entity = other
                    controller.collision_normal_x = 1.0
        if hit_entity is not None:
            controller.last_hit_entity = hit_entity.name
            controller.velocity_x = 0.0
            if controller.move_mode == "move_and_collide":
                controller.velocity_y = 0.0
            self._emit_collision(entity, hit_entity)
        return safe_delta

    def _sweep_vertical(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        controller: CharacterController2D,
        solids: list[Entity],
        delta_y: float,
    ) -> float:
        if abs(delta_y) <= 1e-6:
            return 0.0
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_y
        hit_entity: Entity | None = None
        for other in solids:
            if other.id == entity.id:
                continue
            if not self._layers_can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            if not (left < o_right and right > o_left):
                continue
            if delta_y > 0:
                gap = o_top - bottom
                if 0.0 <= gap <= safe_delta:
                    safe_delta = max(0.0, gap)
                    hit_entity = other
                    controller.collision_normal_y = -1.0
                    controller.on_floor = True
            else:
                gap = o_bottom - top
                if safe_delta <= gap <= 0.0:
                    safe_delta = min(0.0, gap)
                    hit_entity = other
                    controller.collision_normal_y = 1.0
        if hit_entity is not None:
            controller.last_hit_entity = hit_entity.name
            controller.velocity_y = 0.0
            if controller.move_mode == "move_and_collide":
                controller.velocity_x = 0.0
            self._emit_collision(entity, hit_entity)
        return safe_delta

    def _floor_snap(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        controller: CharacterController2D,
        solids: list[Entity],
    ) -> float | None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        snap_limit = max(0.0, controller.floor_snap_distance)
        best_snap: float | None = None
        for other in solids:
            if other.id == entity.id:
                continue
            if not self._layers_can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            if not (left < o_right and right > o_left):
                continue
            gap = o_top - bottom
            if 0.0 <= gap <= snap_limit and (best_snap is None or gap < best_snap):
                best_snap = gap
                controller.collision_normal_y = -1.0
                controller.last_hit_entity = other.name
                self._emit_collision(entity, other)
        return best_snap

    def _layers_can_collide(self, world: World, entity: Entity, other: Entity) -> bool:
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{entity.layer}|{other.layer}", True))

    def _emit_collision(self, entity: Entity, other: Entity) -> None:
        if self._event_bus is None:
            return
        pair = tuple(sorted((int(entity.id), int(other.id))))
        if pair in self._emitted_contacts:
            return
        self._emitted_contacts.add(pair)
        self._event_bus.emit(
            "on_collision",
            {
                "entity_a": entity.name,
                "entity_b": other.name,
                "entity_a_id": int(entity.id),
                "entity_b_id": int(other.id),
                "is_trigger": False,
            },
        )
