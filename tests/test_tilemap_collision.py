import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.tilemap import Tilemap
from engine.tilemap.collision_builder import bake_tilemap_colliders, build_tilemap_collision_regions
from engine.components.transform import Transform
from engine.ecs.world import World


class TilemapCollisionTests(unittest.TestCase):
    def test_collision_region_builder_merges_adjacent_solid_tiles(self) -> None:
        tilemap = Tilemap(
            cell_width=16,
            cell_height=16,
            layers=[
                {
                    "name": "Ground",
                    "tiles": [
                        {"x": 0, "y": 0, "tile_id": "wall", "flags": ["solid"]},
                        {"x": 1, "y": 0, "tile_id": "wall", "flags": ["solid"]},
                        {"x": 0, "y": 1, "tile_id": "wall", "flags": ["solid"]},
                        {"x": 1, "y": 1, "tile_id": "wall", "flags": ["solid"]},
                        {"x": 4, "y": 0, "tile_id": "pillar", "flags": ["solid"]},
                    ],
                }
            ],
        )

        regions = build_tilemap_collision_regions(tilemap, merge_shapes=True)
        self.assertEqual(len(regions), 2)
        self.assertEqual(regions[0]["width"], 32.0)
        self.assertEqual(regions[0]["height"], 32.0)

    def test_baked_tilemap_colliders_block_character_controller(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "TilemapCollisionProject"
            scene = {
                "name": "Tilemap Collision Scene",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_x": 120.0, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                    {
                        "name": "Map",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Tilemap": {
                                "cell_width": 16,
                                "cell_height": 16,
                                "layers": [
                                    {
                                        "name": "Ground",
                                        "tiles": [
                                            {"x": 2, "y": 0, "tile_id": "wall", "flags": ["solid"]},
                                            {"x": 2, "y": 1, "tile_id": "wall", "flags": ["solid"]},
                                        ],
                                    }
                                ],
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
            path = project_root / "levels" / "tilemap_collision.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(scene, indent=2), encoding="utf-8")

            api = EngineAPI(project_root=project_root.as_posix(), global_state_dir=(root / "global_state").as_posix())
            try:
                api.load_level(path.as_posix())
                api.play()
                api.step(20)
                hero = api.get_entity("Hero")
                event_names = [event.name for event in api.game._event_bus.get_recent_events()]
                self.assertLess(hero["components"]["Transform"]["x"], 32.0)
                self.assertIn("on_collision", event_names)
            finally:
                api.shutdown()

    def test_bake_tilemap_colliders_reports_generation_metrics(self) -> None:
        world = World()
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": x, "y": 0, "tile_id": "wall", "flags": ["solid"]} for x in range(8)]}],
            )
        )
        report = bake_tilemap_colliders(world, merge_shapes=True)
        self.assertEqual(report["tile_count"], 8)
        self.assertEqual(report["region_count"], 1)
        self.assertEqual(report["generated_entities"], 1)


if __name__ == "__main__":
    unittest.main()
