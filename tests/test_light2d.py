"""
tests/test_light2d.py - Tests para Light2D component y Light2DSystem
"""

import unittest

from engine.components.light2d import Light2D
from engine.components.transform import Transform
from engine.ecs.component import Component
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.light2d_system import Light2DSystem


class TestLight2DComponent(unittest.TestCase):
    def test_defaults(self):
        light = Light2D()
        self.assertTrue(light.enabled)
        self.assertEqual(light.color_r, 255)
        self.assertEqual(light.color_g, 255)
        self.assertEqual(light.color_b, 255)
        self.assertEqual(light.color_a, 200)
        self.assertEqual(light.energy, 1.0)
        self.assertEqual(light.radius, 100.0)
        self.assertEqual(light.falloff_type, "quadratic")
        self.assertEqual(light.blend_mode, "additive")
        self.assertEqual(light.z_index, 0)

    def test_custom_values(self):
        light = Light2D(
            color_r=100, color_g=50, color_b=200, color_a=128,
            energy=2.0, radius=50.0, falloff_type="linear",
            blend_mode="multiplied", z_index=5,
        )
        self.assertEqual(light.color_r, 100)
        self.assertEqual(light.color_g, 50)
        self.assertEqual(light.color_b, 200)
        self.assertEqual(light.color_a, 128)
        self.assertEqual(light.energy, 2.0)
        self.assertEqual(light.radius, 50.0)
        self.assertEqual(light.falloff_type, "linear")
        self.assertEqual(light.blend_mode, "multiplied")
        self.assertEqual(light.z_index, 5)

    def test_color_clamped(self):
        light = Light2D(color_r=300, color_g=-10, color_b=1000, color_a=-5)
        self.assertEqual(light.color_r, 255)
        self.assertEqual(light.color_g, 0)
        self.assertEqual(light.color_b, 255)
        self.assertEqual(light.color_a, 0)

    def test_energy_non_negative(self):
        light = Light2D(energy=-5.0)
        self.assertEqual(light.energy, 0.0)

    def test_radius_min_one(self):
        light = Light2D(radius=0.5)
        self.assertEqual(light.radius, 1.0)

    def test_to_dict(self):
        light = Light2D(color_r=255, energy=1.5, radius=80.0)
        d = light.to_dict()
        self.assertEqual(d["enabled"], True)
        self.assertEqual(d["color_r"], 255)
        self.assertEqual(d["energy"], 1.5)
        self.assertEqual(d["radius"], 80.0)
        self.assertEqual(d["falloff_type"], "quadratic")
        self.assertEqual(d["blend_mode"], "additive")
        self.assertEqual(d["z_index"], 0)

    def test_from_dict(self):
        data = {
            "enabled": False,
            "color_r": 128,
            "color_g": 64,
            "color_b": 32,
            "color_a": 255,
            "energy": 0.5,
            "radius": 200.0,
            "falloff_type": "constant",
            "blend_mode": "multiplied",
            "z_index": 3,
        }
        light = Light2D.from_dict(data)
        self.assertFalse(light.enabled)
        self.assertEqual(light.color_r, 128)
        self.assertEqual(light.color_g, 64)
        self.assertEqual(light.color_b, 32)
        self.assertEqual(light.color_a, 255)
        self.assertEqual(light.energy, 0.5)
        self.assertEqual(light.radius, 200.0)
        self.assertEqual(light.falloff_type, "constant")
        self.assertEqual(light.blend_mode, "multiplied")
        self.assertEqual(light.z_index, 3)

    def test_from_dict_partial(self):
        data = {"color_r": 100}
        light = Light2D.from_dict(data)
        self.assertEqual(light.color_r, 100)
        self.assertEqual(light.color_g, 255)  # default
        self.assertTrue(light.enabled)  # default

    def test_serialization_roundtrip(self):
        original = Light2D(
            color_r=200, color_g=100, color_b=50, color_a=220,
            energy=0.8, radius=150.0, falloff_type="linear", blend_mode="additive", z_index=2,
        )
        data = original.to_dict()
        restored = Light2D.from_dict(data)
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_is_component(self):
        light = Light2D()
        self.assertIsInstance(light, Component)


class TestLight2DRegistry(unittest.TestCase):
    def test_registry_contains_light2d(self):
        registry = create_default_registry()
        klass = registry.get("Light2D")
        self.assertIsNotNone(klass)
        self.assertTrue(issubclass(klass, Component))

    def test_registry_create_light2d(self):
        registry = create_default_registry()
        light = registry.create("Light2D", {"color_r": 200, "radius": 75.0})
        self.assertIsInstance(light, Light2D)
        self.assertEqual(light.color_r, 200)
        self.assertEqual(light.radius, 75.0)


class TestLight2DSystem(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.system = Light2DSystem()

    def _create_entity_with_light(self, name: str, light: Light2D | None = None,
                                   x: float = 0.0, y: float = 0.0,
                                   light_kwargs: dict | None = None) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        if light is not None:
            entity.add_component(light)
        elif light_kwargs is not None:
            entity.add_component(Light2D(**light_kwargs))
        else:
            entity.add_component(Light2D())

    def test_render_empty_world_no_crash(self):
        self.system.render(self.world)

    def test_render_no_lights_no_crash(self):
        entity = self.world.create_entity("no_light")
        entity.add_component(Transform())
        self.system.render(self.world)

    def test_disabled_light_skipped(self):
        light = Light2D()
        light.enabled = False
        self._create_entity_with_light("disabled_light", light=light)
        self.system.render(self.world)

    def test_light_without_transform_skipped(self):
        entity = self.world.create_entity("no_transform")
        entity.add_component(Light2D())
        self.system.render(self.world)

    def test_enabled_light_with_transform_renders(self):
        self._create_entity_with_light("lamp", x=100.0, y=200.0)
        self.system.render(self.world)

    def test_multiple_lights(self):
        self._create_entity_with_light("light1", x=0.0, y=0.0, light_kwargs={"z_index": 0})
        self._create_entity_with_light("light2", x=50.0, y=50.0, light_kwargs={"z_index": 1})
        self._create_entity_with_light("light3", x=-50.0, y=-50.0, light_kwargs={"z_index": -1})
        self.system.render(self.world)

    def test_disabled_transform_skipped(self):
        entity = self.world.create_entity("disabled_trans")
        transform = Transform(x=10, y=10)
        transform.enabled = False
        entity.add_component(transform)
        entity.add_component(Light2D())
        self.system.render(self.world)

    def test_z_index_sorting(self):
        self._create_entity_with_light("low", x=0, y=0, light_kwargs={"z_index": -10})
        self._create_entity_with_light("high", x=0, y=0, light_kwargs={"z_index": 10})
        self._create_entity_with_light("mid", x=0, y=0, light_kwargs={"z_index": 0})
        self.system.render(self.world)

    def test_all_falloff_types(self):
        for falloff in ("constant", "linear", "quadratic"):
            world = World()
            system = Light2DSystem()
            entity = world.create_entity(f"light_{falloff}")
            entity.add_component(Transform())
            entity.add_component(Light2D(falloff_type=falloff))
            system.render(world)

    def test_both_blend_modes(self):
        for blend in ("additive", "multiplied"):
            world = World()
            system = Light2DSystem()
            entity = world.create_entity(f"light_{blend}")
            entity.add_component(Transform())
            entity.add_component(Light2D(blend_mode=blend))
            system.render(world)


if __name__ == "__main__":
    unittest.main()
