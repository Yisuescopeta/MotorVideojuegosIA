import copy
import inspect
import unittest

import engine.scenes.change_history as change_history_module
from engine.scenes.change_history import SceneChangeCoordinator


class _History:
    def __init__(self) -> None:
        self.operations: list[dict] = []

    def push(self, label, undo, redo) -> None:
        self.operations.append({"label": label, "undo": undo, "redo": redo})


class SceneChangeCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = SceneChangeCoordinator()
        self.history = _History()
        self.coordinator.set_history_manager(self.history)

    def test_coordinator_is_passive_and_has_no_authoring_context(self) -> None:
        module_source = inspect.getsource(change_history_module)
        class_source = inspect.getsource(SceneChangeCoordinator)

        self.assertFalse(hasattr(change_history_module, "SceneChangeCoordinatorContext"))
        self.assertNotIn("_dispatch", class_source)
        self.assertNotIn("engine.authoring.changes", module_source)
        self.assertNotIn("SceneWorkspaceEntry", module_source)
        self.assertNotIn("entry.dirty", module_source)
        for crud_name in (
            "_apply_edit_component",
            "_apply_set_entity_property",
            "_apply_add_component",
            "_apply_remove_component",
            "_apply_create_entity",
            "_apply_delete_entity",
        ):
            self.assertFalse(hasattr(self.coordinator, crud_name))

    def test_transaction_copies_payloads_and_builds_repeatable_restore_closures(self) -> None:
        before = {"name": "Before", "entities": [{"name": "Hero", "tag": "Old"}]}
        change = {"kind": "set_entity_property", "value": {"tag": "New"}}
        self.assertTrue(
            self.coordinator.begin_transaction(label="edit", scene_key="scene-a", before=before)
        )
        self.assertTrue(self.coordinator.has_active_transaction)
        self.assertEqual(self.coordinator.active_transaction_scene_key, "scene-a")
        self.assertTrue(self.coordinator.append_transaction_change(change))
        before["entities"][0]["tag"] = "Poisoned"
        change["value"]["tag"] = "Poisoned"
        restored: list[tuple[str, dict]] = []

        def restore(key: str, payload: dict) -> bool:
            restored.append((key, payload))
            payload["entities"][0]["tag"] = "Mutated by restore"
            return True

        after = {"name": "After", "entities": [{"name": "Hero", "tag": "New"}]}
        result = self.coordinator.commit_transaction(after, restore)
        after["entities"][0]["tag"] = "Poisoned"

        self.assertEqual(
            result,
            {
                "label": "edit",
                "scene_key": "scene-a",
                "changes": [{"kind": "set_entity_property", "value": {"tag": "New"}}],
            },
        )
        self.assertFalse(self.coordinator.has_active_transaction)
        self.assertIsNone(self.coordinator.active_transaction_scene_key)
        self.assertEqual(len(self.history.operations), 1)
        operation = self.history.operations[0]
        self.assertTrue(operation["undo"]())
        self.assertTrue(operation["undo"]())
        self.assertTrue(operation["redo"]())
        self.assertTrue(operation["redo"]())
        self.assertEqual(
            [(key, payload["entities"][0]["tag"]) for key, payload in restored],
            [
                ("scene-a", "Mutated by restore"),
                ("scene-a", "Mutated by restore"),
                ("scene-a", "Mutated by restore"),
                ("scene-a", "Mutated by restore"),
            ],
        )
        self.assertIsNot(restored[0][1], restored[1][1])
        self.assertIsNot(restored[2][1], restored[3][1])

    def test_active_transaction_is_the_only_history_suspension(self) -> None:
        self.coordinator.record_snapshot_change(
            label="outside",
            undo=lambda: True,
            redo=lambda: True,
        )
        self.assertTrue(
            self.coordinator.begin_transaction(
                label="group",
                scene_key="scene-a",
                before={"name": "Same"},
            )
        )
        self.coordinator.record_snapshot_change(
            label="nested-snapshot",
            undo=lambda: True,
            redo=lambda: True,
        )
        self.coordinator.record_differential_change(
            label="nested-differential",
            undo=lambda: True,
            redo=lambda: True,
        )
        self.assertEqual(self.coordinator.commit_transaction({"name": "Same"}, lambda _key, _data: True), {
            "label": "group",
            "scene_key": "scene-a",
            "changes": [],
        })
        self.coordinator.record_differential_change(
            label="after",
            undo=lambda: True,
            redo=lambda: True,
        )

        self.assertEqual([item["label"] for item in self.history.operations], ["outside", "after"])

    def test_failed_push_keeps_transaction_available_for_rollback(self) -> None:
        class _FailingHistory:
            def push(self, label, undo, redo) -> None:
                raise RuntimeError("push failed")

        self.coordinator.set_history_manager(_FailingHistory())
        self.assertTrue(
            self.coordinator.begin_transaction(
                label="edit",
                scene_key="scene-a",
                before={"tag": "Old"},
            )
        )
        with self.assertRaisesRegex(RuntimeError, "push failed"):
            self.coordinator.commit_transaction({"tag": "New"}, lambda _key, _data: True)
        self.assertTrue(self.coordinator.has_active_transaction)
        restored: list[tuple[str, dict]] = []

        self.assertTrue(
            self.coordinator.rollback_transaction(
                lambda key, data: restored.append((key, copy.deepcopy(data))) is None
            )
        )
        self.assertEqual(restored, [("scene-a", {"tag": "Old"})])
        self.assertFalse(self.coordinator.has_active_transaction)

    def test_discard_and_missing_operations_are_explicit(self) -> None:
        self.assertFalse(self.coordinator.append_transaction_change({"kind": "noop"}))
        self.assertIsNone(self.coordinator.commit_transaction({}, lambda _key, _data: True))
        self.assertFalse(self.coordinator.rollback_transaction(lambda _key, _data: True))
        self.assertFalse(self.coordinator.discard_transaction())
        self.assertTrue(
            self.coordinator.begin_transaction(label="discard", scene_key="scene-a", before={})
        )
        self.assertFalse(
            self.coordinator.begin_transaction(label="nested", scene_key="scene-b", before={})
        )
        self.assertTrue(self.coordinator.discard_transaction())
        self.assertFalse(self.coordinator.has_active_transaction)

        self.assertTrue(
            self.coordinator.begin_transaction(label="missing-after", scene_key="scene-a", before={})
        )
        self.assertIsNone(
            self.coordinator.commit_transaction(None, lambda _key, _data: True)
        )
        self.assertFalse(self.coordinator.has_active_transaction)

        self.assertTrue(
            self.coordinator.begin_transaction(label="failed-restore", scene_key="scene-a", before={})
        )
        self.assertFalse(self.coordinator.rollback_transaction(lambda _key, _data: False))
        self.assertFalse(self.coordinator.has_active_transaction)

    def test_no_backend_accepts_records_and_transactions_without_history(self) -> None:
        coordinator = SceneChangeCoordinator()
        coordinator.record_snapshot_change(label="snapshot", undo=lambda: True, redo=lambda: True)
        coordinator.record_differential_change(
            label="differential",
            undo=lambda: True,
            redo=lambda: True,
        )
        self.assertTrue(
            coordinator.begin_transaction(label="group", scene_key="scene-a", before={"tag": "old"})
        )
        self.assertEqual(
            coordinator.commit_transaction({"tag": "new"}, lambda _key, _data: True),
            {"label": "group", "scene_key": "scene-a", "changes": []},
        )


if __name__ == "__main__":
    unittest.main()
