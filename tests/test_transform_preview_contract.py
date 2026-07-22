import copy
import unittest

from engine.editor.transform_preview import (
    TransformPreviewCoordinator,
    TransformPreviewState,
)
from engine.editor.editor_preview_coordinator import EditorPreviewCoordinator
from engine.levels.component_registry import create_default_registry
from engine.scenes.preview_leases import PreviewCancelReason, PreviewLeaseRegistry
from engine.scenes.projection_integrity import AuthoringProjectionFingerprintService
from engine.scenes.refs import EntityRef
from engine.scenes.result import CommandError, CommandErrorCode, Err, Result
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
        self.preview_coordinator = EditorPreviewCoordinator(self.leases)
        self.manager.set_preview_coordinator(self.preview_coordinator)
        self.commit_mode = "ok"
        self.coordinator = TransformPreviewCoordinator(
            self.manager._workspace,
            self.preview_coordinator,
            self._commit_transform,
        )
        self.target = EntityRef(self.entry.open_scene_ref, "hero-id")

    def _restore(self, key: str, payload: dict[str, object]) -> bool:
        entry = self.manager.resolve_entry(key)
        if entry is None:
            return False
        self.manager._workspace.replace_entry_scene(entry, payload)
        return True

    def _commit_transform(self, target: EntityRef, state: TransformPreviewState) -> Result[None] | bool:
        if self.commit_mode == "error":
            return Err(CommandError(CommandErrorCode.VALIDATION_FAILED, "synthetic commit rejection"))
        if self.commit_mode == "exception":
            raise RuntimeError("synthetic commit exception")
        entry = self.manager.resolve_entry(self.entry.key)
        assert entry is not None
        return self.manager.apply_transform_state_by_id(
            target.entity_id,
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

    def test_preview_update_keeps_revision_and_commit_bumps_once(self) -> None:
        initial_revision = self.entry.scene.revision
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        state = TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75)

        self.assertNotIsInstance(self.coordinator.update(started.value, state), Err)
        self.assertEqual(self.entry.scene.revision, initial_revision)
        self.assertNotIsInstance(self.coordinator.commit(started.value, state), Err)
        self.assertEqual(self.entry.scene.revision, initial_revision + 1)

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

    def test_target_deleted_during_preview_cancels_and_releases(self) -> None:
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        self.assertTrue(self.manager.remove_entity_by_id("hero-id"))

        result = self.coordinator.update(
            started.value,
            TransformPreviewState(3.0, 4.0, 0.0, 1.0, 1.0),
        )

        self.assertIsInstance(result, Err)
        self.assertEqual(result.error.code, CommandErrorCode.CONFLICT)
        self.assertEqual(self.preview_coordinator.active_for(self.entry.open_document_id), ())

    def test_commit_result_error_restores_overlay_and_releases(self) -> None:
        before_scene = copy.deepcopy(self.entry.scene.to_snapshot_dict())
        before_revision = self.entry.scene.revision
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        state = TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75)
        self.assertNotIsInstance(self.coordinator.update(started.value, state), Err)
        self.commit_mode = "error"

        result = self.coordinator.commit(started.value, state)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.error.code, CommandErrorCode.VALIDATION_FAILED)
        self.assertEqual(self.entry.scene.to_snapshot_dict(), before_scene)
        self.assertEqual(self.entry.scene.revision, before_revision)
        self.assertEqual(self.preview_coordinator.active_for(self.entry.open_document_id), ())
        self.assertEqual(self.history.records, [])

    def test_commit_exception_restores_overlay_and_releases(self) -> None:
        before_scene = copy.deepcopy(self.entry.scene.to_snapshot_dict())
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        state = TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75)
        self.assertNotIsInstance(self.coordinator.update(started.value, state), Err)
        self.commit_mode = "exception"

        result = self.coordinator.commit(started.value, state)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.error.code, CommandErrorCode.INTERNAL_ERROR)
        self.assertEqual(self.entry.scene.to_snapshot_dict(), before_scene)
        self.assertEqual(self.preview_coordinator.active_for(self.entry.open_document_id), ())
        self.assertEqual(self.history.records, [])

    def test_drag_without_changes_cancels_without_history(self) -> None:
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")

        result = self.coordinator.commit(
            started.value,
            TransformPreviewState(1.0, 2.0, 0.0, 1.0, 1.0),
        )

        self.assertNotIsInstance(result, Err)
        self.assertEqual(self.preview_coordinator.active_for(self.entry.open_document_id), ())
        self.assertEqual(self.history.records, [])

    def test_save_cancels_preview_before_protected_boundary(self) -> None:
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        state = TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75)
        self.assertNotIsInstance(self.coordinator.update(started.value, state), Err)

        with self.subTest(action="save"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as directory:
                self.assertTrue(self.manager.save_scene_to_file(str(Path(directory) / "scene.json")))
        self.assertEqual(self.preview_coordinator.active_for(self.entry.open_document_id), ())

    def test_play_cancels_preview_before_runtime_projection(self) -> None:
        started = self.coordinator.begin(self.target)
        assert hasattr(started, "value")
        state = TransformPreviewState(10.0, 20.0, 15.0, 1.5, 0.75)
        self.assertNotIsInstance(self.coordinator.update(started.value, state), Err)

        runtime = self.manager.enter_play()

        self.assertIsNotNone(runtime)
        self.assertEqual(self.preview_coordinator.active_for(self.entry.open_document_id), ())

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
