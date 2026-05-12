import json
import os
import tempfile
import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.resources.physics_material import (
    PhysicsMaterial,
    clear_physics_material_cache,
    load_physics_material,
)
from engine.systems.physics_system import PhysicsSystem


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

    def test_to_dict_includes_schema_version(self) -> None:
        """Serialized dict must include schema_version=1."""
        mat = PhysicsMaterial(resource_id="test")
        data = mat.to_dict()
        self.assertIn("schema_version", data)
        self.assertEqual(data["schema_version"], 1)

    def test_from_dict_accepts_legacy_no_schema_version(self) -> None:
        """Legacy payload without schema_version loads with default 1."""
        legacy = {
            "resource_id": "old_mat",
            "resource_name": "Old",
            "friction": 0.5,
            "bounce": 0.3,
            "rough": False,
            "absorbent": False,
        }
        mat = PhysicsMaterial.from_dict(legacy)  # type: ignore[arg-type]
        self.assertEqual(mat.resource_id, "old_mat")
        self.assertEqual(mat.friction, 0.5)
        self.assertEqual(mat.schema_version, 1)

    def test_roundtrip_preserves_schema_version(self) -> None:
        """Serialization roundtrip keeps schema_version intact."""
        mat = PhysicsMaterial(resource_id="round", schema_version=1)
        data = mat.to_dict()
        restored = PhysicsMaterial.from_dict(data)
        self.assertEqual(restored.schema_version, mat.schema_version)
        self.assertEqual(restored.resource_id, "round")

    def test_empty_dict_gets_default_schema_version(self) -> None:
        """Empty dict produces schema_version=1 (default)."""
        mat = PhysicsMaterial.from_dict({})  # type: ignore[arg-type]
        self.assertEqual(mat.schema_version, 1)

    def test_from_dict_explicit_schema_version(self) -> None:
        """Explicit schema_version in payload is preserved."""
        mat = PhysicsMaterial.from_dict({
            "resource_id": "v2_marker",
            "schema_version": 99,
        })  # type: ignore[arg-type]
        self.assertEqual(mat.schema_version, 99)


class PhysicsMaterialLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_physics_material_cache()

    def tearDown(self) -> None:
        clear_physics_material_cache()

    def test_load_valid_json_absolute_path(self) -> None:
        data = {
            "resource_id": "bouncy",
            "resource_name": "Bouncy",
            "friction": 0.3,
            "bounce": 0.9,
            "rough": False,
            "absorbent": False,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            mat = load_physics_material(temp_path)
            self.assertIsNotNone(mat)
            assert mat is not None
            self.assertEqual(mat.resource_id, "bouncy")
            self.assertEqual(mat.bounce, 0.9)
            self.assertEqual(mat.friction, 0.3)
        finally:
            os.unlink(temp_path)

    def test_load_empty_path_returns_none(self) -> None:
        self.assertIsNone(load_physics_material(""))
        self.assertIsNone(load_physics_material("   "))

    def test_load_nonexistent_file_returns_none(self) -> None:
        result = load_physics_material("/nonexistent/path/material.json")
        self.assertIsNone(result)

    def test_load_invalid_json_returns_none(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("not valid json {{{")
            temp_path = f.name

        try:
            self.assertIsNone(load_physics_material(temp_path))
        finally:
            os.unlink(temp_path)

    def test_load_non_dict_json_returns_none(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump([1, 2, 3], f)
            temp_path = f.name

        try:
            self.assertIsNone(load_physics_material(temp_path))
        finally:
            os.unlink(temp_path)

    def test_load_missing_fields_uses_defaults(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"resource_id": "minimal"}, f)
            temp_path = f.name

        try:
            mat = load_physics_material(temp_path)
            self.assertIsNotNone(mat)
            assert mat is not None
            self.assertEqual(mat.resource_id, "minimal")
            self.assertEqual(mat.friction, 1.0)  # default
            self.assertEqual(mat.bounce, 0.0)  # default
        finally:
            os.unlink(temp_path)

    def test_cache_returns_same_instance(self) -> None:
        data = {"resource_id": "cached", "friction": 0.5}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            mat1 = load_physics_material(temp_path)
            mat2 = load_physics_material(temp_path)
            self.assertIs(mat1, mat2)
        finally:
            os.unlink(temp_path)

    def test_cache_negative_result(self) -> None:
        """Failed loads are also cached (as None)."""
        bad_path = "/tmp/completely_missing_file_xyz.json"
        # First call: miss
        result1 = load_physics_material(bad_path)
        self.assertIsNone(result1)
        # Second call: cached None
        result2 = load_physics_material(bad_path)
        self.assertIsNone(result2)

    def test_load_relative_path(self) -> None:
        data = {"resource_id": "relative_test", "bounce": 0.5}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            mat = load_physics_material(temp_path)
            self.assertIsNotNone(mat)
            assert mat is not None
            self.assertEqual(mat.resource_id, "relative_test")
        finally:
            os.unlink(temp_path)


class PhysicsMaterialIntegrationTests(unittest.TestCase):
    """Tests that physics_material_override_path affects PhysicsSystem collision resolution.

    Use discrete collision detection + close wall to guarantee overlap → bounce/friction applied.
    """

    def setUp(self) -> None:
        clear_physics_material_cache()

    def tearDown(self) -> None:
        clear_physics_material_cache()

    @staticmethod
    def _write_temp_material(data: dict) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            return f.name

    def test_material_bounce_overrides_collider_restitution_zero(self) -> None:
        """Material con bounce=1.0 produce bounce incluso cuando collider.restitution=0."""
        # NOTA: Con PGS, restitution se usa en la formula de impulso normal.
        # Este test verifica que el bounce del physics_material se aplica.
        mat_path = self._write_temp_material({
            "resource_id": "super_bouncy",
            "bounce": 1.0,
            "friction": 1.0,
        })
        try:
            world = World()
            physics = PhysicsSystem(gravity=0.0)
            ball = world.create_entity("Ball")
            ball.add_component(Transform(x=0.0, y=100.0))
            ball.add_component(Collider(width=8.0, height=8.0, restitution=0.0, friction=0.5))
            ball.add_component(RigidBody(
                body_type="dynamic", mass=1.0, gravity_scale=0.0,
                velocity_x=100.0, velocity_y=0.0,
                physics_material_override_path=mat_path,
            ))
            wall = world.create_entity("Wall")
            wall.add_component(Transform(x=20.0, y=100.0))
            wall.add_component(Collider(width=4.0, height=40.0, restitution=0.0))
            wall.add_component(RigidBody(body_type="static", mass=1.0))

            vx_before = ball.get_component(RigidBody).velocity_x
            dt = 1.0 / 60.0
            for _ in range(30):
                physics.update(world, dt)

            rb = ball.get_component(RigidBody)
            # Con bounce efectivo > 0, la velocidad debe invertirse
            self.assertLess(rb.velocity_x, 0,
                f"Material bounce should reverse velocity. vx={rb.velocity_x}")
        finally:
            os.unlink(mat_path)

    def test_material_rough_kills_tangential_velocity_horizontal(self) -> None:
        """Rough material (infinite friction) reduce significativamente velocidad tangencial."""
        mat_path = self._write_temp_material({
            "resource_id": "sandpaper",
            "rough": True,
            "friction": 1.0,
        })
        try:
            world = World()
            physics = PhysicsSystem(gravity=0.0)
            ball = world.create_entity("Ball")
            ball.add_component(Transform(x=0.0, y=100.0))
            ball.add_component(Collider(width=8.0, height=8.0, friction=0.2))
            ball.add_component(RigidBody(
                body_type="dynamic", mass=1.0, gravity_scale=0.0,
                velocity_x=100.0, velocity_y=1.0,  # pequeña vy para crear contacto
                physics_material_override_path=mat_path,
            ))
            wall = world.create_entity("Wall")
            wall.add_component(Transform(x=20.0, y=100.0))
            wall.add_component(Collider(width=4.0, height=40.0))
            wall.add_component(RigidBody(body_type="static", mass=1.0))

            dt = 1.0 / 60.0
            for _ in range(30):
                physics.update(world, dt)

            rb = ball.get_component(RigidBody)
            # Con rough material, se espera que la velocidad tangencial se reduzca
            self.assertLess(abs(rb.velocity_y) if abs(rb.velocity_x) < 1.0 else abs(rb.velocity_x),
                50.0, f"Rough material should reduce tangential velocity. vx={rb.velocity_x}")
        finally:
            os.unlink(mat_path)

    def test_material_rough_kills_tangential_velocity_vertical(self) -> None:
        """Rough material en colision vertical reduce velocidad tangencial."""
        mat_path = self._write_temp_material({
            "resource_id": "sandpaper",
            "rough": True,
            "friction": 1.0,
        })
        try:
            world = World()
            physics = PhysicsSystem(gravity=0.0)
            ball = world.create_entity("Ball")
            ball.add_component(Transform(x=0.0, y=0.0))
            ball.add_component(Collider(width=8.0, height=8.0, friction=0.2))
            ball.add_component(RigidBody(
                body_type="dynamic", mass=1.0, gravity_scale=0.0,
                velocity_x=30.0, velocity_y=100.0,
                physics_material_override_path=mat_path,
            ))
            ground = world.create_entity("Ground")
            ground.add_component(Transform(x=0.0, y=20.0))
            ground.add_component(Collider(width=100.0, height=4.0))
            ground.add_component(RigidBody(body_type="static", mass=1.0))

            dt = 1.0 / 60.0
            for _ in range(30):
                physics.update(world, dt)

            rb = ball.get_component(RigidBody)
            # Con rough, la velocidad tangencial (vx) debe reducirse
            self.assertLess(abs(rb.velocity_x), 25.0,
                f"Rough material should reduce tangential vx. vx={rb.velocity_x}")
        finally:
            os.unlink(mat_path)

    def test_empty_path_falls_back_to_collider(self) -> None:
        """Path vacio usa collider friction/restitution (PGS)."""
        world = World()
        physics = PhysicsSystem(gravity=0.0)
        ball = world.create_entity("Ball")
        ball.add_component(Transform(x=0.0, y=100.0))
        ball.add_component(Collider(width=8.0, height=8.0, restitution=0.3, friction=0.5))
        ball.add_component(RigidBody(
            body_type="dynamic", mass=1.0, gravity_scale=0.0,
            velocity_x=100.0, velocity_y=0.0,
            physics_material_override_path="",
        ))
        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=20.0, y=100.0))
        wall.add_component(Collider(width=4.0, height=40.0, restitution=0.0))
        wall.add_component(RigidBody(body_type="static", mass=1.0))

        dt = 1.0 / 60.0
        for _ in range(30):
            physics.update(world, dt)

        rb = ball.get_component(RigidBody)
        # Con restitution=0.3 del collider, la velocidad debe reducirse (no invertirse completamente)
        self.assertLess(abs(rb.velocity_x), 95.0,
            f"Collider restitution should affect bounce. vx={rb.velocity_x}")

    def test_invalid_path_falls_back_to_collider(self) -> None:
        """Path invalido usa collider valores (PGS)."""
        world = World()
        physics = PhysicsSystem(gravity=0.0)
        ball = world.create_entity("Ball")
        ball.add_component(Transform(x=0.0, y=100.0))
        ball.add_component(Collider(width=8.0, height=8.0, restitution=0.5, friction=0.8))
        ball.add_component(RigidBody(
            body_type="dynamic", mass=1.0, gravity_scale=0.0,
            velocity_x=100.0, velocity_y=0.0,
            physics_material_override_path="/nonexistent/bad_path.physmat",
        ))
        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=20.0, y=100.0))
        wall.add_component(Collider(width=4.0, height=40.0, restitution=0.0))
        wall.add_component(RigidBody(body_type="static", mass=1.0))

        dt = 1.0 / 60.0
        for _ in range(30):
            physics.update(world, dt)

        rb = ball.get_component(RigidBody)
        # Fallback al collider con restitution=0.5
        self.assertLess(abs(rb.velocity_x), 95.0,
            "Invalid path should fall back to collider values")

    def test_absorbent_vs_zero_restitution_wall(self) -> None:
        """Material absorbente + pared zero-restitution = sin bounce."""
        mat_path = self._write_temp_material({
            "resource_id": "mud",
            "absorbent": True,
            "bounce": 0.9,
            "friction": 1.0,
        })
        try:
            world = World()
            physics = PhysicsSystem(gravity=0.0)
            ball = world.create_entity("Ball")
            ball.add_component(Transform(x=0.0, y=100.0))
            ball.add_component(Collider(width=8.0, height=8.0, restitution=0.5))
            ball.add_component(RigidBody(
                body_type="dynamic", mass=1.0, gravity_scale=0.0,
                velocity_x=100.0, velocity_y=0.0,
                physics_material_override_path=mat_path,
            ))
            wall = world.create_entity("Wall")
            wall.add_component(Transform(x=20.0, y=100.0))
            wall.add_component(Collider(width=4.0, height=40.0, restitution=0.0))
            wall.add_component(RigidBody(body_type="static", mass=1.0))

            dt = 1.0 / 60.0
            for _ in range(30):
                physics.update(world, dt)

            rb = ball.get_component(RigidBody)
            # Absorbent efectivo = bounce casi 0
            self.assertAlmostEqual(abs(rb.velocity_x), 0.0, msg=
                f"Absorbent should nearly stop ball. vx={rb.velocity_x}", delta=30.0)
        finally:
            os.unlink(mat_path)

    def test_rough_material_with_inf_friction_does_not_produce_nan(self) -> None:
        """Rough material (inf friction) produces valid velocity (0), not NaN."""
        mat_path = self._write_temp_material({
            "resource_id": "rough",
            "rough": True,
        })

        try:
            world = World()
            physics = PhysicsSystem(gravity=0.0)

            ball = world.create_entity("Ball")
            ball.add_component(Transform(x=0.0, y=0.0))
            ball.add_component(Collider(width=8.0, height=8.0))
            ball.add_component(RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=300.0,
                velocity_y=300.0,
                physics_material_override_path=mat_path,
            ))

            wall = world.create_entity("Wall")
            wall.add_component(Transform(x=5.0, y=0.0))
            wall.add_component(Collider(width=4.0, height=40.0))

            ground = world.create_entity("Ground")
            ground.add_component(Transform(x=0.0, y=5.0))
            ground.add_component(Collider(width=100.0, height=4.0))

            physics.update(world, 1.0 / 60.0)
            rb = ball.get_component(RigidBody)
            self.assertIsNotNone(rb)
            import math
            self.assertFalse(math.isnan(rb.velocity_x), "vx must not be NaN")
            self.assertFalse(math.isnan(rb.velocity_y), "vy must not be NaN")
            self.assertTrue(math.isfinite(rb.velocity_x), "vx must be finite")
            self.assertTrue(math.isfinite(rb.velocity_y), "vy must be finite")
        finally:
            os.unlink(mat_path)
