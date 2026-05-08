import unittest

from engine.components.collision_shape_set_2d import (
    CollisionShape2DDef,
    CollisionShapeSet2D,
)


class CollisionShape2DDefTests(unittest.TestCase):
    def test_default_box_bounds(self) -> None:
        d = CollisionShape2DDef(width=32.0, height=48.0)
        bounds = d.get_bounds(100.0, 200.0)
        self.assertAlmostEqual(bounds[0], 84.0)   # left: 100 - 16
        self.assertAlmostEqual(bounds[1], 176.0)  # top: 200 - 24
        self.assertAlmostEqual(bounds[2], 116.0)  # right: 100 + 16
        self.assertAlmostEqual(bounds[3], 224.0)  # bottom: 200 + 24

    def test_bounds_with_offset(self) -> None:
        d = CollisionShape2DDef(width=16.0, height=16.0, offset_x=10.0, offset_y=-5.0)
        bounds = d.get_bounds(0.0, 0.0)
        self.assertAlmostEqual(bounds[0], 2.0)
        self.assertAlmostEqual(bounds[1], -13.0)
        self.assertAlmostEqual(bounds[2], 18.0)
        self.assertAlmostEqual(bounds[3], 3.0)

    def test_circle_bounds(self) -> None:
        d = CollisionShape2DDef(shape_type="circle", radius=10.0)
        bounds = d.get_bounds(50.0, 60.0)
        self.assertAlmostEqual(bounds[0], 40.0)
        self.assertAlmostEqual(bounds[1], 50.0)
        self.assertAlmostEqual(bounds[2], 60.0)
        self.assertAlmostEqual(bounds[3], 70.0)

    def test_capsule_bounds(self) -> None:
        d = CollisionShape2DDef(shape_type="capsule", radius=5.0, capsule_height=20.0)
        bounds = d.get_bounds(0.0, 0.0)
        # half total = radius + capsule_height/2 = 5 + 10 = 15
        self.assertAlmostEqual(bounds[0], -5.0)
        self.assertAlmostEqual(bounds[1], -15.0)
        self.assertAlmostEqual(bounds[2], 5.0)
        self.assertAlmostEqual(bounds[3], 15.0)

    def test_to_dict_roundtrip_box(self) -> None:
        d = CollisionShape2DDef(width=20.0, height=30.0, friction=0.5, restitution=0.3)
        data = d.to_dict()
        restored = CollisionShape2DDef.from_dict(data)
        self.assertEqual(restored.shape_type, "box")
        self.assertEqual(restored.width, 20.0)
        self.assertEqual(restored.height, 30.0)
        self.assertEqual(restored.friction, 0.5)
        self.assertEqual(restored.restitution, 0.3)

    def test_to_dict_roundtrip_with_points(self) -> None:
        d = CollisionShape2DDef(shape_type="polygon", points=[[0.0, 0.0], [10.0, 0.0], [5.0, 10.0]])
        data = d.to_dict()
        restored = CollisionShape2DDef.from_dict(data)
        self.assertEqual(restored.shape_type, "polygon")
        self.assertEqual(len(restored.points), 3)
        self.assertEqual(restored.points[0], [0.0, 0.0])

    def test_disabled_and_trigger_flags(self) -> None:
        d = CollisionShape2DDef(disabled=True, is_trigger=True)
        self.assertTrue(d.disabled)
        self.assertTrue(d.is_trigger)
        data = d.to_dict()
        restored = CollisionShape2DDef.from_dict(data)
        self.assertTrue(restored.disabled)
        self.assertTrue(restored.is_trigger)


class CollisionShapeSet2DTests(unittest.TestCase):
    def test_default_has_one_shape(self) -> None:
        s = CollisionShapeSet2D()
        self.assertEqual(len(s.shapes), 1)
        self.assertEqual(s.shapes[0].shape_type, "box")

    def test_composite_bounds_single_shape(self) -> None:
        s = CollisionShapeSet2D(shapes=[
            CollisionShape2DDef(width=10.0, height=10.0),
        ])
        bounds = s.get_composite_bounds(0.0, 0.0)
        self.assertAlmostEqual(bounds[0], -5.0)
        self.assertAlmostEqual(bounds[1], -5.0)
        self.assertAlmostEqual(bounds[2], 5.0)
        self.assertAlmostEqual(bounds[3], 5.0)

    def test_composite_bounds_multiple_shapes(self) -> None:
        s = CollisionShapeSet2D(shapes=[
            CollisionShape2DDef(width=10.0, height=10.0, offset_x=-20.0),
            CollisionShape2DDef(width=10.0, height=10.0, offset_x=20.0),
        ])
        bounds = s.get_composite_bounds(0.0, 0.0)
        # leftmost: -25, rightmost: 25, top: -5, bottom: 5
        self.assertAlmostEqual(bounds[0], -25.0)
        self.assertAlmostEqual(bounds[2], 25.0)
        self.assertAlmostEqual(bounds[3], 5.0)

    def test_disabled_shapes_excluded_from_composite(self) -> None:
        s = CollisionShapeSet2D(shapes=[
            CollisionShape2DDef(width=10.0, height=10.0),
            CollisionShape2DDef(width=100.0, height=100.0, disabled=True),
        ])
        enabled = s.get_enabled_non_trigger_shapes()
        self.assertEqual(len(enabled), 1)
        bounds = s.get_composite_bounds(0.0, 0.0)
        self.assertAlmostEqual(bounds[2], 5.0)  # not 50.0

    def test_trigger_shapes_excluded_from_composite(self) -> None:
        s = CollisionShapeSet2D(shapes=[
            CollisionShape2DDef(width=10.0, height=10.0, is_trigger=True),
            CollisionShape2DDef(width=20.0, height=20.0),
        ])
        enabled = s.get_enabled_non_trigger_shapes()
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0].width, 20.0)

    def test_to_dict_roundtrip(self) -> None:
        s = CollisionShapeSet2D(shapes=[
            CollisionShape2DDef(width=10.0, shape_type="box"),
            CollisionShape2DDef(width=5.0, shape_type="circle", radius=2.5, offset_x=3.0),
        ])
        data = s.to_dict()
        restored = CollisionShapeSet2D.from_dict(data)
        self.assertEqual(len(restored.shapes), 2)
        self.assertEqual(restored.shapes[0].width, 10.0)
        self.assertEqual(restored.shapes[1].shape_type, "circle")
        self.assertEqual(restored.shapes[1].radius, 2.5)
        self.assertEqual(restored.shapes[1].offset_x, 3.0)

    def test_empty_shapes_list_creates_default(self) -> None:
        s = CollisionShapeSet2D.from_dict({"shapes": []})
        self.assertEqual(len(s.shapes), 1)
        self.assertEqual(s.shapes[0].shape_type, "box")

    def test_get_bounds_on_each_shape(self) -> None:
        d = CollisionShape2DDef(width=8.0, height=16.0, offset_x=5.0, offset_y=-2.0)
        bounds = d.get_bounds(100.0, 200.0)
        self.assertAlmostEqual(bounds[0], 101.0)
        self.assertAlmostEqual(bounds[1], 190.0)
        self.assertAlmostEqual(bounds[2], 109.0)
        self.assertAlmostEqual(bounds[3], 206.0)


if __name__ == "__main__":
    unittest.main()
