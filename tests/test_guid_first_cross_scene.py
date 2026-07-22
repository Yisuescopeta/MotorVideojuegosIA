import json
import tempfile
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager
from engine.scenes.refs import SceneAssetRef
from engine.serialization.schema import (
    ResolvedSceneReference,
    canonicalize_scene_cross_references,
    migrate_scene_data,
    validate_no_session_only_references,
)


TARGET_GUID = "11111111-1111-1111-1111-111111111111"


def _resolver(path: str) -> ResolvedSceneReference | None:
    if path == "levels/target.json":
        return ResolvedSceneReference(SceneAssetRef(TARGET_GUID, path), "target-id")
    return None


class GuidFirstCrossSceneTests(unittest.TestCase):
    def test_v2_path_migrates_to_guid_and_target_entity_id(self) -> None:
        payload = migrate_scene_data(
            {
                "schema_version": 2,
                "name": "Source",
                "entities": [
                    {
                        "id": "portal-id",
                        "name": "Portal",
                        "components": {
                            "SceneLink": {
                                "target_path": "levels/target.json",
                                "target_entity_name": "Target",
                            }
                        },
                    }
                ],
            }
        )

        canonical = canonicalize_scene_cross_references(payload, _resolver)
        link = canonical["entities"][0]["components"]["SceneLink"]
        self.assertEqual(link["target_scene"], {"guid": TARGET_GUID, "path_hint": "levels/target.json"})
        self.assertEqual(link["target_entity_id"], "target-id")
        self.assertNotIn("target_path", link)

    def test_path_hint_changes_without_changing_guid(self) -> None:
        payload = {
            "schema_version": 3,
            "name": "Source",
            "entities": [
                {
                    "id": "portal-id",
                    "name": "Portal",
                    "components": {
                        "SceneLink": {
                            "target_scene": {"guid": TARGET_GUID, "path_hint": "levels/old.json"},
                            "target_entity_id": "target-id",
                        }
                    },
                }
            ],
        }
        canonical = canonicalize_scene_cross_references(
            payload,
            lambda _path: ResolvedSceneReference(SceneAssetRef(TARGET_GUID, "levels/new.json"), "target-id"),
        )
        link = canonical["entities"][0]["components"]["SceneLink"]
        self.assertEqual(link["target_scene"]["guid"], TARGET_GUID)
        self.assertEqual(link["target_scene"]["path_hint"], "levels/old.json")

    def test_unresolved_reference_blocks_migration_and_session_ids_never_persist(self) -> None:
        payload = {
            "schema_version": 3,
            "name": "Source",
            "open_document_id": "session-only",
            "entities": [
                {
                    "id": "portal-id",
                    "name": "Portal",
                    "components": {"SceneTransitionAction": {"target_scene_path": "levels/missing.json"}},
                }
            ],
        }
        self.assertTrue(validate_no_session_only_references(payload))
        with self.assertRaises(ValueError):
            canonicalize_scene_cross_references(payload, _resolver)

    def test_scene_manager_writer_emits_v3_and_backup(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.set_scene_reference_resolver(_resolver)
        manager.load_scene(
            {
                "name": "Source",
                "entities": [
                    {
                        "id": "portal-id",
                        "name": "Portal",
                        "components": {
                            "SceneLink": {
                                "target_path": "levels/target.json",
                                "target_entity_id": "target-id",
                            }
                        },
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"
            path.write_text(json.dumps({"old": True}), encoding="utf-8")
            self.assertTrue(manager.save_scene_to_file(str(path)))
            saved = json.loads(path.read_text(encoding="utf-8"))
            link = saved["entities"][0]["components"]["SceneLink"]
            self.assertEqual(link["target_scene"]["guid"], TARGET_GUID)
            self.assertNotIn("target_path", link)
            self.assertTrue((path.with_name("source.json.bak")).exists())


if __name__ == "__main__":
    unittest.main()
