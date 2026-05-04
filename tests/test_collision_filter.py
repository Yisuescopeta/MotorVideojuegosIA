import os
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.collision_filter_2d import CollisionFilter2D, MASK_ALL
from engine.levels.component_registry import create_default_registry


class CollisionFilter2DComponentTests(unittest.TestCase):
    """Tests unitarios del componente CollisionFilter2D."""

    def test_default_values(self) -> None:
        cf = CollisionFilter2D()
        self.assertEqual(cf.layer, 1)
        self.assertEqual(cf.mask, MASK_ALL)
        self.assertTrue(cf.enabled)

    def test_custom_values(self) -> None:
        cf = CollisionFilter2D(layer=4, mask=0x0000000F)
        self.assertEqual(cf.layer, 4)
        self.assertEqual(cf.mask, 0x0000000F)

    def test_layer_int_conversion(self) -> None:
        cf = CollisionFilter2D(layer=3.7)
        self.assertIsInstance(cf.layer, int)
        self.assertEqual(cf.layer, 3)

    def test_to_dict(self) -> None:
        cf = CollisionFilter2D(layer=2, mask=255)
        data = cf.to_dict()
        self.assertEqual(data["enabled"], True)
        self.assertEqual(data["layer"], 2)
        self.assertEqual(data["mask"], 255)

    def test_from_dict(self) -> None:
        data = {"enabled": False, "layer": 8, "mask": 15}
        cf = CollisionFilter2D.from_dict(data)
        self.assertFalse(cf.enabled)
        self.assertEqual(cf.layer, 8)
        self.assertEqual(cf.mask, 15)

    def test_from_dict_defaults(self) -> None:
        cf = CollisionFilter2D.from_dict({})
        self.assertTrue(cf.enabled)
        self.assertEqual(cf.layer, 1)
        self.assertEqual(cf.mask, MASK_ALL)

    def test_serialization_roundtrip(self) -> None:
        original = CollisionFilter2D(layer=0x0000000F, mask=0xAAAAAAAA)
        data = original.to_dict()
        restored = CollisionFilter2D.from_dict(data)
        self.assertEqual(restored.layer, original.layer)
        self.assertEqual(restored.mask, original.mask)
        self.assertEqual(restored.enabled, original.enabled)

    def test_repr(self) -> None:
        cf = CollisionFilter2D(layer=1, mask=MASK_ALL)
        rep = repr(cf)
        self.assertIn("CollisionFilter2D", rep)
        self.assertIn("layer", rep)
        self.assertIn("mask", rep)

    def test_set_layer_bit(self) -> None:
        cf = CollisionFilter2D(layer=0)
        cf.set_layer_bit(0)
        self.assertEqual(cf.layer, 1)
        cf.set_layer_bit(3)
        self.assertEqual(cf.layer, 1 | 8)

    def test_clear_layer_bit(self) -> None:
        cf = CollisionFilter2D(layer=0xFFFFFFFF)
        cf.clear_layer_bit(0)
        self.assertEqual(cf.layer, 0xFFFFFFFF & ~1)
        cf.clear_layer_bit(3)
        self.assertEqual(cf.layer, 0xFFFFFFFF & ~1 & ~8)

    def test_has_layer_bit(self) -> None:
        cf = CollisionFilter2D(layer=0x00000005)
        self.assertTrue(cf.has_layer_bit(0))
        self.assertFalse(cf.has_layer_bit(1))
        self.assertTrue(cf.has_layer_bit(2))
        self.assertFalse(cf.has_layer_bit(3))

    def test_set_mask_bit(self) -> None:
        cf = CollisionFilter2D(mask=0)
        cf.set_mask_bit(2)
        self.assertEqual(cf.mask, 4)

    def test_clear_mask_bit(self) -> None:
        cf = CollisionFilter2D(mask=MASK_ALL)
        cf.clear_mask_bit(5)
        self.assertFalse(cf.has_mask_bit(5))
        self.assertTrue(cf.has_mask_bit(0))

    def test_has_mask_bit(self) -> None:
        cf = CollisionFilter2D(mask=0x0000000A)
        self.assertFalse(cf.has_mask_bit(0))
        self.assertTrue(cf.has_mask_bit(1))
        self.assertFalse(cf.has_mask_bit(2))
        self.assertTrue(cf.has_mask_bit(3))

    def test_should_collide_both_present(self) -> None:
        a = CollisionFilter2D(layer=1, mask=1)       # capa 1, colisiona con capa 1
        b = CollisionFilter2D(layer=2, mask=1)       # capa 2, colisiona con capa 1
        self.assertFalse(CollisionFilter2D.should_collide(a, b))

    def test_should_collide_mutual_layers(self) -> None:
        a = CollisionFilter2D(layer=1, mask=3)       # capa 1, colisiona con 1 y 2
        b = CollisionFilter2D(layer=2, mask=1)       # capa 2, colisiona con 1
        self.assertTrue(CollisionFilter2D.should_collide(a, b))

    def test_should_collide_same_layer(self) -> None:
        a = CollisionFilter2D(layer=1, mask=1)
        b = CollisionFilter2D(layer=1, mask=1)
        self.assertTrue(CollisionFilter2D.should_collide(a, b))

    def test_should_collide_one_way_no(self) -> None:
        # A colisiona con B, pero B no colisiona con A
        a = CollisionFilter2D(layer=1, mask=2)       # colisiona con capa 2
        b = CollisionFilter2D(layer=2, mask=4)       # colisiona con capa 3, NO con capa 1
        self.assertFalse(CollisionFilter2D.should_collide(a, b))

    def test_should_collide_none_filter_compat(self) -> None:
        a = CollisionFilter2D(layer=1, mask=0)
        self.assertTrue(CollisionFilter2D.should_collide(a, None))
        self.assertTrue(CollisionFilter2D.should_collide(None, a))
        self.assertTrue(CollisionFilter2D.should_collide(None, None))

    def test_should_collide_both_present_full_mask(self) -> None:
        a = CollisionFilter2D(layer=1, mask=MASK_ALL)
        b = CollisionFilter2D(layer=2, mask=MASK_ALL)
        self.assertTrue(CollisionFilter2D.should_collide(a, b))

    def test_create_from_registry(self) -> None:
        registry = create_default_registry()
        cf = registry.create("CollisionFilter2D", {"layer": 4, "mask": 255})
        self.assertIsInstance(cf, CollisionFilter2D)
        self.assertEqual(cf.layer, 4)
        self.assertEqual(cf.mask, 255)

    def test_create_from_registry_defaults(self) -> None:
        registry = create_default_registry()
        cf = registry.create("CollisionFilter2D", {})
        self.assertIsInstance(cf, CollisionFilter2D)
        self.assertEqual(cf.layer, 1)
        self.assertEqual(cf.mask, MASK_ALL)

    def test_registry_listed(self) -> None:
        registry = create_default_registry()
        names = registry.list_registered()
        self.assertIn("CollisionFilter2D", names)


