from __future__ import annotations

import math
from typing import Any, Optional

from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.collision_filter_2d import CollisionFilter2D
from engine.components.inputmap import InputMap
from engine.components.rigidbody import RigidBody
from engine.components.static_body_2d import StaticBody2D
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend


class CharacterControllerSystem:
    """Ejecuta movimiento de personaje data-driven sin depender del editor."""

    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._emitted_contacts: set[tuple[int, int]] = set()
        from engine.physics.kinematic_move_service import PhysicsKinematicMoveService
        self._move_service = PhysicsKinematicMoveService()

    def set_event_bus(self, event_bus: Optional[Any]) -> None:
        self._event_bus = event_bus

    def update(self, world: World, delta_time: float, backend: Any = None) -> None:
        self._emitted_contacts = set()
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
            if backend is None:
                backend = LegacyAABBPhysicsBackend(None, None)
            self._move_with_service(backend, world, entity, transform, collider, controller, float(delta_time))

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

    def _move_entity_legacy(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        controller: CharacterController2D,
        solids: list[Entity],
        delta_time: float,
    ) -> None:
        """[DEPRECATED] Legacy per-axis sweep path. No longer called directly.

        Kept for backward compatibility with external code that may reference this method.
        PhysicsKinematicMoveService via LegacyAABBPhysicsBackend is now the unified path.
        """
        controller._was_on_floor = controller.on_floor
        controller.on_wall = False
        controller.on_ceiling = False

        # Apply platform velocity before sweeps
        transform.x += controller.platform_velocity_x
        transform.y += controller.platform_velocity_y
        controller.platform_velocity_x = 0.0
        controller.platform_velocity_y = 0.0

        if not controller.on_floor:
            controller.velocity_y = min(controller.max_fall_speed, controller.velocity_y + controller.gravity * delta_time)

        delta_x = controller.velocity_x * delta_time
        transform.x += self._sweep_horizontal(world, entity, transform, collider, controller, solids, delta_x)

        controller.on_floor = False
        delta_y = controller.velocity_y * delta_time
        transform.y += self._sweep_vertical(world, entity, transform, collider, controller, solids, delta_y)

        if controller._was_on_floor and not controller.on_floor and controller.floor_snap_distance > 0.0:
            snap_distance = self._floor_snap(world, entity, transform, collider, controller, solids)
            if snap_distance is not None:
                transform.y += snap_distance
                controller.on_floor = True
                # Verify snap with vertical sweep
                verify_delta = min(0.0, snap_distance + 0.01)
                self._sweep_vertical(world, entity, transform, collider, controller, solids, verify_delta)

        controller.slide_collisions.clear()

    def _move_with_service(
        self,
        backend: Any,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        controller: CharacterController2D,
        delta_time: float,
    ) -> None:
        """Usa PhysicsKinematicMoveService como fachada entre CharacterController y backend."""
        was_on_floor = controller.on_floor

        # Aplicar platform velocity antes del movimiento
        transform.x += controller.platform_velocity_x
        transform.y += controller.platform_velocity_y
        controller.platform_velocity_x = 0.0
        controller.platform_velocity_y = 0.0

        # Apply platform velocity from tracked platform entity
        if controller.platform_entity_name:
            platform_e = world.get_entity_by_name(controller.platform_entity_name)
            if platform_e is not None:
                pv_x, pv_y = 0.0, 0.0
                platform_sb = platform_e.get_component(StaticBody2D) if hasattr(platform_e, "get_component") else None
                if platform_sb is not None:
                    pv_x = platform_sb.constant_linear_velocity_x
                    pv_y = platform_sb.constant_linear_velocity_y
                else:
                    platform_rb = platform_e.get_component(RigidBody) if hasattr(platform_e, "get_component") else None
                    if platform_rb is not None:
                        pv_x = platform_rb.velocity_x
                        pv_y = platform_rb.velocity_y
                if pv_x != 0.0 or pv_y != 0.0:
                    transform.x += pv_x * delta_time
                    transform.y += pv_y * delta_time

        # Calcular velocidad (gravedad + input)
        if not controller.on_floor:
            controller.velocity_y = min(
                controller.max_fall_speed,
                controller.velocity_y + controller.gravity * delta_time,
            )

        # Llamar al servicio según move_mode
        if controller.move_mode == "move_and_collide":
            result = self._move_service.move_and_collide(
                backend=backend,
                world=world,
                entity=entity,
                velocity=(controller.velocity_x, controller.velocity_y),
                delta_time=delta_time,
            )
        else:
            result = self._move_service.move_and_slide(
                backend=backend,
                world=world,
                entity=entity,
                velocity=(controller.velocity_x, controller.velocity_y),
                delta_time=delta_time,
                floor_max_angle=controller.floor_max_angle,
                floor_snap_distance=controller.floor_snap_distance,
                up_direction=(controller.up_direction_x, controller.up_direction_y),
                wall_min_slide_angle=controller.wall_min_slide_angle,
                floor_stop_on_slope=controller.floor_stop_on_slope,
                max_slides=controller.max_slides,
            )

        # Aplicar resultado al Transform
        transform.x = result.position_x
        transform.y = result.position_y

        # Copiar estado a CharacterController2D
        controller.velocity_x = result.velocity_x
        controller.velocity_y = result.velocity_y
        controller.on_floor = result.on_floor
        controller.on_wall = result.on_wall
        controller.on_ceiling = result.on_ceiling
        controller.collision_normal_x = result.collision_normal_x
        controller.collision_normal_y = result.collision_normal_y
        controller._was_on_floor = was_on_floor

        # Track platform entity from move result
        if result.on_floor and result.platform_entity_id > 0:
            platform_e = world.get_entity(result.platform_entity_id)
            if platform_e is not None:
                controller.platform_entity_name = str(platform_e.name) if hasattr(platform_e, "name") else ""
        elif not result.on_floor:
            controller.platform_entity_name = ""

        # platform_on_leave: apply velocity when leaving a moving platform
        if was_on_floor and not result.on_floor and controller.platform_entity_name:
            leave_platform = world.get_entity_by_name(controller.platform_entity_name)
            if leave_platform is not None:
                lv_x, lv_y = 0.0, 0.0
                lp_sb = leave_platform.get_component(StaticBody2D) if hasattr(leave_platform, "get_component") else None
                if lp_sb is not None:
                    lv_x = lp_sb.constant_linear_velocity_x
                    lv_y = lp_sb.constant_linear_velocity_y
                else:
                    lp_rb = leave_platform.get_component(RigidBody) if hasattr(leave_platform, "get_component") else None
                    if lp_rb is not None:
                        lv_x = lp_rb.velocity_x
                        lv_y = lp_rb.velocity_y
                if controller.platform_on_leave == "add_velocity":
                    controller.velocity_x += lv_x
                    controller.velocity_y += lv_y
                elif controller.platform_on_leave == "add_upward_velocity":
                    controller.velocity_y += lv_y
            controller.platform_entity_name = ""

        # Emitir eventos de contacto
        for contact in result.contacts:
            other_name = contact.entity_b if contact.entity_a == entity.name else contact.entity_a
            other_id = contact.entity_b_id if contact.entity_a_id == int(entity.id) else contact.entity_a_id
            controller.last_hit_entity = other_name
            self._emit_collision_manual(entity, other_name, int(entity.id), int(other_id))

        controller.slide_collisions.clear()

    def _emit_collision_manual(self, entity: Entity, other_name: str, entity_id: int, other_id: int) -> None:
        if self._event_bus is None:
            return
        pair = (min(entity_id, other_id), max(entity_id, other_id))
        if pair in self._emitted_contacts:
            return
        self._emitted_contacts.add(pair)
        self._event_bus.emit(
            "on_collision",
            {
                "entity_a": entity.name,
                "entity_b": other_name,
                "entity_a_id": entity_id,
                "entity_b_id": other_id,
                "is_trigger": False,
            },
        )

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
        """[DEPRECATED] Legacy horizontal sweep. Only referenced by _move_entity_legacy."""
        if abs(delta_x) <= 1e-6:
            return 0.0
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_x
        hit_entity: Entity | None = None
        for other in solids:
            if other.id == entity.id:
                continue
            if not self._can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            # Skip one-way platforms horizontally
            if other_collider.one_way_collision:
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
            nx = controller.collision_normal_x
            ny = 0.0
            collision_type = self._classify_collision(
                nx, ny, controller.up_direction_x, controller.up_direction_y,
                controller.floor_max_angle, controller.wall_min_slide_angle
            )
            if collision_type == "wall":
                controller.on_wall = True
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
        """[DEPRECATED] Legacy vertical sweep. Only referenced by _move_entity_legacy."""
        if abs(delta_y) <= 1e-6:
            return 0.0
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_y
        hit_entity: Entity | None = None
        for other in solids:
            if other.id == entity.id:
                continue
            if not self._can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            # One-way platform check
            if other_collider.one_way_collision:
                if delta_y < 0:
                    direction_check = other_collider.one_way_collision_direction_y
                    if direction_check < 0:
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
            nx = controller.collision_normal_x
            ny = controller.collision_normal_y
            collision_type = self._classify_collision(
                nx, ny, controller.up_direction_x, controller.up_direction_y,
                controller.floor_max_angle, controller.wall_min_slide_angle
            )
            if collision_type == "ceiling":
                controller.on_ceiling = True
            elif collision_type == "wall":
                controller.on_wall = True
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
            if not self._can_collide(world, entity, other):
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

    def _can_collide(self, world: World, entity: Entity, other: Entity) -> bool:
        cc_filter = entity.get_component(CollisionFilter2D)
        other_filter = other.get_component(CollisionFilter2D)
        if cc_filter is not None or other_filter is not None:
            if not CollisionFilter2D.should_collide(cc_filter, other_filter):
                return False
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{entity.layer}|{other.layer}", True))

    @staticmethod
    def _classify_collision(nx: float, ny: float, up_x: float, up_y: float, floor_max_angle: float, wall_min_slide_angle: float) -> str:
        dot = nx * up_x + ny * up_y
        angle = math.acos(max(-1.0, min(1.0, abs(dot))))
        if angle <= floor_max_angle:
            return "floor" if dot >= 0 else "ceiling"
        elif angle >= (math.pi / 2 - wall_min_slide_angle):
            return "wall"
        else:
            return "ceiling" if dot > 0 else "wall"

    def _emit_collision(self, entity: Entity, other: Entity) -> None:
        if self._event_bus is None:
            return
        entity_id = int(entity.id)
        other_id = int(other.id)
        pair = (min(entity_id, other_id), max(entity_id, other_id))
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
