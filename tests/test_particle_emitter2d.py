"""
tests/test_particle_emitter2d.py - Tests para ParticleEmitter2D y ParticleSystem.
"""

import unittest

from engine.components.particle_emitter2d import ColorRampStop, ParticleEmitter2D
from engine.components.transform import Transform
from engine.ecs.component import Component
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.particle_system import ParticleSystem


class TestParticleEmitter2DComponent(unittest.TestCase):
    def test_defaults(self):
        emitter = ParticleEmitter2D()
        self.assertTrue(emitter.enabled)
        self.assertTrue(emitter.emitting)
        self.assertEqual(emitter.amount, 64)
        self.assertEqual(emitter.lifetime, 1.0)
        self.assertEqual(emitter.lifetime_randomness, 0.0)
        self.assertEqual(emitter.speed_scale, 1.0)
        self.assertEqual(emitter.explosiveness, 0.0)
        self.assertFalse(emitter.one_shot)
        self.assertEqual(emitter.emission_shape, "point")
        self.assertEqual(emitter.color, (255, 255, 255, 255))
        self.assertEqual(emitter.gravity, (0.0, 0.0))
        self.assertEqual(emitter.direction, (1.0, 0.0))
        self.assertEqual(emitter.spread, 45.0)

    def test_custom_values(self):
        emitter = ParticleEmitter2D(
            amount=100, lifetime=2.0, one_shot=True,
            emission_shape="sphere", spread=90.0,
            color=(255, 0, 0, 128),
            gravity=(0.0, 500.0),
        )
        self.assertEqual(emitter.amount, 100)
        self.assertEqual(emitter.lifetime, 2.0)
        self.assertTrue(emitter.one_shot)
        self.assertEqual(emitter.emission_shape, "sphere")
        self.assertEqual(emitter.spread, 90.0)
        self.assertEqual(emitter.color, (255, 0, 0, 128))
        self.assertEqual(emitter.gravity, (0.0, 500.0))

    def test_explosiveness_clamped(self):
        emitter = ParticleEmitter2D(explosiveness=2.0)
        self.assertEqual(emitter.explosiveness, 1.0)
        emitter2 = ParticleEmitter2D(explosiveness=-0.5)
        self.assertEqual(emitter2.explosiveness, 0.0)

    def test_color_clamped(self):
        emitter = ParticleEmitter2D(color=(300, -10, 1000, 300))
        self.assertEqual(emitter.color, (255, 0, 255, 255))

    def test_to_dict(self):
        emitter = ParticleEmitter2D(amount=50, lifetime=1.5, spread=30.0)
        d = emitter.to_dict()
        self.assertEqual(d["enabled"], True)
        self.assertEqual(d["emitting"], True)
        self.assertEqual(d["amount"], 50)
        self.assertEqual(d["lifetime"], 1.5)
        self.assertEqual(d["spread"], 30.0)
        self.assertEqual(d["emission_shape"], "point")
        self.assertIn("color", d)
        self.assertIn("gravity", d)
        self.assertIn("texture", d)

    def test_from_dict(self):
        data = {
            "enabled": False,
            "emitting": True,
            "amount": 20,
            "lifetime": 0.5,
            "one_shot": True,
            "emission_shape": "rectangle",
            "emission_rect_extents": [10.0, 5.0],
            "direction": [0.0, -1.0],
            "spread": 10.0,
            "color": [100, 200, 50, 255],
            "gravity": [0.0, -200.0],
        }
        emitter = ParticleEmitter2D.from_dict(data)
        self.assertFalse(emitter.enabled)
        self.assertTrue(emitter.emitting)
        self.assertEqual(emitter.amount, 20)
        self.assertEqual(emitter.lifetime, 0.5)
        self.assertTrue(emitter.one_shot)
        self.assertEqual(emitter.emission_shape, "rectangle")
        self.assertEqual(emitter.emission_rect_extents, (10.0, 5.0))
        self.assertEqual(emitter.direction, (0.0, -1.0))
        self.assertEqual(emitter.spread, 10.0)
        self.assertEqual(emitter.color, (100, 200, 50, 255))
        self.assertEqual(emitter.gravity, (0.0, -200.0))

    def test_from_dict_partial(self):
        data = {"amount": 10}
        emitter = ParticleEmitter2D.from_dict(data)
        self.assertEqual(emitter.amount, 10)
        self.assertEqual(emitter.lifetime, 1.0)
        self.assertTrue(emitter.enabled)

    def test_serialization_roundtrip(self):
        original = ParticleEmitter2D(
            amount=30, lifetime=2.0, one_shot=True,
            emission_shape="sphere", emission_sphere_radius=5.0,
            direction=(0.0, 1.0), spread=60.0,
            initial_velocity=(10.0, 50.0),
            color=(255, 128, 0, 200), gravity=(0.0, 300.0),
        )
        data = original.to_dict()
        restored = ParticleEmitter2D.from_dict(data)
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_is_component(self):
        emitter = ParticleEmitter2D()
        self.assertIsInstance(emitter, Component)

    def test_texture_reference(self):
        emitter = ParticleEmitter2D(texture="sprites/fire.png")
        ref = emitter.get_texture_reference()
        self.assertEqual(ref["path"], "sprites/fire.png")
        self.assertEqual(emitter.texture_path, "sprites/fire.png")

    def test_texture_reference_sync(self):
        emitter = ParticleEmitter2D()
        emitter.sync_texture_reference({"path": "sprites/smoke.png", "guid": "abc123"})
        self.assertEqual(emitter.texture_path, "sprites/smoke.png")
        ref = emitter.get_texture_reference()
        self.assertEqual(ref["path"], "sprites/smoke.png")
        self.assertEqual(ref["guid"], "abc123")

    def test_color_ramp_roundtrip(self):
        emitter = ParticleEmitter2D(
            color_ramp=[
                ColorRampStop(0.0, (255, 0, 0, 255)),
                ColorRampStop(0.5, (0, 255, 0, 128)),
                ColorRampStop(1.0, (0, 0, 255, 255)),
            ]
        )
        d = emitter.to_dict()
        self.assertIn("color_ramp", d)
        restored = ParticleEmitter2D.from_dict(d)
        self.assertEqual(len(restored.color_ramp), 3)
        self.assertEqual(restored.color_ramp[0].position, 0.0)
        self.assertEqual(restored.color_ramp[0].color, (255, 0, 0, 255))