class CollisionFilter2DAPITests(unittest.TestCase):
    """Tests de integración con EngineAPI authoring."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        self._previous_cwd = Path.cwd()
        repo_levels = Path(__file__).resolve().parents[1] / "levels"
        target_levels = self.project_root / "levels"
        target_levels.mkdir(parents=True, exist_ok=True)
        for level_name in ("demo_level.json", "platformer_test_scene.json"):
            source_level = repo_levels / level_name
            (target_levels / level_name).write_text(
                source_level.read_text(encoding="utf-8"), encoding="utf-8"
            )
        os.chdir(self.project_root)
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        os.chdir(self._previous_cwd)
        self._temp_dir.cleanup()

    def test_set_collision_filter_new_entity(self) -> None:
        result = self.api.create_entity("FilteredEntity")
        self.assertTrue(result["success"])

        result = self.api.set_collision_filter("FilteredEntity", layer=4, mask=255)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["entity"], "FilteredEntity")

        entity = self.api.get_entity("FilteredEntity")
        cf_data = entity["components"].get("CollisionFilter2D")
        self.assertIsNotNone(cf_data)
        self.assertEqual(cf_data["layer"], 4)
        self.assertEqual(cf_data["mask"], 255)

    def test_set_collision_filter_update_existing(self) -> None:
        result = self.api.create_entity("UpdateFilterEntity")
        self.assertTrue(result["success"])

        result = self.api.set_collision_filter("UpdateFilterEntity", layer=1, mask=0xFFFFFFFF)
        self.assertTrue(result["success"])

        result = self.api.set_collision_filter("UpdateFilterEntity", layer=8, mask=15)
        self.assertTrue(result["success"])

        entity = self.api.get_entity("UpdateFilterEntity")
        cf_data = entity["components"].get("CollisionFilter2D")
        self.assertEqual(cf_data["layer"], 8)
        self.assertEqual(cf_data["mask"], 15)

    def test_set_collision_filter_defaults(self) -> None:
        result = self.api.create_entity("DefaultFilter")
        self.assertTrue(result["success"])

        result = self.api.set_collision_filter("DefaultFilter")
        self.assertTrue(result["success"])

        entity = self.api.get_entity("DefaultFilter")
        cf_data = entity["components"].get("CollisionFilter2D")
        self.assertEqual(cf_data["layer"], 1)
        self.assertEqual(cf_data["mask"], 0xFFFFFFFF)

    def test_compatibility_no_filter_collides_with_filter(self) -> None:
        """Entidad sin CollisionFilter2D colisiona con entidad que sí tiene."""
        result = self.api.create_entity("WithFilter")
        self.assertTrue(result["success"])
        result = self.api.set_collision_filter("WithFilter", layer=1, mask=0)
        self.assertTrue(result["success"])

        result = self.api.create_entity("NoFilter")
        self.assertTrue(result["success"])

        entity_with = self.api.get_entity("WithFilter")
        entity_without = self.api.get_entity("NoFilter")

        cf_data = entity_with["components"].get("CollisionFilter2D")
        self.assertIsNotNone(cf_data)

        cf_none = entity_without["components"].get("CollisionFilter2D")
        self.assertIsNone(cf_none)

        # Compatibilidad: None siempre colisiona
        self.assertTrue(CollisionFilter2D.should_collide(
            CollisionFilter2D.from_dict(cf_data) if cf_data else None,
            None,
        ))

    def test_set_collision_filter_via_authoring_then_component_data(self) -> None:
        """Verifica que set_collision_filter persiste correctamente en el payload."""
        result = self.api.create_entity("PersistTest")
        self.assertTrue(result["success"])

        result = self.api.set_collision_filter("PersistTest", layer=2, mask=3)
        self.assertTrue(result["success"])

        payload = self.api.load_component_payload("PersistTest", "CollisionFilter2D")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["layer"], 2)
        self.assertEqual(payload["mask"], 3)


class CollisionFilter2DIntegrationTests(unittest.TestCase):
    """Tests de integración del CollisionFilter2D con CollisionSystem y PhysicsSystem."""

    def setUp(self) -> None:
        from engine.components.collider import Collider
        from engine.components.rigidbody import RigidBody
        from engine.components.transform import Transform
        from engine.ecs.world import World
        from engine.systems.collision_system import CollisionSystem

        self.World = World
        self.Transform = Transform
        self.Collider = Collider
        self.RigidBody = RigidBody
        self.CollisionSystem = CollisionSystem

    def _create_entity_with_collision(self, world, name, x=0.0, y=0.0, width=10.0, height=10.0,
                                       layer="Gameplay", body_type="static", collision_filter=None):
        entity = world.create_entity(name)
        entity.layer = layer
        entity.add_component(self.Transform(x=x, y=y))
        entity.add_component(self.Collider(width=width, height=height))
        entity.add_component(self.RigidBody(body_type=body_type))
        if collision_filter is not None:
            entity.add_component(collision_filter)
        return entity

    def test_filter_integration_compat(self) -> None:
        """Entidades sin CollisionFilter2D colisionan normalmente."""
        world = self.World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}

        a = self._create_entity_with_collision(world, "A", x=0.0)
        b = self._create_entity_with_collision(world, "B", x=5.0)

        cs = self.CollisionSystem()
        cs.update(world)

        self.assertEqual(len(cs.get_collisions()), 1)
        self.assertEqual(cs.get_step_metrics()["actual_collisions"], 1)

    def test_filter_blocks_collision(self) -> None:
        """Entidad con layer=1 mask=2 vs layer=2 mask=4 no colisionan (A.mask & B.layer = 2&2=2≠0, B.mask & A.layer = 4&1=0)."""
        world = self.World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}

        cf_a = CollisionFilter2D(layer=1, mask=2)
        cf_b = CollisionFilter2D(layer=2, mask=4)

        a = self._create_entity_with_collision(world, "A", x=0.0, collision_filter=cf_a)
        b = self._create_entity_with_collision(world, "B", x=5.0, collision_filter=cf_b)

        cs = self.CollisionSystem()
        cs.update(world)

        self.assertEqual(len(cs.get_collisions()), 0)
        self.assertEqual(cs.get_step_metrics()["actual_collisions"], 0)

    def test_filter_allows_collision(self) -> None:
        """Entidad con layer=1 mask=2 vs layer=2 mask=1 colisionan (2&2=2≠0 AND 1&1=1≠0)."""
        world = self.World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}

        cf_a = CollisionFilter2D(layer=1, mask=2)
        cf_b = CollisionFilter2D(layer=2, mask=1)

        a = self._create_entity_with_collision(world, "A", x=0.0, collision_filter=cf_a)
        b = self._create_entity_with_collision(world, "B", x=5.0, collision_filter=cf_b)

        cs = self.CollisionSystem()
        cs.update(world)

        self.assertEqual(len(cs.get_collisions()), 1)
        self.assertEqual(cs.get_step_metrics()["actual_collisions"], 1)

    def test_filter_unilateral_compat(self) -> None:
        """Entidad con filter vs entidad sin filter colisionan (sin filter usa 0xFFFFFFFF)."""
        world = self.World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}

        cf_a = CollisionFilter2D(layer=1, mask=0xFFFFFFFF)

        a = self._create_entity_with_collision(world, "A", x=0.0, collision_filter=cf_a)
        b = self._create_entity_with_collision(world, "B", x=5.0, collision_filter=None)

        cs = self.CollisionSystem()
        cs.update(world)

        self.assertEqual(len(cs.get_collisions()), 1)
        self.assertEqual(cs.get_step_metrics()["actual_collisions"], 1)

    def test_filter_in_physics_system(self) -> None:
        """CollisionFilter2D también se respeta en PhysicsSystem durante resolución."""
        from engine.systems.physics_system import PhysicsSystem

        world = self.World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}

        # Entidades con filtros que bloquean colisión
        cf_a = CollisionFilter2D(layer=1, mask=2)
        cf_b = CollisionFilter2D(layer=2, mask=4)

        # A es dynamic cayendo sobre B que es static
        a = self._create_entity_with_collision(world, "A", x=0.0, y=0.0, body_type="dynamic", collision_filter=cf_a)
        b = self._create_entity_with_collision(world, "B", x=0.0, y=20.0, body_type="static", collision_filter=cf_b)

        ps = PhysicsSystem(gravity=98.0)
        ps.update(world, 1.0 / 60.0)

        # A debe atravesar B porque el filtro bloquea
        transform_a = a.get_component(self.Transform)
        # Con gravity 98 y delta 1/60, velocity_y ≈ 98 * 1/60 = 1.633, y ≈ 1.633
        # B está en y=20, así que A está lejos de B de todos modos.
        # Pero si no hubiera filtro, cuando A llegue a B se resolvería.
        # Para probar que el filtro funciona, colocamos A justo encima de B.
        a.get_component(self.Transform).y = 15.0
        a.get_component(self.RigidBody).velocity_y = 10.0

        ps.update(world, 1.0 / 60.0)
        transform_a = a.get_component(self.Transform)
        # Con filtro bloqueante, A debería atravesar B sin ser detenido
        # velocity_y sigue siendo ~11.63 (gravedad + velocidad inicial), y avanzó
        self.assertGreater(transform_a.y, 15.0,
                           "Dynamic entity should pass through static when filter blocks")


if __name__ == "__main__":
    unittest.main()
