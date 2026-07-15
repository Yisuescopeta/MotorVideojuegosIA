import copy
import unittest
from unittest.mock import patch

import engine.scenes.change_history as change_history_module
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


def _scene_payload() -> dict:
    return {
        "schema_version": 2,
        "name": "History Atomicity",
        "entities": [
            {
                "id": "hero-id",
                "name": "Hero",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {},
                "component_metadata": {},
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


class SceneHistoryAtomicityTests(unittest.TestCase):
    def _manager_with_history(self) -> tuple[SceneManager, UndoRedoManager]:
        manager = SceneManager(create_default_registry())
        history = UndoRedoManager()
        manager.set_history_manager(history)
        manager.load_scene(_scene_payload())
        return manager, history

    def _seed_prior_redo(self, history: UndoRedoManager) -> list[str]:
        events: list[str] = []
        history.push(
            "prior",
            undo=lambda: events.append("prior_undo"),
            redo=lambda: events.append("prior_redo"),
        )
        self.assertTrue(history.undo())
        events.clear()
        self.assertFalse(history.can_undo())
        self.assertTrue(history.can_redo())
        return events

    @staticmethod
    def _push_then_raise(history: UndoRedoManager):
        original_push = history.push

        def push_then_raise(*args, **kwargs):
            original_push(*args, **kwargs)
            raise RuntimeError("push failed after append")

        return push_then_raise

    def test_undo_redo_checkpoint_roundtrip_restores_both_stacks(self) -> None:
        history = UndoRedoManager()
        events: list[str] = []
        history.push(
            "first",
            undo=lambda: events.append("first_undo"),
            redo=lambda: events.append("first_redo"),
        )
        history.push(
            "second",
            undo=lambda: events.append("second_undo"),
            redo=lambda: events.append("second_redo"),
        )
        self.assertTrue(history.undo())
        events.clear()
        checkpoint = history.capture_checkpoint()

        history.push("temporary", undo=lambda: None, redo=lambda: None)
        history.restore_checkpoint(checkpoint)

        self.assertTrue(history.can_undo())
        self.assertTrue(history.can_redo())
        self.assertTrue(history.redo())
        self.assertEqual(events, ["second_redo"])
        history.restore_checkpoint(checkpoint)
        events.clear()
        self.assertTrue(history.undo())
        self.assertEqual(events, ["first_undo"])
        with self.assertRaisesRegex(TypeError, "not created by UndoRedoManager"):
            history.restore_checkpoint(object())

    def test_snapshot_push_after_append_returns_false_and_restores_history(self) -> None:
        manager, history = self._manager_with_history()
        events = self._seed_prior_redo(history)
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None and entry.edit_world is not None
        self.assertTrue(manager.set_selected_entity("Hero"))
        scene_before = copy.deepcopy(entry.scene.to_dict())
        world_before = copy.deepcopy(entry.edit_world.serialize())

        with patch.object(
            history,
            "push",
            side_effect=self._push_then_raise(history),
        ):
            self.assertFalse(manager.set_feature_metadata("probe", {"value": 1}))

        self.assertEqual(entry.scene.to_dict(), scene_before)
        self.assertEqual(entry.edit_world.serialize(), world_before)
        self.assertEqual(entry.selected_entity_name, "Hero")
        self.assertFalse(entry.dirty)
        self.assertEqual(entry.edit_world_version, entry.edit_world.version)
        self.assertFalse(history.can_undo())
        self.assertTrue(history.can_redo())
        self.assertTrue(history.redo())
        self.assertEqual(events, ["prior_redo"])

    def test_differential_push_after_append_returns_false_and_restores_history(self) -> None:
        manager, history = self._manager_with_history()
        events = self._seed_prior_redo(history)
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None and entry.edit_world is not None
        self.assertTrue(manager.set_selected_entity("Hero"))
        scene_before = copy.deepcopy(entry.scene.to_dict())
        world_before = copy.deepcopy(entry.edit_world.serialize())

        with patch.object(
            history,
            "push",
            side_effect=self._push_then_raise(history),
        ):
            self.assertFalse(manager.create_entity("RejectedByHistory"))

        self.assertEqual(entry.scene.to_dict(), scene_before)
        self.assertEqual(entry.edit_world.serialize(), world_before)
        self.assertIsNone(entry.scene.find_entity("RejectedByHistory"))
        self.assertIsNone(entry.edit_world.get_entity_by_name("RejectedByHistory"))
        self.assertEqual(entry.selected_entity_name, "Hero")
        self.assertFalse(entry.dirty)
        self.assertEqual(entry.edit_world_version, entry.edit_world.version)
        self.assertFalse(history.can_undo())
        self.assertTrue(history.can_redo())
        self.assertTrue(history.redo())
        self.assertEqual(events, ["prior_redo"])

    def test_transaction_push_after_append_rethrows_and_remains_rollbackable(self) -> None:
        manager, history = self._manager_with_history()
        events = self._seed_prior_redo(history)
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None
        scene_before = copy.deepcopy(entry.scene.to_dict())
        self.assertTrue(manager.begin_transaction("tag-hero"))
        self.assertTrue(
            manager.apply_change(
                {
                    "kind": "set_entity_property",
                    "entity": "Hero",
                    "field": "tag",
                    "value": "Player",
                }
            )
        )

        with patch.object(
            history,
            "push",
            side_effect=self._push_then_raise(history),
        ):
            with self.assertRaisesRegex(RuntimeError, "push failed after append"):
                manager.commit_transaction()

        self.assertTrue(manager.rollback_transaction())
        self.assertEqual(entry.scene.to_dict(), scene_before)
        self.assertFalse(history.can_undo())
        self.assertTrue(history.can_redo())
        self.assertTrue(history.redo())
        self.assertEqual(events, ["prior_redo"])

    def test_restore_failure_keeps_push_error_and_chains_restore_error(self) -> None:
        manager, history = self._manager_with_history()
        self.assertTrue(manager.begin_transaction("tag-hero"))
        self.assertTrue(
            manager.apply_change(
                {
                    "kind": "set_entity_property",
                    "entity": "Hero",
                    "field": "tag",
                    "value": "Player",
                }
            )
        )

        with (
            patch.object(
                history,
                "push",
                side_effect=self._push_then_raise(history),
            ),
            patch.object(
                history,
                "restore_checkpoint",
                side_effect=RuntimeError("restore checkpoint failed"),
            ),
            patch.object(change_history_module, "log_err") as log_error,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "push failed after append",
            ) as raised:
                manager.commit_transaction()

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertEqual(str(raised.exception.__cause__), "restore checkpoint failed")
        log_error.assert_called_once_with(
            "SceneChangeCoordinator: failed to restore history checkpoint "
            "after push failure: restore checkpoint failed"
        )
        self.assertTrue(manager.rollback_transaction())


if __name__ == "__main__":
    unittest.main()
