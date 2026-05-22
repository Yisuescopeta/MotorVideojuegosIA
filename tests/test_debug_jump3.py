"""Debug test v3 - direct with internal prints."""
from __future__ import annotations

import unittest

from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.backend import MoveResult2D
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.systems.character_controller_system import CharacterControllerSystem


class DebugJumpV3Tests(unittest.TestCase):
    def test_jump_trace(self):
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

        dt = 1.0 / 60.0
        # Land first
        for _ in range(30):
            system.update(world, dt, backend=backend)

        y_before = player.get_component(Transform).y
        print(f"\nBefore jump: y={y_before:.6f}, on_floor={cc.on_floor}")

        # Directly call move_and_slide to see result
        cc.velocity_y = cc.jump_velocity
        cc.on_floor = False
        cc.velocity_y = min(cc.max_fall_speed, cc.velocity_y + cc.gravity * dt)

        print(f"  vy after gravity={cc.velocity_y:.2f}, on_floor={cc.on_floor}")
        print(f"  entity._move_slide_was_on_floor = {getattr(player, '_move_slide_was_on_floor', 'N/A')}")

        result: MoveResult2D = backend.move_and_slide(
            world=world, entity=player,
            velocity=(cc.velocity_x, cc.velocity_y),
            delta_time=dt,
            floor_max_angle=cc.floor_max_angle,
            floor_snap_distance=cc.floor_snap_distance,
            up_direction=(cc.up_direction_x, cc.up_direction_y),
            wall_min_slide_angle=cc.wall_min_slide_angle,
            floor_stop_on_slope=cc.floor_stop_on_slope,
            max_slides=cc.max_slides,
        )

        print(f"  Result: pos=({result.position_x:.4f},{result.position_y:.4f}), "
              f"on_floor={result.on_floor}, on_ceiling={result.on_ceiling}, "
              f"on_wall={result.on_wall}, vy={result.velocity_y:.2f}")
        print(f"  entity._move_slide_was_on_floor after = {getattr(player, '_move_slide_was_on_floor', 'N/A')}")
        print(f"  Transform after: y={player.get_component(Transform).y:.6f}")

        self.assertEqual(result.on_ceiling, False,
                         f"Esperaba no ceiling; normal={result.collision_normal_x},{result.collision_normal_y}")
        self.assertLess(result.position_y, y_before,
                        f"No cambio en y: antes={y_before}, despues={result.position_y}")


if __name__ == "__main__":
    unittest.main()
