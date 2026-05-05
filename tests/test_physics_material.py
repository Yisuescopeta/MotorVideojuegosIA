import unittest

from engine.resources.physics_material import PhysicsMaterial


class PhysicsMaterialTests(unittest.TestCase):
    def test_default_values(self) -> None:
        mat = PhysicsMaterial()
        self.assertEqual(mat.friction, 1.0)
        self.assertEqual(mat.bounce, 0.0)
        self.assertFalse(mat.rough)
        self.assertFalse(mat.absorbent)

    def test_get_effective_friction_normal(self) -> None:
        mat = PhysicsMaterial(friction=0.5)
        self.assertEqual(mat.get_effective_friction(), 0.5)

    def test_rough_material_infinite_friction(self) -> None:
        mat = PhysicsMaterial(rough=True, friction=0.3)
        self.assertEqual(mat.get_effective_friction(), float('inf'))

    def test_absorbent_zero_bounce(self) -> None:
        mat = PhysicsMaterial(absorbent=True, bounce=0.9)
        self.assertEqual(mat.get_effective_bounce(), 0.0)

    def test_get_effective_bounce_normal(self) -> None:
        mat = PhysicsMaterial(bounce=0.7)
        self.assertEqual(mat.get_effective_bounce(), 0.7)

    def test_serialization_roundtrip(self) -> None:
        mat = PhysicsMaterial(
            resource_id="ice",
            resource_name="Ice",
            friction=0.1,
            bounce=0.0,
            rough=False,
            absorbent=False,
        )
        data = mat.to_dict()
        restored = PhysicsMaterial.from_dict(data)
        self.assertEqual(restored.resource_id, "ice")
        self.assertEqual(restored.resource_name, "Ice")
        self.assertEqual(restored.friction, 0.1)
        self.assertEqual(restored.bounce, 0.0)
        self.assertFalse(restored.rough)
        self.assertFalse(restored.absorbent)

    def test_serialization_with_rough_absorbent(self) -> None:
        mat = PhysicsMaterial(
            resource_id="sandpaper",
            resource_name="Sandpaper",
            friction=1.5,
            rough=True,
            absorbent=True,
        )
        data = mat.to_dict()
        restored = PhysicsMaterial.from_dict(data)
        self.assertTrue(restored.rough)
        self.assertTrue(restored.absorbent)
        self.assertEqual(restored.get_effective_friction(), float('inf'))
        self.assertEqual(restored.get_effective_bounce(), 0.0)

    def test_from_dict_missing_fields_uses_defaults(self) -> None:
        mat = PhysicsMaterial.from_dict({})
        self.assertEqual(mat.resource_id, "")
        self.assertEqual(mat.resource_name, "default")
        self.assertEqual(mat.friction, 1.0)
        self.assertEqual(mat.bounce, 0.0)

    def test_bounce_value_preserved_when_not_absorbent(self) -> None:
        mat = PhysicsMaterial(bounce=0.8, absorbent=False)
        self.assertEqual(mat.get_effective_bounce(), 0.8)

    def test_friction_edge_cases(self) -> None:
        mat = PhysicsMaterial(friction=0.0)
        self.assertEqual(mat.get_effective_friction(), 0.0)

        mat2 = PhysicsMaterial(friction=2.0)
        self.assertEqual(mat2.get_effective_friction(), 2.0)