class TestParticleEmitter2DRegistry(unittest.TestCase):
    def test_registry_contains_particle_emitter2d(self):
        registry = create_default_registry()
        klass = registry.get("ParticleEmitter2D")
        self.assertIsNotNone(klass)
        self.assertTrue(issubclass(klass, Component))

    def test_registry_create_particle_emitter2d(self):
        registry = create_default_registry()
        emitter = registry.create("ParticleEmitter2D", {"amount": 80, "lifetime": 0.5})
        self.assertIsInstance(emitter, ParticleEmitter2D)
        self.assertEqual(emitter.amount, 80)
        self.assertEqual(emitter.lifetime, 0.5)


class TestParticleSystem(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.system = ParticleSystem()

    def _create_emitter_entity(self, name="emitter", x=0.0, y=0.0, **kwargs):
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(ParticleEmitter2D(**kwargs))
        return entity

    def test_update_empty_world_no_crash(self):
        self.system.update(self.world, 0.016)

    def test_update_disabled_emitter_no_crash(self):
        entity = self.world.create_entity("off")
        entity.add_component(Transform())
        emitter = ParticleEmitter2D()
        emitter.enabled = False
        entity.add_component(emitter)
        self.system.update(self.world, 0.016)
        self.assertEqual(self.system.active_particle_count, 0)

    def test_update_without_transform_skipped(self):
        entity = self.world.create_entity("no_transform")
        entity.add_component(ParticleEmitter2D())
        self.system.update(self.world, 0.016)
        self.assertEqual(self.system.active_particle_count, 0)

    def test_emitting_creates_particles(self):
        self._create_emitter_entity(amount=20, lifetime=1.0, speed_scale=1.0)
        for _ in range(60):
            self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)

    def test_particles_have_lifetime(self):
        self._create_emitter_entity(amount=10, lifetime=0.1, speed_scale=1.0)
        for _ in range(10):
            self.system.update(self.world, 0.016)
        self.assertGreater(self.system.total_particle_count, 0)

    def test_particles_expire(self):
        self._create_emitter_entity("expire", amount=10, lifetime=0.05, one_shot=True)
        self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)
        for _ in range(30):
            self.system.update(self.world, 0.016)
        self.assertEqual(self.system.active_particle_count, 0)

    def test_one_shot_event(self):
        events = []
        from engine.events.event_bus import EventBus
        bus = EventBus()
        bus.subscribe("on_particle_finished", lambda e: events.append(e.data))
        self.system = ParticleSystem(event_bus=bus)

        self._create_emitter_entity("event_test", x=0, y=0, amount=3, lifetime=0.02, one_shot=True)
        for _ in range(100):
            self.system.update(self.world, 0.016)
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[0]["entity"], "event_test")

    def test_explosiveness_all_at_once(self):
        self._create_emitter_entity("burst", amount=30, lifetime=1.0, explosiveness=1.0, speed_scale=1.0)
        self.system.update(self.world, 0.016)
        self.assertGreater(self.system.total_particle_count, 0)

    def test_preprocess(self):
        self._create_emitter_entity("pre", amount=10, lifetime=0.5, preprocess=0.1)
        self.system.update(self.world, 0.016)
        self.assertGreater(self.system.total_particle_count, 0)

    def test_render_no_crash(self):
        self._create_emitter_entity(amount=5, lifetime=0.5)
        for _ in range(10):
            self.system.update(self.world, 0.016)
        self.system.render(self.world)

    def test_clear(self):
        self._create_emitter_entity(amount=20, lifetime=1.0)
        for _ in range(10):
            self.system.update(self.world, 0.016)
        self.assertGreater(self.system.total_particle_count, 0)
        self.system.clear()
        self.assertEqual(self.system.active_particle_count, 0)
        self.assertEqual(self.system.total_particle_count, 0)

    def test_not_emitting(self):
        self._create_emitter_entity("quiet", amount=50, lifetime=1.0, emitting=False)
        for _ in range(30):
            self.system.update(self.world, 0.016)
        self.assertEqual(self.system.active_particle_count, 0)

    def test_emission_shapes(self):
        for shape in ("point", "rectangle", "sphere", "sphere_surface"):
            w = World()
            sys = ParticleSystem()
            ent = w.create_entity(f"shape_{shape}")
            ent.add_component(Transform())
            ent.add_component(ParticleEmitter2D(
                emission_shape=shape, amount=5, lifetime=0.1,
                emission_rect_extents=(10.0, 5.0),
                emission_sphere_radius=5.0,
            ))
            for _ in range(5):
                sys.update(w, 0.016)

    def test_multiple_emitters(self):
        self._create_emitter_entity("e1", x=-50, amount=10, lifetime=0.5)
        self._create_emitter_entity("e2", x=50, amount=10, lifetime=0.5)
        for _ in range(30):
            self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)

    def test_disabled_transform_skipped(self):
        entity = self.world.create_entity("off_trans")
        t = Transform()
        t.enabled = False
        entity.add_component(t)
        entity.add_component(ParticleEmitter2D(amount=10, lifetime=0.5))
        for _ in range(10):
            self.system.update(self.world, 0.016)
        self.assertEqual(self.system.active_particle_count, 0)

    def test_gravity_affects_particles(self):
        self._create_emitter_entity("grav", amount=10, lifetime=2.0,
            initial_velocity=(0.0, 0.0), gravity=(0.0, 500.0))
        for _ in range(20):
            self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)

    def test_color_ramp_sampling(self):
        ramp = [
            ColorRampStop(0.0, (255, 0, 0, 255)),
            ColorRampStop(1.0, (0, 0, 255, 255)),
        ]
        c = ParticleSystem.sample_ramp(ramp, 0.0)
        self.assertEqual(c, (255, 0, 0, 255))
        c = ParticleSystem.sample_ramp(ramp, 1.0)
        self.assertEqual(c, (0, 0, 255, 255))
        c = ParticleSystem.sample_ramp(ramp, 0.5)
        self.assertEqual(c, (127, 0, 127, 255))

    def test_empty_ramp_returns_none(self):
        c = ParticleSystem.sample_ramp([], 0.5)
        self.assertIsNone(c)


if __name__ == "__main__":
    unittest.main()
