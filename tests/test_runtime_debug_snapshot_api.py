import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI


class RuntimeDebugSnapshotApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "DebugSnapshotProject"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.root / "global_state"
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, payload: dict) -> Path:
        path = self.project_root / "levels" / "runtime_debug_snapshot.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def test_runtime_debug_snapshot_contract_includes_physics_animator_and_tilemap(self) -> None:
        scene_path = self._write_scene(
            {
                "name": "Runtime Debug Snapshot",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 25.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {
                                "enabled": True,
                                "body_type": "dynamic",
                                "gravity_scale": 0.0,
                                "velocity_x": 0.0,
                                "velocity_y": 0.0,
                                "is_grounded": True,
                            },
                            "Collider": {"enabled": True, "width": 10.0, "height": 10.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Ground",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 120.0, "height": 20.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Bullet",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {
                                "enabled": True,
                                "body_type": "dynamic",
                                "gravity_scale": 0.0,
                                "velocity_x": 2000.0,
                                "velocity_y": 0.0,
                                "is_grounded": True,
                                "collision_detection_mode": "continuous",
                            },
                            "Collider": {"enabled": True, "width": 2.0, "height": 2.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 20.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 4.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "HeroAnimator",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 10.0, "y": 10.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Animator": {
                                "enabled": True,
                                "sprite_sheet": "assets/hero.png",
                                "sprite_sheet_path": "assets/hero.png",
                                "frame_width": 16,
                                "frame_height": 16,
                                "anchor_mode": "slice_pivot",
                                "animations": {
                                    "idle": {
                                        "frames": [0, 1],
                                        "slice_names": ["idle_0", "idle_1"],
                                        "fps": 2.0,
                                        "loop": True,
                                    }
                                },
                                "default_state": "idle",
                                "current_state": "idle",
                                "current_frame": 0,
                                "is_finished": False,
                            },
                            "AnimatorController": {
                                "enabled": True,
                                "entry_state": "idle_logic",
                                "parameters": {
                                    "speed_x": {"type": "float", "default": 0.0},
                                    "jump": {"type": "trigger"},
                                },
                                "states": {
                                    "idle_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                                    "jump_logic": {"animation_state": "idle", "enter_events": [], "exit_events": []},
                                },
                                "transitions": [],
                            },
                        },
                    },
                    {
                        "name": "Map",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 120.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Tilemap": {
                                "enabled": True,
                                "cell_width": 16,
                                "cell_height": 16,
                                "orientation": "orthogonal",
                                "tileset_mode": "atlas_slices",
                                "tileset": {"guid": "", "path": "assets/terrain_atlas.png"},
                                "tileset_path": "assets/terrain_atlas.png",
                                "layers": [
                                    {
                                        "name": "Ground",
                                        "visible": True,
                                        "opacity": 1.0,
                                        "locked": False,
                                        "offset_x": 0.0,
                                        "offset_y": 0.0,
                                        "collision_layer": 0,
                                        "tilemap_source": {"guid": "", "path": "assets/terrain_atlas.png"},
                                        "tiles": [
                                            {"x": 0, "y": 0, "tile_id": "grass", "slice_name": "terrain_grass", "flags": ["solid"]},
                                            {"x": 1, "y": 0, "tile_id": "stone", "slice_name": "terrain_stone"},
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
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(1)

        snapshot = self.api.get_runtime_debug_snapshot()
        serialized = json.dumps(snapshot)

        self.assertTrue(serialized)
        self.assertEqual(snapshot["engine_state"], "PLAY")
        self.assertTrue(snapshot["world_available"])
        self.assertEqual(snapshot["physics"]["backend"]["effective"], "legacy_aabb")
        self.assertIn("substeps", snapshot["physics"]["last_step_metrics"])
        self.assertIn("ccd_bodies", snapshot["physics"]["last_step_metrics"])
        self.assertIn("swept_checks", snapshot["physics"]["last_step_metrics"])

        rigidbodies = {entry["entity"]: entry for entry in snapshot["physics"]["rigidbodies"]}
        self.assertIn("Player", rigidbodies)
        self.assertTrue(rigidbodies["Player"]["grounded"])
        self.assertIn("position", rigidbodies["Player"])
        self.assertIn("velocity", rigidbodies["Player"])
        self.assertIn("contact_state", rigidbodies["Player"])
        self.assertTrue(rigidbodies["Player"]["contact_state"]["grounded"])
        self.assertEqual(rigidbodies["Player"]["contact_state"]["ground_normal"]["y"], -1.0)

        contact_pairs = {
            frozenset((entry["entity_a"], entry["entity_b"])): entry
            for entry in snapshot["physics"]["contacts"]
        }
        bullet_wall = contact_pairs[frozenset(("Bullet", "Wall"))]
        self.assertEqual(bullet_wall["contact_type"], "wall")
        self.assertEqual(bullet_wall["normal"]["x"], -1.0)
        self.assertEqual(bullet_wall["source"], "swept")
        self.assertIn("penetration", bullet_wall)
        self.assertIn("separation", bullet_wall)

        animators = {entry["entity"]: entry for entry in snapshot["animators"]}
        self.assertEqual(animators["HeroAnimator"]["current_state"], "idle")
        self.assertEqual(animators["HeroAnimator"]["current_frame"], 0)
        self.assertEqual(animators["HeroAnimator"]["current_slice"], "idle_0")
        self.assertEqual(animators["HeroAnimator"]["anchor_mode"], "slice_pivot")
        self.assertTrue(animators["HeroAnimator"]["controller_enabled"])
        self.assertEqual(animators["HeroAnimator"]["controller_state"], "idle_logic")
        self.assertEqual(animators["HeroAnimator"]["mapped_animation_state"], "idle")
        self.assertIn("speed_x", animators["HeroAnimator"]["parameters"])
        self.assertIn("jump", animators["HeroAnimator"]["parameters"])
        self.assertEqual(animators["HeroAnimator"]["pending_triggers"], [])

        tilemaps = {entry["entity"]: entry for entry in snapshot["tilemaps"]}
        self.assertEqual(tilemaps["Map"]["tileset_mode"], "atlas_slices")
        self.assertEqual(tilemaps["Map"]["tileset_path"], "assets/terrain_atlas.png")
        self.assertEqual(tilemaps["Map"]["total_tiles"], 2)
        self.assertEqual(tilemaps["Map"]["layer_count"], 1)
        self.assertEqual(tilemaps["Map"]["layers"][0]["tile_count"], 2)

    def test_runtime_debug_snapshot_is_stable_in_edit_mode(self) -> None:
        scene_path = self._write_scene(
            {
                "name": "Edit Debug Snapshot",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.api.load_level(scene_path.as_posix())

        snapshot = self.api.get_runtime_debug_snapshot()

        self.assertEqual(snapshot["engine_state"], "EDIT")
        self.assertTrue(snapshot["world_available"])
        self.assertEqual(snapshot["physics"]["backend"]["requested"], "legacy_aabb")
        self.assertEqual(snapshot["physics"]["contacts"], [])
        self.assertEqual(snapshot["physics"]["rigidbodies"], [])
        self.assertEqual(snapshot["animators"], [])
        self.assertEqual(snapshot["tilemaps"], [])


if __name__ == "__main__":
    unittest.main()
