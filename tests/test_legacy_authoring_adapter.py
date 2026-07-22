import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.result import CommandErrorCode, Err
from engine.scenes.scene_manager import SceneManager


def _payload() -> dict[str, object]:
    return {
        "name": "Legacy",
        "entities": [
            {
                "id": "hero-id",
                "name": "Hero",
                "components": {
                    "Transform": {
                        "x": 1.0,
                        "y": 2.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            }
        ],
    }


class LegacyWorldAuthoringAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(_payload())
        self.entry = self.manager.resolve_entry(None)
        assert self.entry is not None and self.entry.edit_world is not None
        self.entity = self.entry.edit_world.get_entity_by_serialized_id("hero-id")
        assert self.entity is not None

    def test_explicit_lease_commit_imports_only_scoped_world_changes(self) -> None:
        opened = self.manager.legacy_authoring_adapter.open_lease(
            self.entry,
            consumer="test.consumer",
            owner="test.owner",
            mutation_scope=frozenset({"Transform"}),
        )
        self.assertFalse(isinstance(opened, Err))
        assert hasattr(opened, "value")
        transform = self.entity.get_component(Transform)
        assert transform is not None
        transform.x = 72.0

        result = self.manager.legacy_authoring_adapter.commit(opened.value)

        self.assertFalse(isinstance(result, Err))
        self.assertEqual(self.entry.scene.find_entity_by_id("hero-id")["components"]["Transform"]["x"], 72.0)
        self.assertFalse(self.manager.legacy_authoring_adapter.has_open_lease(self.entry))
        self.assertEqual(self.manager.legacy_authoring_adapter.consumer_metrics["test.consumer"], 1)

    def test_scope_violation_rolls_back_and_closes_lease(self) -> None:
        opened = self.manager.legacy_authoring_adapter.open_lease(
            self.entry,
            consumer="test.scope",
            owner="test.owner",
            mutation_scope=frozenset({"Transform"}),
        )
        assert hasattr(opened, "value")
        self.entity.get_component(Transform).x = 72.0
        self.entry.edit_world.feature_metadata["unscoped"] = True

        result = self.manager.legacy_authoring_adapter.commit(opened.value)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.error.code, CommandErrorCode.VALIDATION_FAILED)
        self.assertFalse(self.manager.legacy_authoring_adapter.has_open_lease(self.entry))
        self.assertEqual(self.entry.scene.find_entity_by_id("hero-id")["components"]["Transform"]["x"], 1.0)

    def test_save_play_and_switch_never_import_pending_legacy_world(self) -> None:
        before_scene = copy.deepcopy(self.entry.scene.to_snapshot_dict())
        adapter = self.manager.legacy_authoring_adapter
        adapter_commit = Mock(wraps=adapter.commit)
        adapter.commit = adapter_commit
        transform = self.entity.get_component(Transform)
        assert transform is not None
        transform.x = 72.0
        self.manager.mark_edit_world_dirty(reason="legacy_authoring")

        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.manager.save_scene_to_file(str(Path(tmp) / "blocked.json")))
        self.assertIsNone(self.manager.enter_play())
        self.assertEqual(self.entry.scene.to_snapshot_dict(), before_scene)
        adapter_commit.assert_not_called()
        self.assertFalse(self.manager.legacy_authoring_adapter.has_open_lease(self.entry))


if __name__ == "__main__":
    unittest.main()
