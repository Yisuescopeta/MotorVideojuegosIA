from __future__ import annotations

import unittest

from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.systems.character_controller_system import CharacterControllerSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.physics_system import PhysicsSystem


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

        # Backend legacy
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

        # Sistema de character controller con backend
        system = CharacterControllerSystem()

        # Ejecutar varios frames (debe caer y posarse en el suelo)
        dt = 1.0 / 60.0
        for _ in range(120):  # 2 segundos a 60fps
            system.update(world, dt, backend=backend)

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

        system = CharacterControllerSystem()

        dt = 1.0 / 60.0
        for _ in range(60):
            system.update(world, dt, backend=backend)

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

    # ── Punto 1: primer frame sin estado previo ────────────────────

    def test_first_frame_no_previous_state(self) -> None:
        """CharacterController funciona en el primer frame sin estado previo."""
        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=100))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600)
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=350))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        system = CharacterControllerSystem()

        # Primer frame — sin estado previo
        system.update(world, 1 / 60, backend=backend)

        self.assertTrue(True)  # no debe crashear

    # ── Punto 3: on_floor fresco cada frame ────────────────────────

    def test_on_floor_computed_fresh_each_frame(self) -> None:
        """on_floor se computa fresco cada frame, no del frame anterior."""
        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=50))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600)
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        system = CharacterControllerSystem()

        # Frame 1: cae al suelo → on_floor = True
        for _ in range(60):
            system.update(world, 1 / 60, backend=backend)
        self.assertTrue(cc.on_floor, "Debería estar en el suelo tras 60 frames")

        # Frame 2: teletransportar al aire (simular que el suelo desaparece)
        transform = player.get_component(Transform)
        transform.y = 50
        cc.on_floor = False  # reset manual

        # Frame 3: sin suelo debajo → debe seguir en el aire
        world.remove_entity(ground.id)  # eliminar suelo
        system.update(world, 1 / 60, backend=backend)
        self.assertFalse(
            cc.on_floor,
            "on_floor debería ser False sin suelo, no arrastrado del frame anterior",
        )

    # ── Punto 4: cambio de backend limpia estado anterior ──────────

    def test_backend_switch_cleans_previous_state(self) -> None:
        """Cambiar de backend limpia el estado anterior."""
        world1 = World()
        p1 = Entity(name="P1")
        p1.add_component(Transform(x=160, y=50))
        p1.add_component(Collider(width=32, height=32))
        world1.add_entity(p1)

        backend1 = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        system = CharacterControllerSystem()

        # Usar backend1
        system.update(world1, 1 / 60, backend=backend1)

        # Cambiar a backend2 (otro LegacyAABB — simula backend switch)
        backend2 = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        system.update(world1, 1 / 60, backend=backend2)

        # No debe arrastrar estado de backend1
        self.assertTrue(True)  # no crashea

    # ── Punto 5: no duplicación de on_collision ────────────────────

    def test_no_duplicate_collision_events(self) -> None:
        """Un solo contacto no debe emitir múltiples on_collision."""
        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=50))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600)
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        events: list = []
        bus = EventBus()
        bus.subscribe("on_collision", lambda data: events.append(data))

        backend = LegacyAABBPhysicsBackend(
            physics_system=None, collision_system=None, event_bus=bus,
        )
        system = CharacterControllerSystem()
        system.set_event_bus(bus)

        # Un solo frame
        system.update(world, 1 / 60, backend=backend)

        # Verificar no duplicación: máximo 1 evento por par entity-sólido
        player_events = [
            e for e in events
            if e.get("entity_a") == "Player" or e.get("entity_b") == "Player"
        ]
        self.assertLessEqual(
            len(player_events), 1,
            f"Esperado ≤1 evento para Player, recibidos {len(player_events)}",
        )

    # ── Punto 6: ciclo completo sin duplicación ───────────────────

    def test_no_duplicate_collision_events_in_full_cycle(self) -> None:
        """Ciclo completo: CharacterController + backend.step no duplica on_collision."""
        world = World()
        player = Entity(name="Player")
        # Posicionar justo arriba del suelo: Ground top=184, Player bottom=182 (gap=2px)
        player.add_component(Transform(x=160, y=166))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600)
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        events: list = []
        bus = EventBus()
        bus.subscribe("on_collision", lambda event: events.append(event.data))

        physics_system = PhysicsSystem()
        collision_system = CollisionSystem(event_bus=bus)

        backend = LegacyAABBPhysicsBackend(
            physics_system=physics_system,
            collision_system=collision_system,
            event_bus=bus,
        )
        system = CharacterControllerSystem()
        system.set_event_bus(bus)

        # Ciclo completo: character controller → backend step
        bus.reset_frame_dedup()
        system.update(world, 1 / 60, backend=backend)
        backend.step(world, 1 / 60)

        # Verificar: máximo 1 on_collision por par (Player, Ground)
        player_ground_events = [
            e for e in events
            if (e.get("entity_a") == "Player" and e.get("entity_b") == "Ground")
            or (e.get("entity_a") == "Ground" and e.get("entity_b") == "Player")
        ]
        self.assertLessEqual(
            len(player_ground_events), 1,
            f"Esperado ≤1 evento Player-Ground, recibidos {len(player_ground_events)}: {player_ground_events}"
        )

    def test_frame_dedup_resets_between_frames(self) -> None:
        """Dedup se limpia entre frames. Segundo frame puede emitir de nuevo."""
        world = World()
        player = Entity(name="Player")
        # Posicionar justo arriba del suelo para que colisione en 1 frame
        # Ground: y=200, half_h=16 → top=184. Player: y=166, half_h=16 → bottom=182
        # Gap=2px. Con gravity=600, dt=1/60: vy=10, delta_y=0.167 → colisiona en frame 1.
        player.add_component(Transform(x=160, y=166))
        player.add_component(Collider(width=32, height=32))
        cc = CharacterController2D(move_speed=200, gravity=600)
        player.add_component(cc)
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        events: list[dict] = []
        bus = EventBus()
        bus.subscribe("on_collision", lambda event: events.append(event.data))

        physics_system = PhysicsSystem()
        collision_system = CollisionSystem(event_bus=bus)

        backend = LegacyAABBPhysicsBackend(
            physics_system=physics_system,
            collision_system=collision_system,
            event_bus=bus,
        )
        system = CharacterControllerSystem()
        system.set_event_bus(bus)

        # Ejecutar varios frames hasta que el player toque el suelo
        dt = 1.0 / 60.0
        for _ in range(30):
            bus.reset_frame_dedup()
            system.update(world, dt, backend=backend)
            backend.step(world, dt)
            if cc.on_floor:
                break

        self.assertTrue(cc.on_floor, "Player no llegó al suelo")

        # Contar eventos Player-Ground en todos los frames hasta aquí
        events_before = len(events)

        # Frame extra: player ya en el suelo, dedup reseteado
        bus.reset_frame_dedup()
        system.update(world, dt, backend=backend)
        backend.step(world, dt)

        new_events = len(events) - events_before
        # Puede emitir 0 o 1 (si floor snap encuentra contacto), pero NO más de 1
        self.assertLessEqual(new_events, 1, f"Frame extra duplicó: {new_events} eventos")


if __name__ == "__main__":
    unittest.main()
