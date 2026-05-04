"""
tests/test_light2d_occluders.py - Tests para LightOccluder2D y shadow casting en Light2DSystem
"""

import unittest

from engine.components.light2d import Light2D
from engine.components.light_occluder_2d import LightOccluder2D
from engine.components.transform import Transform
from engine.ecs.component import Component
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.light2d_system import Light2DSystem


class TestLightOccluder2DComponent(unittest.TestCase):
    def test_create_occluder_defaults(self):
        occluder = LightOccluder2D()
        self.assertTrue(occluder.enabled)
        self.assertEqual(occluder.shape, "box")
        self.assertEqual(occluder.width, 32.0)
        self.assertEqual(occluder.height, 32.0)
        self.assertEqual(occluder.points, [])

    def test_create_occluder_custom(self):
        occluder = LightOccluder2D(
            shape="box",
            enabled=False,
            width=64.0,
            height=48.0,
            points=[(0.0, 0.0), (10.0, 10.0)],
        )
        self.assertFalse(occluder.enabled)
        self.assertEqual(occluder.shape, "box")
        self.assertEqual(occluder.width, 64.0)
        self.assertEqual(occluder.height, 48.0)
        self.assertEqual(occluder.points, [(0.0, 0.0), (10.0, 10.0)])

    def test_invalid_shape_defaults_to_box(self):
        occluder = LightOccluder2D(shape="invalid_shape")
        self.assertEqual(occluder.shape, "box")

    def test_occluder_bounds_box(self):
        occluder = LightOccluder2D(shape="box", width=64.0, height=48.0)
        bounds = occluder.get_bounds(10.0, 20.0)
        self.assertEqual(bounds, (10.0, 20.0, 74.0, 68.0))

    def test_occluder_bounds_non_box_falls_back_to_box(self):
        """Shapes no válidas ('circle', 'polygon') caen a 'box' y usan dimensiones reales del occluder."""
        occluder = LightOccluder2D(shape="circle", width=100.0, height=200.0)
        self.assertEqual(occluder.shape, "box")
        bounds = occluder.get_bounds(5.0, 15.0)
        self.assertEqual(bounds, (5.0, 15.0, 105.0, 215.0))

    def test_occluder_serialization_roundtrip(self):
        original = LightOccluder2D(
            shape="box",
            enabled=False,
            width=128.0,
            height=64.0,
            points=[(1.0, 2.0)],
        )
        data = original.to_dict()
        restored = LightOccluder2D.from_dict(data)
        self.assertEqual(restored.enabled, original.enabled)
        self.assertEqual(restored.shape, original.shape)
        self.assertEqual(restored.width, original.width)
        self.assertEqual(restored.height, original.height)
        self.assertEqual(restored.points, original.points)

    def test_occluder_to_dict(self):
        occluder = LightOccluder2D(width=50.0, height=25.0)
        d = occluder.to_dict()
        self.assertEqual(d["enabled"], True)
        self.assertEqual(d["shape"], "box")
        self.assertEqual(d["width"], 50.0)
        self.assertEqual(d["height"], 25.0)
        self.assertEqual(d["points"], [])

    def test_occluder_from_dict_partial(self):
        data = {"width": 100.0}
        occluder = LightOccluder2D.from_dict(data)
        self.assertEqual(occluder.width, 100.0)
        self.assertEqual(occluder.height, 32.0)  # default
        self.assertTrue(occluder.enabled)  # default

    def test_occluder_is_component(self):
        occluder = LightOccluder2D()
        self.assertIsInstance(occluder, Component)


class TestLightOccluder2DSystem(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.system = Light2DSystem()

    def _create_entity_with_light(
        self,
        name: str,
        x: float = 0.0,
        y: float = 0.0,
        light: Light2D | None = None,
    ) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(light or Light2D())

    def _create_entity_with_occluder(
        self,
        name: str,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 32.0,
        height: float = 32.0,
        enabled: bool = True,
    ) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(
            LightOccluder2D(
                shape="box",
                width=width,
                height=height,
                enabled=enabled,
            )
        )

    def test_render_with_occluders_no_crash(self):
        self._create_entity_with_light("lamp", x=100, y=100)
        self._create_entity_with_occluder("wall", x=200, y=200, width=64, height=64)
        self.system.render(self.world)

    def test_occluder_disabled_does_not_block(self):
        self._create_entity_with_light("lamp", x=50, y=50)
        self._create_entity_with_occluder(
            "wall", x=50, y=50, width=64, height=64, enabled=False
        )
        self.system.render(self.world)

    def test_occluder_point_occluded(self):
        system = Light2DSystem()
        occluder = LightOccluder2D(shape="box", width=64, height=48)
        transform = Transform(x=10, y=20)
        occluders: list[tuple[LightOccluder2D, Transform]] = [(occluder, transform)]

        self.assertTrue(system._is_point_occluded(30.0, 40.0, occluders))
        self.assertTrue(system._is_point_occluded(10.0, 20.0, occluders))
        self.assertTrue(system._is_point_occluded(74.0, 68.0, occluders))

        self.assertFalse(system._is_point_occluded(5.0, 20.0, occluders))
        self.assertFalse(system._is_point_occluded(10.0, 5.0, occluders))
        self.assertFalse(system._is_point_occluded(80.0, 80.0, occluders))

    def test_occluder_point_not_occluded_empty_list(self):
        system = Light2DSystem()
        self.assertFalse(system._is_point_occluded(50.0, 50.0, []))


class TestLightOccluder2DRegistry(unittest.TestCase):
    def test_registry_contains_light_occluder(self):
        registry = create_default_registry()
        klass = registry.get("LightOccluder2D")
        self.assertIsNotNone(klass)
        self.assertTrue(issubclass(klass, Component))

    def test_registry_create_light_occluder(self):
        registry = create_default_registry()
        occluder = registry.create(
            "LightOccluder2D",
            {"shape": "box", "width": 100.0, "height": 50.0},
        )
        self.assertIsInstance(occluder, LightOccluder2D)
        self.assertEqual(occluder.shape, "box")
        self.assertEqual(occluder.width, 100.0)
        self.assertEqual(occluder.height, 50.0)

    def test_registry_list_includes_occluder(self):
        registry = create_default_registry()
        names = registry.list_registered()
        self.assertIn("LightOccluder2D", names)


if __name__ == "__main__":
    unittest.main()
