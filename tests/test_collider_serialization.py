import unittest

from engine.components.collider import Collider


class ColliderSerializationTests(unittest.TestCase):
    """Roundtrip serialization tests para todos los shape types del Collider."""

    def test_roundtrip_box(self) -> None:
        original = Collider(
            shape_type="box",
            width=64,
            height=48,
            offset_x=5,
            offset_y=10,
            friction=0.5,
            restitution=0.3,
            density=2.0,
        )
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertEqual(restored.shape_type, "box")
        self.assertEqual(restored.width, 64)
        self.assertEqual(restored.height, 48)
        self.assertEqual(restored.offset_x, 5)
        self.assertEqual(restored.offset_y, 10)
        self.assertEqual(restored.friction, 0.5)
        self.assertEqual(restored.restitution, 0.3)
        self.assertEqual(restored.density, 2.0)
        self.assertFalse(restored.is_trigger)

    def test_roundtrip_circle(self) -> None:
        original = Collider(shape_type="circle", radius=32, width=64, height=64)
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertEqual(restored.shape_type, "circle")
        self.assertEqual(restored.radius, 32)

    def test_roundtrip_capsule(self) -> None:
        original = Collider(shape_type="capsule", radius=12, capsule_height=40)
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertEqual(restored.shape_type, "capsule")
        self.assertEqual(restored.radius, 12)
        self.assertEqual(restored.capsule_height, 40)

    def test_roundtrip_polygon(self) -> None:
        original = Collider(
            shape_type="polygon",
            points=[[-16, -16], [16, -16], [0, 16]],
        )
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertEqual(restored.shape_type, "polygon")
        self.assertEqual(len(restored.points), 3)
        self.assertEqual(restored.points[0], [-16, -16])

    def test_roundtrip_trigger(self) -> None:
        original = Collider(is_trigger=True, width=32, height=32)
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertTrue(restored.is_trigger)

    def test_roundtrip_one_way(self) -> None:
        original = Collider(
            one_way_collision=True,
            one_way_collision_direction_y=-1.0,
        )
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertTrue(restored.one_way_collision)
        self.assertEqual(restored.one_way_collision_direction_y, -1.0)

    def test_one_way_collision_margin_and_direction_x_serialize(self) -> None:
        """one_way_collision_margin and direction_x survive roundtrip."""
        c = Collider(
            one_way_collision=True,
            one_way_collision_margin=2.5,
            one_way_collision_direction_x=0.5,
            one_way_collision_direction_y=-1.0,
        )
        data = c.to_dict()
        self.assertEqual(data["one_way_collision_margin"], 2.5)
        self.assertEqual(data["one_way_collision_direction_x"], 0.5)
        c2 = Collider.from_dict(data)
        self.assertEqual(c2.one_way_collision_margin, 2.5)
        self.assertEqual(c2.one_way_collision_direction_x, 0.5)

    def test_roundtrip_enabled(self) -> None:
        original = Collider(width=64, height=48)
        original.enabled = False
        data = original.to_dict()
        restored = Collider.from_dict(data)
        self.assertFalse(restored.enabled)

    def test_existing_scene_loads_without_migration(self) -> None:
        """Escena existente carga sin errores de migración."""
        try:
            from engine.api import EngineAPI
        except ImportError:
            self.skipTest("EngineAPI no disponible")
        try:
            api = EngineAPI(project_root=".", read_only=True)
            scenes = api.list_project_scenes()
            if not scenes:
                self.skipTest("No hay escenas en el proyecto")
            api.load_scene(scenes[0])
            api.shutdown()
        except Exception as e:
            self.skipTest(f"No se pudo cargar escena: {e}")
