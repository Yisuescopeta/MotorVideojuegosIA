from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
import tempfile
import unittest

from engine.api import EngineAPI
from engine.vision.gamespec2d import CameraSpec, EntitySpec, GameSpec2D, GridSpec, TileCell, TileMapSpec
from engine.vision.gamespec_to_scene import build_scene_from_gamespec2d


def sample_spec() -> GameSpec2D:
    return GameSpec2D(
        camera=CameraSpec(x=24.0, y=32.0),
        grid=GridSpec(width=4, height=3, tile_size=16.0, origin_x=10.0, origin_y=20.0),
        tilemap=TileMapSpec(solid_cells=[TileCell(x=0, y=1, label="solid_ground"), TileCell(x=2, y=2, label="platform")]),
        entities=[
            EntitySpec(type="player_spawn", x=12.0, y=34.0),
            EntitySpec(type="coin", x=30.0, y=40.0),
            EntitySpec(type="coin", x=46.0, y=40.0),
            EntitySpec(type="enemy_patrol", x=60.0, y=40.0),
            EntitySpec(type="hazard", x=76.0, y=40.0),
            EntitySpec(type="goal", x=92.0, y=40.0),
            EntitySpec(type="checkpoint", x=108.0, y=40.0),
            EntitySpec(type="killzone", x=124.0, y=40.0),
            EntitySpec(type="decorative_prop", x=140.0, y=40.0, semantics="tree", label="tree"),
        ],
    )


class GameSpecToSceneTests(unittest.TestCase):
    def test_valid_spec_builds_saved_loadable_scene_via_public_engine_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "levels" / "generated.scene"
            output.parent.mkdir()
            report = build_scene_from_gamespec2d(sample_spec(), output, project_root=tmp)

            self.assertEqual(report.representation, "collider_blocks")
            self.assertTrue(output.exists())
            api = EngineAPI(project_root=tmp, auto_ensure_project=True)
            api.load_level(output.as_posix())
            names = [entity["name"] for entity in api.list_entities()]
            self.assertIn("vision_camera", names)
            self.assertIn("player_spawn_001", names)

    def test_semantic_mappings_use_registered_serializable_existing_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "generated.scene"
            report = build_scene_from_gamespec2d(sample_spec(), output, project_root=tmp)
            api = EngineAPI(project_root=tmp, auto_ensure_project=True)
            api.load_level(output.as_posix())
            entities = {entity["name"]: entity["components"] for entity in api.list_entities()}

            expected = {
                "player_spawn_001": "RespawnPoint2D",
                "coin_001": "Collectible2D",
                "enemy_patrol_001": "EnemyPatrol2D",
                "hazard_001": "Hazard2D",
                "goal_001": "Goal2D",
                "checkpoint_001": "Checkpoint2D",
                "killzone_001": "KillZone2D",
            }
            for name, component in expected.items():
                self.assertIn(component, entities[name])
                json.dumps(entities[name][component])
            self.assertEqual(report.semantic_mapping["coin"], ["coin_001", "coin_002"])

    def test_deterministic_collision_safe_entity_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "generated.scene"
            report = build_scene_from_gamespec2d(sample_spec(), output, project_root=tmp)

            self.assertEqual(len(report.entity_names), len(set(report.entity_names)))
            self.assertIn("coin_001", report.entity_names)
            self.assertIn("coin_002", report.entity_names)
            self.assertIn("solid_ground_cell_001_000", report.entity_names)

    def test_grid_origin_tile_size_placement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "generated.scene"
            build_scene_from_gamespec2d(sample_spec(), output, project_root=tmp)
            api = EngineAPI(project_root=tmp, auto_ensure_project=True)
            api.load_level(output.as_posix())
            ground = api.get_entity("solid_ground_cell_001_000")

            self.assertEqual(ground["components"]["Transform"]["x"], 18.0)
            self.assertEqual(ground["components"]["Transform"]["y"], 44.0)
            self.assertEqual(ground["components"]["Collider"]["width"], 16.0)

    def test_collider_fallback_represents_solid_cells_and_camera_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "generated.scene"
            report = build_scene_from_gamespec2d(sample_spec(), output, project_root=tmp)
            api = EngineAPI(project_root=tmp, auto_ensure_project=True)
            api.load_level(output.as_posix())

            self.assertEqual(report.representation, "collider_blocks")
            self.assertIn("Collider", api.get_entity("solid_ground_cell_001_000")["components"])
            self.assertIn("Camera2D", api.get_entity("vision_camera")["components"])

    def test_repeated_builds_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.scene"
            second = Path(tmp) / "second.scene"
            report_a = build_scene_from_gamespec2d(sample_spec(), first, project_root=tmp)
            report_b = build_scene_from_gamespec2d(sample_spec(), second, project_root=tmp)

            self.assertEqual(report_a.entity_names, report_b.entity_names)
            self.assertEqual(_stable_scene_subset(first), _stable_scene_subset(second))

    def test_invalid_spec_does_not_create_or_overwrite_scene_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "generated.scene"
            output.write_text("sentinel", encoding="utf-8")
            spec = sample_spec()
            spec.grid.width = 0

            with self.assertRaises(Exception):
                build_scene_from_gamespec2d(spec, output, project_root=tmp)

            self.assertEqual(output.read_text(encoding="utf-8"), "sentinel")

    def test_builder_import_has_no_optional_vision_deps(self) -> None:
        module = importlib.import_module("engine.vision.gamespec_to_scene")
        self.assertTrue(hasattr(module, "build_scene_from_gamespec2d"))
        source = Path("engine/vision/gamespec_to_scene.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        self.assertTrue({"cv2", "PIL", "numpy", "supervision"}.isdisjoint(imported_roots))

    def test_source_does_not_use_protected_internals_or_direct_json_mutation(self) -> None:
        source = Path("engine/vision/gamespec_to_scene.py").read_text(encoding="utf-8")
        forbidden = [
            "engine.scenes",
            "engine.serialization",
            "engine.levels",
            "engine.ecs",
            "SceneManager",
            "json.dump",
            "json.dumps",
            "open(",
            ".write_text(",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


def _stable_scene_subset(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"name": entity["name"], "tag": entity.get("tag"), "layer": entity.get("layer"), "components": entity.get("components", {})}
        for entity in data.get("entities", [])
    ]


if __name__ == "__main__":
    unittest.main()
