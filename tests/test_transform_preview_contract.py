import copy
import unittest

from engine.editor.transform_preview import (
    TransformPreviewCoordinator,
    TransformPreviewState,
)
from engine.levels.component_registry import create_default_registry
from engine.scenes.preview_leases import PreviewCancelReason, PreviewLeaseRegistry
from engine.scenes.projection_integrity import AuthoringProjectionFingerprintService
from engine.scenes.refs import EntityRef
from engine.scenes.result import CommandErrorCode, Err
from engine.scenes.scene_manager import SceneManager


class _History:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_snapshot_change(self, *, label, undo, redo) -> None:
        self.records.append({"label": label, "undo": undo, "redo": redo})

    def record_differential_change(self, *, label, undo, redo) -> None:
        raise AssertionError("transform preview must use one snapshot history entry")


def _payload() -> dict[str, object]:
    return {
        "name": "Transform Preview",
        "entities": [
            {
                "id": "hero-id",
                "name": "Hero",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 1.0,
                        "y": 2.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


class TransformPreviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(_payload())
        self.entry = self.manager.resolve_entry(None)
        assert self.entry is not None
        self.history = _History()
        self.leases = PreviewLeaseRegistry(
            AuthoringProjectionFingerprintService(self.manager._projection.create_world),
            history=self.history,
            restore_snapshot=self._restore,
        )
        self.coordinator = TransformPreviewCoordinator(
            self.manager._workspace,
            self.leases,
            self._commit_transform,
        )
        self.target = EntityRef(self.entry.open_scene_ref, "hero-id")

    def _restore(self, key: str, payload: dict[str, object]) -> bool:
        entry = self.manager.resolve_entry(key)
        if entry is None:
            return False
        self.manager._workspace.replace_entry_scene(entry, payload)
        return True

    def _commit_transform(self, target: EntityRef, state: TransformPreviewState) -> bool:
        entry = self.manager.resolve_entry(self.entry.key)
        assert entry is not None
        entity = entry.scene.find_entity_by_id(target.entity_id)
        assert entity is not None
        return self.manager.apply_transform_state(
            entity["name"],
            {
                "x": state.x,
                "y": state.y,
                "rotation": state.rotation,
                "scale_x": state.scale_x,
                "scale_y": state.scale_y,
            },
            key_or_path=entry.key,
            record_history=False,
            label="transform_preview",
        )

    def test_begin_and_update_keep_scene_unchanged(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_snapshot_dict())
        started = self.coordinator.begin(self.target)
        self.assertNotIsInstance(started, Err)
        assert hasattr(started, "value")

        updated = self.coordinator.update(
            started.value,
            TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75),
        )

        self.assertNotIsInstance(updated, Err)
        self.assertEqual(self.entry.scene.to_snapshot_dict(), before)
        self.assertEqual(self.history.records, [])

    def test_commit_is_single_snapshot_history_entry(self) -> None:
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        state = TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75)

        committed = self.coordinator.commit(started.value, state)

        self.assertNotIsInstance(committed, Err)
        self.assertEqual(len(self.history.records), 1)
        transform = self.entry.scene.find_entity_by_id("hero-id")["components"]["Transform"]
        self.assertEqual(transform["x"], 10.0)
        self.assertEqual(transform["scale_y"], 0.75)
        self.assertIsNone(self.leases.active_for_scene(self.entry.key))

    def test_revision_conflict_cancels_lease(self) -> None:
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        self.assertTrue(self.manager.create_entity("OutsidePreview"))

        result = self.coordinator.update(
            started.value,
            TransformPreviewState(3.0, 4.0, 0.0, 1.0, 1.0),
        )

        self.assertIsInstance(result, Err)
        self.assertEqual(result.error.code, CommandErrorCode.CONFLICT)
        self.assertIsNone(self.leases.active_for_scene(self.entry.key))

    def test_cancel_releases_lease_without_scene_write(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_snapshot_dict())
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")

        result = self.coordinator.cancel(started.value, PreviewCancelReason.POINTER_CAPTURE_LOST)

        self.assertNotIsInstance(result, Err)
        self.assertEqual(self.entry.scene.to_snapshot_dict(), before)
        self.assertEqual(self.history.records, [])

    def test_state_rejects_non_finite_values(self) -> None:
        with self.assertRaises(ValueError):
            TransformPreviewState(float("nan"), 0.0, 0.0, 1.0, 1.0)


if __name__ == "__main__":
    unittest.main()
