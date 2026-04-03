import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.assets.asset_service import AssetService
from engine.project.project_service import ProjectService
from engine.workflows.ai_assist import ProjectContextPackGenerator


def _transform(x: float = 0.0, y: float = 0.0) -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


class ProjectContextPackGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "ContextPackProject"
        self.global_state_dir = self.workspace / "global_state"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.asset_service = AssetService(self.project_service)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, relative_path: str, payload: dict) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _write_prefab(self, relative_path: str, payload: dict) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _write_script(self, relative_path: str, body: str = "def update(entity, dt):\n    return None\n") -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def _write_asset(self, relative_path: str, content: bytes = b"fake") -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def _load_json_artifact(self, relative_path: str) -> dict:
        return json.loads((self.project_root / relative_path).read_text(encoding="utf-8"))

    def test_empty_project_generates_stable_context_pack(self) -> None:
        generator = ProjectContextPackGenerator(self.project_service, self.asset_service)

        first = generator.generate()
        second = generator.generate()

        self.assertEqual(first.json_path, ".motor/meta/ai_context_pack.json")
        self.assertEqual(first.markdown_path, ".motor/meta/ai_context_pack.md")
        self.assertEqual(
            (self.project_root / first.json_path).read_text(encoding="utf-8"),
            (self.project_root / second.json_path).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (self.project_root / first.markdown_path).read_text(encoding="utf-8"),
            (self.project_root / second.markdown_path).read_text(encoding="utf-8"),
        )

        payload = self._load_json_artifact(first.json_path)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["project"]["startup_scene"], "levels/main_scene.json")
        self.assertEqual(payload["project"]["editor_state"]["last_scene"], "")
        self.assertEqual([scene["path"] for scene in payload["scenes"]["project_scenes"]], ["levels/main_scene.json"])
        self.assertEqual(payload["scenes"]["active_scene"], {})
        self.assertEqual(payload["script_behaviours"]["usages"], [])

    def test_multiple_scenes_capture_sorted_project_scene_list_and_editor_state(self) -> None:
        self.project_service.save_project_settings({"startup_scene": "levels/alpha_scene.json"})
        self.project_service.save_editor_state(
            {
                "last_scene": "levels/beta_scene.json",
                "recent_assets": {"sprite": ["assets/zeta.png", "assets/alpha.png"]},
                "scene_view_states": {"levels/beta_scene.json": {"zoom": 2}},
                "preferences": {"active_tab": "SCENE"},
            }
        )
        self._write_scene(
            "levels/beta_scene.json",
            {"name": "Beta Scene", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self._write_scene(
            "levels/alpha_scene.json",
            {"name": "Alpha Scene", "entities": [], "rules": [], "feature_metadata": {}},
        )

        artifacts = ProjectContextPackGenerator(self.project_service, self.asset_service).generate()
        payload = self._load_json_artifact(artifacts.json_path)

        self.assertEqual(
            [scene["path"] for scene in payload["scenes"]["project_scenes"]],
            ["levels/alpha_scene.json", "levels/beta_scene.json", "levels/main_scene.json"],
        )
        self.assertEqual(payload["project"]["startup_scene"], "levels/alpha_scene.json")
        self.assertEqual(payload["project"]["editor_state"]["last_scene"], "levels/beta_scene.json")
        self.assertEqual(payload["project"]["editor_state"]["recent_assets"]["sprite"], ["assets/alpha.png", "assets/zeta.png"])

    def test_scene_flow_metadata_and_transition_rows_are_exported(self) -> None:
        self._write_scene(
            "levels/source_scene.json",
            {
                "name": "Source Scene",
                "entities": [
                    {
                        "name": "Door",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": _transform(16.0, 32.0),
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_scene.json",
                                "target_entry_id": "arrival",
                            },
                            "SceneTransitionOnInteract": {
                                "enabled": True,
                                "require_player": True,
                            },
                            "Collider": {
                                "enabled": True,
                                "shape_type": "box",
                                "width": 16.0,
                                "height": 16.0,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "is_trigger": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {
                    "scene_flow": {"next_scene": "levels/target_scene.json"},
                    "render_2d": {"sorting_layers": ["Background", "Gameplay"]},
                    "physics_2d": {"backend": "box2d", "layer_matrix": {"Player|World": True}},
                },
            },
        )
        self._write_scene(
            "levels/target_scene.json",
            {
                "name": "Target Scene",
                "entities": [
                    {
                        "name": "Arrival",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": _transform(100.0, 200.0),
                            "SceneEntryPoint": {
                                "enabled": True,
                                "entry_id": "arrival",
                                "label": "Arrival",
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )

        artifacts = ProjectContextPackGenerator(self.project_service, self.asset_service).generate()
        payload = self._load_json_artifact(artifacts.json_path)

        self.assertTrue(
            any(item["scene_path"] == "levels/source_scene.json" for item in payload["features"]["scene_flow_metadata"])
        )
        self.assertIn("Background", payload["features"]["sorting_layers"])
        self.assertTrue(
            any(
                row["target_scene_path"] == "levels/target_scene.json" and row["target_entry_id"] == "arrival"
                for row in payload["scenes"]["transition_rows"]
            )
        )

    def test_script_behaviour_usage_is_summarized_from_scenes_and_prefabs(self) -> None:
        self._write_script("scripts/player_logic.py")
        self._write_script("scripts/enemy_logic.py")
        self._write_scene(
            "levels/script_scene.json",
            {
                "name": "Script Scene",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": _transform(),
                            "ScriptBehaviour": {
                                "enabled": True,
                                "script": {"path": "scripts/player_logic.py", "guid": ""},
                                "module_path": "player_logic",
                                "run_in_edit_mode": True,
                                "public_data": {"lives": 3, "god_mode": False, "spawn": {"x": 1}},
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_prefab(
            "prefabs/enemy.json",
            {
                "root_name": "EnemyPrefab",
                "entities": [
                    {
                        "name": "EnemyPrefab",
                        "active": True,
                        "tag": "Enemy",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": _transform(),
                            "ScriptBehaviour": {
                                "enabled": True,
                                "script": {"path": "scripts/enemy_logic.py", "guid": ""},
                                "module_path": "enemy_logic",
                                "run_in_edit_mode": False,
                                "public_data": {"speed": 2.5},
                            },
                        },
                    }
                ],
            },
        )

        artifacts = ProjectContextPackGenerator(self.project_service, self.asset_service).generate()
        payload = self._load_json_artifact(artifacts.json_path)
        usages = payload["script_behaviours"]["usages"]

        self.assertEqual(len(usages), 2)
        self.assertEqual(payload["script_behaviours"]["module_paths"], ["enemy_logic", "player_logic"])
        self.assertTrue(
            any(
                usage["source_kind"] == "scene"
                and usage["entity_name"] == "Player"
                and usage["script_path"] == "scripts/player_logic.py"
                and usage["module_path"] == "player_logic"
                and usage["run_in_edit_mode"] is True
                and usage["public_data_shape"] == [
                    {"key": "god_mode", "value_type": "bool"},
                    {"key": "lives", "value_type": "int"},
                    {"key": "spawn", "value_type": "object"},
                ]
                for usage in usages
            )
        )
        self.assertTrue(any(usage["source_kind"] == "prefab" for usage in usages))

    def test_asset_catalog_prefabs_scripts_and_relevant_metadata_are_exported(self) -> None:
        self._write_asset("assets/hero.png")
        self._write_script("scripts/player_logic.py")
        self._write_prefab(
            "prefabs/player.json",
            {
                "root_name": "PlayerPrefab",
                "entities": [
                    {
                        "name": "PlayerPrefab",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": _transform(),
                            "Sprite": {
                                "enabled": True,
                                "texture": {"path": "assets/hero.png", "guid": ""},
                                "texture_path": "assets/hero.png",
                            },
                        },
                    }
                ],
            },
        )
        self.asset_service.save_metadata(
            "assets/hero.png",
            {"labels": ["player", "sprite"], "asset_type": "sprite_sheet", "import_mode": "grid"},
        )

        artifacts = ProjectContextPackGenerator(self.project_service, self.asset_service).generate()
        payload = self._load_json_artifact(artifacts.json_path)

        self.assertTrue(any(item["path"] == "assets/hero.png" for item in payload["assets"]["catalog"]))
        self.assertEqual(payload["assets"]["prefabs"], ["prefabs/player.json"])
        self.assertEqual(payload["assets"]["scripts"], ["scripts/player_logic.py"])
        self.assertTrue(
            any(
                item["path"] == "assets/hero.png"
                and item["labels"] == ["player", "sprite"]
                and item["asset_type"] == "sprite_sheet"
                for item in payload["assets"]["relevant_metadata"]
            )
        )

    def test_live_workspace_state_is_included_when_api_is_available(self) -> None:
        self._write_scene(
            "levels/live_scene.json",
            {"name": "Live Scene", "entities": [], "rules": [], "feature_metadata": {"scene_flow": {"next_scene": "levels/main_scene.json"}}},
        )
        api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        try:
            api.load_level("levels/live_scene.json")
            artifacts = ProjectContextPackGenerator(self.project_service, self.asset_service, api=api).generate()
            payload = self._load_json_artifact(artifacts.json_path)

            self.assertEqual(payload["scenes"]["active_scene"]["path"], "levels/live_scene.json")
            self.assertTrue(any(scene["path"] == "levels/live_scene.json" for scene in payload["scenes"]["open_scenes"]))
            self.assertEqual(payload["scenes"]["active_scene_flow_connections"]["next_scene"], "levels/main_scene.json")
        finally:
            api.shutdown()


if __name__ == "__main__":
    unittest.main()
