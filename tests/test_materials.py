import tempfile
import unittest
from pathlib import Path

from engine.assets.asset_service import AssetService
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.project.project_service import ProjectService
from engine.rendering.materials import Material2D
from engine.systems.render_system import RenderSystem


class MaterialInfraTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temp_dir.name) / "MaterialProject"
        self.project_service = ProjectService(self.project_root.as_posix())
        self.asset_service = AssetService(self.project_service)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_material_asset_roundtrip_and_catalog_registration(self) -> None:
        material_path = "assets/materials/additive.material.json"
        material = Material2D(
            name="Additive",
            shader_id="default",
            blend_mode="additive",
            parameters={"intensity": 1.25},
            tags=["fx", "glow"],
        )

        saved = self.asset_service.save_material_definition(material_path, material)
        loaded = self.asset_service.load_material_definition(material_path)
        entry = self.asset_service.get_asset_entry(material_path)

        self.assertEqual(saved["path"], material_path)
        self.assertEqual(loaded.blend_mode, "additive")
        self.assertEqual(loaded.parameters["intensity"], 1.25)
        self.assertEqual(loaded.tags, ["fx", "glow"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["asset_kind"], "material")

    def test_render_batch_key_uses_material_asset_blend_mode(self) -> None:
        self.asset_service.save_material_definition(
            "assets/materials/additive.material.json",
            Material2D(name="Additive", blend_mode="additive", shader_id="default"),
        )
        self.asset_service.save_material_definition(
            "assets/materials/normal.material.json",
            Material2D(name="Normal", blend_mode="alpha", shader_id="default"),
        )

        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay"]}}
        additive = world.create_entity("AdditiveSprite")
        additive.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        additive.add_component(Sprite(texture_path="assets/shared.png", width=32, height=32))
        additive.add_component(RenderOrder2D(sorting_layer="Gameplay", order_in_layer=0))
        additive.add_component(RenderStyle2D(material="assets/materials/additive.material.json"))

        normal = world.create_entity("NormalSprite")
        normal.add_component(Transform(x=10.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        normal.add_component(Sprite(texture_path="assets/shared.png", width=32, height=32))
        normal.add_component(RenderOrder2D(sorting_layer="Gameplay", order_in_layer=1))
        normal.add_component(RenderStyle2D(material="assets/materials/normal.material.json"))

        render_system = RenderSystem()
        render_system.set_project_service(self.project_service)
        graph = render_system.get_last_render_graph()
        self.assertEqual(graph["totals"]["render_entities"], 0)

        graph = render_system._public_graph(render_system._build_render_graph(world))
        world_batches = graph["passes"][0]["batches"]

        self.assertEqual(len(world_batches), 2)
        self.assertEqual(world_batches[0]["key"]["blend_mode"], "additive")
        self.assertEqual(world_batches[1]["key"]["blend_mode"], "alpha")


if __name__ == "__main__":
    unittest.main()
