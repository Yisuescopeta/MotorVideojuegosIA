"""Temporary debug test for jump behavior - minimal version."""
from __future__ import annotations

import unittest

from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.systems.character_controller_system import CharacterControllerSystem


class DebugJumpDirectTests(unittest.TestCase):
    def test_jump_moves_character_up_direct(self):
        """Direct test of CharacterControllerSystem jump - no EngineAPI."""
        world = World()

        player = Entity(name="Player")
        player.add_component(Transform(x=0, y=38))
        player.add_component(Collider(width=12, height=24))
        cc = CharacterController2D(
            move_speed=120, gravity=600, jump_velocity=-260,
            floor_snap_distance=2.0, use_input_map=False,
        )
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=0, y=60))
        ground.add_component(Collider(width=200, height=20))
        world.add_entity(ground)

        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        system = CharacterControllerSystem()

        # First frame: land on ground
        dt = 1.0 / 60.0
        for _ in range(30):
            system.update(world, dt, backend=backend)

        transform = player.get_component(Transform)
        y_before = transform.y
        print(f"Before jump: y={y_before:.6f}, on_floor={cc.on_floor}, vy={cc.velocity_y:.2f}")

        # Jump
        cc.velocity_y = cc.jump_velocity
        cc.on_floor = False
        entity_was = getattr(player, "_move_slide_was_on_floor", "N/A")
        print(f"  entity._move_slide_was_on_floor = {entity_was}")

        for i in range(4):
            system.update(world, dt, backend=backend)
            entity_was = getattr(player, "_move_slide_was_on_floor", "N/A")
            print(f"  Frame {i+1}: y={transform.y:.6f}, on_floor={cc.on_floor}, vy={cc.velocity_y:.2f}, was_on_floor={entity_was}")

        y_after = transform.y
        print(f"After 4 jump frames: y={y_after:.6f}, on_floor={cc.on_floor}, vy={cc.velocity_y:.2f}")

        self.assertLess(y_after, y_before, f"No salto: y_antes={y_before}, y_despues={y_after}")


if __name__ == "__main__":
    unittest.main()
