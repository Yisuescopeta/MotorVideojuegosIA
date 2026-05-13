import unittest

from engine.editor.ui.property_widgets import (
    EditTransaction,
    PropertyDescriptor,
    PropertyEditResult,
    PropertyKind,
)


class EditorUIPropertyWidgetsTests(unittest.TestCase):
    def test_property_descriptor_autofills_display_name(self) -> None:
        descriptor = PropertyDescriptor("move_speed", PropertyKind.FLOAT)

        self.assertEqual(descriptor.display_name, "Move Speed")

    def test_transaction_set_get_dirty_and_rollback(self) -> None:
        tx = EditTransaction({"Transform": {"x": 1}})

        tx.set_value("Transform", "x", 2)


        self.assertTrue(tx.is_dirty())
        self.assertTrue(tx.is_dirty("Transform", "x"))
        self.assertEqual(tx.dirty_groups(), ["Transform"])
        self.assertEqual(tx.dirty_properties("Transform"), ["x"])
        self.assertEqual(tx.dirty_properties(), [("Transform", "x")])
        self.assertEqual(tx.get_value("Transform", "x"), 2)

        tx.rollback()

        self.assertFalse(tx.is_dirty())
        self.assertEqual(tx.get_value("Transform", "x"), 1)

    def test_transaction_commit_without_callback_fails_and_preserves_dirty(self) -> None:
        tx = EditTransaction({"Entity": {"name": "Old"}})
        tx.set_value("Entity", "name", "New")

        results = tx.commit()

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)
        self.assertEqual(results[0].old_value, "Old")
        self.assertEqual(results[0].new_value, "New")
        self.assertTrue(tx.is_dirty("Entity", "name"))

    def test_transaction_success_commit_clears_dirty_and_updates_value(self) -> None:
        tx = EditTransaction({"Entity": {"active": False}})
        tx.set_commit_callback(lambda group, prop, old, new: True)
        tx.set_value("Entity", "active", True)

        results = tx.commit()

        self.assertTrue(results[0].success)
        self.assertFalse(tx.is_dirty())
        self.assertTrue(tx.get_value("Entity", "active"))

    def test_transaction_failure_commit_preserves_dirty_and_original_result(self) -> None:
        tx = EditTransaction({"Transform": {"x": 1}})
        tx.set_commit_callback(
            lambda group, prop, old, new: PropertyEditResult(group, prop, False, "blocked")
        )
        tx.set_value("Transform", "x", 2)

        results = tx.commit()

        self.assertFalse(results[0].success)
        self.assertEqual(results[0].error, "blocked")
        self.assertEqual(results[0].old_value, 1)
        self.assertEqual(results[0].new_value, 2)
        self.assertTrue(tx.is_dirty("Transform", "x"))
        self.assertEqual(tx.get_value("Transform", "x"), 2)

    def test_transaction_partial_commit_preserves_only_failed_dirty(self) -> None:
        tx = EditTransaction({"Entity": {"name": "Old", "active": False}})

        def commit(group: str, prop: str, old: object, new: object) -> PropertyEditResult:
            return PropertyEditResult(group, prop, prop == "name", "bad" if prop == "active" else None)

        tx.set_commit_callback(commit)
        tx.set_value("Entity", "name", "New")
        tx.set_value("Entity", "active", True)

        results = tx.commit()

        self.assertEqual([result.success for result in results], [True, False])
        self.assertFalse(tx.is_dirty("Entity", "name"))
        self.assertTrue(tx.is_dirty("Entity", "active"))
        self.assertEqual(tx.get_value("Entity", "name"), "New")
        self.assertTrue(tx.get_value("Entity", "active"))


if __name__ == "__main__":
    unittest.main()
