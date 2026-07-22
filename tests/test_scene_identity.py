from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.refs import (
    ComponentRef,
    EntityRef,
    OpenDocumentId,
    OpenSceneRef,
    SceneAssetRef,
)
from engine.scenes.scene_manager import SceneManager


class SceneIdentityTests(unittest.TestCase):
    def test_reference_value_objects_are_typed_and_session_identity_is_uuid(self) -> None:
        document_id = OpenDocumentId.new()
        scene_ref = OpenSceneRef(document_id)
        entity_ref = EntityRef(scene_ref, "entity-1")
        component_ref = ComponentRef(entity_ref, "Transform")
        asset_ref = SceneAssetRef("11111111-1111-1111-1111-111111111111", "levels/main.json")

        self.assertEqual(component_ref.entity.scene.document_id, document_id)
        self.assertEqual(asset_ref.canonical_path_hint, "levels/main.json")
        self.assertNotEqual(document_id.value, asset_ref.guid)
        with self.assertRaises(ValueError):
            OpenDocumentId("not-a-uuid")

    def test_open_document_id_survives_save_and_rekey(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "Identity",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            }
        )
        entry = manager.resolve_entry(None)
        assert entry is not None
        document_id = entry.open_document_id

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "identity.json"
            self.assertTrue(manager.save_scene_to_file(target.as_posix(), key=entry.key))

        self.assertEqual(entry.open_document_id, document_id)
        self.assertEqual(entry.open_scene_ref.document_id, document_id)
        self.assertNotIn("open_document_id", entry.scene.to_dict())


if __name__ == "__main__":
    unittest.main()
