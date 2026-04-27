import json
import tempfile
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager
from engine.scenes.storage import ChunkedSceneStorage, JsonSceneStorage


class SceneStorageTests(unittest.TestCase):
    def test_json_scene_storage_load_returns_payload_dict(self) -> None:
        payload = {
            "name": "Storage Probe",
            "entities": [],
            "rules": [],
            "feature_metadata": {},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "scene.json"
            scene_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            loaded = JsonSceneStorage().load(scene_path)

        self.assertEqual(loaded, payload)

    def test_json_scene_storage_pretty_save_writes_current_json_format(self) -> None:
        payload = {"name": "Pretty", "entities": [], "rules": [], "feature_metadata": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "scene.json"
            JsonSceneStorage().save(scene_path, payload)
            persisted_text = scene_path.read_text(encoding="utf-8")

        self.assertIn("\n    ", persisted_text)
        self.assertEqual(json.loads(persisted_text), payload)

    def test_json_scene_storage_compact_save_writes_compact_valid_json(self) -> None:
        payload = {"name": "Compact", "entities": [{"name": "Player"}], "rules": []}

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "scene.json"
            JsonSceneStorage(compact=True).save(scene_path, payload)
            persisted_text = scene_path.read_text(encoding="utf-8")

        self.assertNotIn("\n    ", persisted_text)
        self.assertEqual(json.loads(persisted_text), payload)

    def test_json_scene_storage_still_writes_single_file(self) -> None:
        payload = {"name": "Single File", "entities": [{"name": "Player"}], "rules": [], "feature_metadata": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "single_scene.json"
            JsonSceneStorage().save(scene_path, payload)

            self.assertTrue(scene_path.is_file())
            self.assertFalse((Path(temp_dir) / "single_scene.scene").exists())

    def test_chunked_scene_storage_roundtrips_5000_entities_in_chunks(self) -> None:
        payload = {
            "name": "Chunked Probe",
            "schema_version": 2,
            "entities": [
                {
                    "name": f"Entity_{index:04d}",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {},
                }
                for index in range(5000)
            ],
            "rules": [],
            "feature_metadata": {"chunked_probe": {"enabled": True}},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir) / "large.scene"
            ChunkedSceneStorage(chunk_size=1000).save(scene_dir, payload)

            self.assertTrue((scene_dir / "scene.json").is_file())
            for chunk_index in range(5):
                self.assertTrue((scene_dir / "entities" / f"chunk_{chunk_index:04d}.json").is_file())
            manifest = json.loads((scene_dir / "scene.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["chunks"]), 5)
            self.assertNotIn("entities", manifest)

            loaded = ChunkedSceneStorage(chunk_size=1000).load(scene_dir)

        self.assertEqual(loaded, payload)

    def test_chunked_scene_storage_rejects_payload_without_entity_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "entities is a list"):
                ChunkedSceneStorage().save(Path(temp_dir) / "invalid.scene", {"name": "Invalid"})

    def test_chunked_scene_storage_fails_when_manifest_chunk_is_missing(self) -> None:
        payload = {
            "name": "Missing Chunk",
            "schema_version": 2,
            "entities": [{"name": "Entity", "active": True, "tag": "Untagged", "layer": "Default", "components": {}}],
            "rules": [],
            "feature_metadata": {},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir) / "missing.scene"
            ChunkedSceneStorage().save(scene_dir, payload)
            (scene_dir / "entities" / "chunk_0000.json").unlink()

            with self.assertRaisesRegex(FileNotFoundError, "chunk not found"):
                ChunkedSceneStorage().load(scene_dir)

    def test_scene_manager_uses_chunked_storage_only_when_opted_in(self) -> None:
        payload = {
            "name": "Manager Chunked",
            "schema_version": 2,
            "entities": [
                {"name": f"Entity_{index}", "active": True, "tag": "Untagged", "layer": "Default", "components": {}}
                for index in range(12)
            ],
            "rules": [],
            "feature_metadata": {},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = Path(temp_dir) / "manager.scene"
            manager = SceneManager(create_default_registry())
            manager.load_scene(payload)

            self.assertTrue(
                manager.save_scene_to_file(
                    scene_dir.as_posix(),
                    storage=ChunkedSceneStorage(chunk_size=5),
                )
            )

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(
                reloaded.load_scene_from_file(
                    scene_dir.as_posix(),
                    storage=ChunkedSceneStorage(chunk_size=5),
                )
            )

        self.assertEqual(len(reloaded.current_scene.entities_data), 12)
        self.assertEqual(reloaded.current_scene.entities_data[-1]["name"], "Entity_11")


if __name__ == "__main__":
    unittest.main()
