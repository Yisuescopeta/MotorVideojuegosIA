from __future__ import annotations

import unittest

from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.systems.character_controller_system import CharacterControllerSystem


class CharacterControllerBackendIntegrationTests(unittest.TestCase):

    def test_character_controller_uses_backend_move_and_slide(self) -> None:
        """Player con CharacterController2D + backend no atraviesa el suelo."""
        world = World()

        # Player: cae sobre el suelo
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=100))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600, jump_velocity=-320)
        player.add_component(cc)
        world.add_entity(player)

        # Suelo
        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=350))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        # Backend legacy — debe conocer el mundo para el sweep
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        backend._last_world = world

        # Sistema de character controller con backend
        system = CharacterControllerSystem()
        system.set_physics_backend(backend)

        # Ejecutar varios frames (debe caer y posarse en el suelo)
        dt = 1.0 / 60.0
        for _ in range(120):  # 2 segundos a 60fps
            system.update(world, dt)

        transform = player.get_component(Transform)
        expected_bottom = 350.0 - 16.0  # top del suelo (y=350, half_h=16 → top=334)
        player_bottom = transform.y + 16.0  # centro + half height

        self.assertLessEqual(
            player_bottom,
            expected_bottom + 1.0,
            f"Player atravesó el suelo: bottom={player_bottom}, suelo_top={expected_bottom}",
        )
        self.assertTrue(cc.on_floor, "Player debería estar en el suelo")
        self.assertGreaterEqual(
            cc.velocity_y,
            -1.0,
            f"Velocidad vertical debería ser ~0, es {cc.velocity_y}",
        )

    def test_character_controller_without_backend_uses_legacy(self) -> None:
        """Sin backend, el código legacy de sweeps AABB debe funcionar igual."""
        world = World()

        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=100))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600, jump_velocity=-320)
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=350))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        # Sin backend (legacy)
        system = CharacterControllerSystem()

        dt = 1.0 / 60.0
        for _ in range(120):
            system.update(world, dt)

        transform = player.get_component(Transform)
        expected_bottom = 350.0 - 16.0
        player_bottom = transform.y + 16.0

        self.assertLessEqual(player_bottom, expected_bottom + 1.0)
        self.assertTrue(cc.on_floor)

    def test_character_controller_wall_collision_with_backend(self) -> None:
        """Player se mueve hacia pared y se detiene usando backend."""
        world = World()

        player = Entity(name="Player")
        player.add_component(Transform(x=100, y=100))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=0, jump_velocity=-320)
        cc.velocity_x = 200  # moviendo a la derecha
        player.add_component(cc)
        world.add_entity(player)

        wall = Entity(name="Wall")
        wall.add_component(Transform(x=200, y=100))
        wall.add_component(Collider(width=32, height=128))
        world.add_entity(wall)

        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        backend._last_world = world

        system = CharacterControllerSystem()
        system.set_physics_backend(backend)

        dt = 1.0 / 60.0
        for _ in range(60):
            system.update(world, dt)

        transform = player.get_component(Transform)
        # Player no debe atravesar la pared
        player_right = transform.x + 16.0
        wall_left = 200.0 - 16.0
        self.assertLessEqual(
            player_right,
            wall_left + 1.0,
            f"Player atravesó pared: right={player_right}, wall_left={wall_left}",
        )
        self.assertTrue(
            cc.on_wall or cc.velocity_x == 0.0,
            "Player debería estar en pared o detenido",
        )
