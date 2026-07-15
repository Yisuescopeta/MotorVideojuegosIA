import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from engine.components.transform import Transform
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes import scene_persistence
from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON
from engine.scenes.scene_manager import COMPACT_SCENE_SAVE_SEPARATORS, SceneManager
from engine.scenes.scene_persistence import (
    LoadedScenePayload,
    SavedSceneResult,
    ScenePersistenceService,
    SceneStorageReadError,
)
from engine.scenes.storage import SceneStorage
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _scene_payload() -> dict:
    return {
        "name": "PersistenceContract",
        "entities": [
            {
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
            },
            {
                "name": "Enemy",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {},
            },
        ],
        "rules": [],
        "feature_metadata": {},
    }


class _DirectJsonStorage(SceneStorage):
    def __init__(self, *, fail_save: bool = False, fail_load: bool = False) -> None:
        self.fail_save = fail_save
        self.fail_load = fail_load
        self.save_calls: list[Path] = []
        self.load_calls: list[Path] = []

    def save(self, path: str | Path, payload: dict) -> None:
        target = Path(path)
        self.save_calls.append(target)
        if self.fail_save:
            raise OSError("custom save failed")
        target.write_text(json.dumps(payload), encoding="utf-8")

    def load(self, path: str | Path) -> dict:
        target = Path(path)
        self.load_calls.append(target)
        if self.fail_load:
            raise OSError("custom readback failed")
        return json.loads(target.read_text(encoding="utf-8"))


class _PayloadStorage(SceneStorage):
    def __init__(self, payload: dict | None = None, *, load_error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.load_error = load_error

    def save(self, path: str | Path, payload: dict) -> None:
        _ = path, payload

    def load(self, path: str | Path) -> dict:
        _ = path
        if self.load_error is not None:
            raise self.load_error
        return copy.deepcopy(self.payload)


class _FailIfCalledStorage(SceneStorage):
    def __init__(self) -> None:
        self.save_calls = 0
        self.load_calls = 0

    def save(self, path: str | Path, payload: dict) -> None:
        _ = path, payload
        self.save_calls += 1
        raise AssertionError("inactive pending save reached storage")

    def load(self, path: str | Path) -> dict:
        _ = path
        self.load_calls += 1
        raise AssertionError("inactive pending save reached storage")


class ScenePersistenceContractTests(unittest.TestCase):
    def test_scene_manager_reexports_compact_save_separators_from_persistence(self) -> None:
        self.assertIs(COMPACT_SCENE_SAVE_SEPARATORS, scene_persistence.COMPACT_SCENE_SAVE_SEPARATORS)
        self.assertEqual(COMPACT_SCENE_SAVE_SEPARATORS, (",", ":"))

    def test_service_returns_explicit_load_and_save_results(self) -> None:
        service = ScenePersistenceService()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scene.json"
            with patch.object(service, "get_mtime", return_value=1234.5):
                saved = service.save(target, _scene_payload())
                loaded = service.load(target)

        self.assertIsInstance(saved, SavedSceneResult)
        self.assertEqual(saved.resolved_path, str(target.resolve()))
        self.assertEqual(saved.entity_count, 2)
        self.assertEqual(saved.mtime, 1234.5)
        self.assertIsInstance(loaded, LoadedScenePayload)
        self.assertEqual(loaded.resolved_path, str(target.resolve()))
        self.assertEqual(len(loaded.payload["entities"]), 2)
        self.assertEqual(loaded.mtime, 1234.5)

    def test_default_storage_semantic_validation_error_propagates(self) -> None:
        payload = _scene_payload()
        payload["entities"][1]["name"] = "Hero"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "invalid.json"
            target.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate entity name"):
                SceneManager(create_default_registry()).load_scene_from_file(target.as_posix())

    def test_custom_storage_semantic_installation_error_propagates(self) -> None:
        payload = _scene_payload()
        payload["entities"][0]["tag"] = "MainCamera"
        payload["entities"][0]["components"]["Camera2D"] = {
            "enabled": True,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "zoom": 0.0,
            "rotation": 0.0,
            "is_primary": True,
            "follow_entity": "",
            "framing_mode": "platformer",
            "dead_zone_width": 0.0,
            "dead_zone_height": 0.0,
            "clamp_left": None,
            "clamp_right": None,
            "clamp_top": None,
            "clamp_bottom": None,
            "recenter_on_play": True,
        }

        with self.assertRaises(ValueError):
            SceneManager(create_default_registry()).load_scene_from_file(
                "invalid.custom",
                storage=_PayloadStorage(payload),
            )

    def test_post_read_migration_and_validation_errors_propagate_unchanged(self) -> None:
        failure_cases = (
            ("migration", "engine.scenes.scene_persistence.migrate_scene_data"),
            ("validation", "engine.scenes.scene_persistence.validate_scene_data"),
        )

        for phase, patch_target in failure_cases:
            with self.subTest(phase=phase):
                failure = RuntimeError(f"{phase} failed")
                with patch(patch_target, side_effect=failure):
                    with self.assertRaises(RuntimeError) as raised:
                        SceneManager(create_default_registry()).load_scene_from_file(
                            f"invalid-{phase}.custom",
                            storage=_PayloadStorage(_scene_payload()),
                        )

                self.assertIs(raised.exception, failure)

    def test_default_storage_read_failure_returns_none(self) -> None:
        manager = SceneManager(create_default_registry())
        with patch(
            "engine.scenes.scene_persistence.JsonSceneStorage.load",
            side_effect=OSError("default read failed"),
        ):
            self.assertIsNone(manager.load_scene_from_file("missing.json"))

    def test_custom_storage_read_failure_returns_none(self) -> None:
        manager = SceneManager(create_default_registry())

        self.assertIsNone(
            manager.load_scene_from_file(
                "missing.custom",
                storage=_PayloadStorage(load_error=OSError("custom read failed")),
            )
        )

    def test_service_read_error_preserves_storage_failure_as_cause(self) -> None:
        storage_error = OSError("custom read failed")

        with self.assertRaises(SceneStorageReadError) as raised:
            ScenePersistenceService().load(
                "missing.custom",
                storage=_PayloadStorage(load_error=storage_error),
            )

        self.assertIs(raised.exception.__cause__, storage_error)

    def _dirty_manager(self) -> tuple[SceneManager, object, dict, str]:
        manager = SceneManager(create_default_registry())
        manager.load_scene(_scene_payload())
        self.assertTrue(manager.update_entity_property("Hero", "tag", "Edited"))
        entry = manager.resolve_entry(manager.active_scene_key)
        self.assertIsNotNone(entry)
        return manager, entry, copy.deepcopy(manager.current_scene.to_dict()), manager.active_scene_key

    def _assert_failed_save_preserves_memory(
        self,
        manager: SceneManager,
        entry: object,
        memory_before: dict,
        key_before: str,
    ) -> None:
        self.assertIs(manager.resolve_entry(key_before), entry)
        self.assertEqual(manager.active_scene_key, key_before)
        self.assertEqual(manager.current_scene.to_dict(), memory_before)
        self.assertEqual(entry.source_path, "")
        self.assertTrue(entry.dirty)
        self.assertFalse(entry.edit_world_sync_pending)
        self.assertIsNotNone(entry.edit_world.get_entity_by_name("Hero"))

    def test_temp_write_failure_keeps_previous_target_and_cleans_temp(self) -> None:
        manager, entry, memory_before, key_before = self._dirty_manager()

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scene.json"
            target.write_text('{"name": "previous"}', encoding="utf-8")
            with patch(
                "engine.scenes.scene_persistence.JsonSceneStorage.save",
                side_effect=OSError("temp write failed"),
            ):
                saved = manager.save_scene_to_file(target.as_posix())

            self.assertFalse(saved)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"name": "previous"}')
            self.assertFalse(target.with_name("scene.json.tmp").exists())

        self._assert_failed_save_preserves_memory(manager, entry, memory_before, key_before)

    def test_replace_failure_keeps_previous_target_and_cleans_temp(self) -> None:
        manager, entry, memory_before, key_before = self._dirty_manager()

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scene.json"
            target.write_text('{"name": "previous"}', encoding="utf-8")
            with patch("pathlib.Path.replace", side_effect=OSError("replace failed")):
                saved = manager.save_scene_to_file(target.as_posix())

            self.assertFalse(saved)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"name": "previous"}')
            self.assertFalse(target.with_name("scene.json.tmp").exists())

        self._assert_failed_save_preserves_memory(manager, entry, memory_before, key_before)

    def test_custom_storage_save_failure_keeps_direct_target_and_workspace_state(self) -> None:
        manager, entry, memory_before, key_before = self._dirty_manager()
        callbacks: list[str] = []
        manager.register_on_scene_saved(lambda path, _info: callbacks.append(path))
        storage = _DirectJsonStorage(fail_save=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "custom.scene"
            target.write_text('{"name": "previous"}', encoding="utf-8")

            saved = manager.save_scene_to_file(target.as_posix(), storage=storage)

            self.assertFalse(saved)
            self.assertEqual(storage.save_calls, [target])
            self.assertEqual(storage.load_calls, [])
            self.assertEqual(target.read_text(encoding="utf-8"), '{"name": "previous"}')
            self.assertFalse(target.with_name("custom.scene.tmp").exists())

        self.assertEqual(callbacks, [])
        self._assert_failed_save_preserves_memory(manager, entry, memory_before, key_before)

    def test_custom_storage_readback_failure_keeps_direct_write_without_installing(self) -> None:
        manager, entry, memory_before, key_before = self._dirty_manager()
        callbacks: list[str] = []
        manager.register_on_scene_saved(lambda path, _info: callbacks.append(path))
        storage = _DirectJsonStorage(fail_load=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "custom.scene"
            target.write_text('{"name": "previous"}', encoding="utf-8")

            saved = manager.save_scene_to_file(target.as_posix(), storage=storage)

            self.assertFalse(saved)
            self.assertEqual(storage.save_calls, [target])
            self.assertEqual(storage.load_calls, [target])
            persisted = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(persisted["name"], "PersistenceContract")
            self.assertEqual(persisted["entities"][0]["tag"], "Edited")
            self.assertFalse(target.with_name("custom.scene.tmp").exists())

        self.assertEqual(callbacks, [])
        self._assert_failed_save_preserves_memory(manager, entry, memory_before, key_before)

    def test_inactive_legacy_pending_save_rejects_before_projection_or_storage(self) -> None:
        manager = SceneManager(create_default_registry())
        history = UndoRedoManager()
        manager.set_history_manager(history)
        manager.load_scene(_scene_payload())
        pending_key = manager.active_scene_key
        pending_entry = manager.resolve_entry(pending_key)
        assert pending_entry is not None and pending_entry.edit_world is not None
        self.assertTrue(manager.set_selected_entity("Hero"))
        pending_scene = pending_entry.scene
        pending_world = pending_entry.edit_world
        hero = pending_world.get_entity_by_name("Hero")
        assert hero is not None
        transform = hero.get_component(Transform)
        assert transform is not None
        transform.x = 42.0
        self.assertTrue(manager.mark_edit_world_dirty(LEGACY_AUTHORING_SYNC_REASON))
        scene_payload = copy.deepcopy(pending_scene.to_dict())
        world_payload = copy.deepcopy(pending_world.serialize())
        pending_state = (
            pending_entry.dirty,
            pending_entry.dirty_before_pending_edit_world_sync,
            pending_entry.pending_edit_world_sync_reason,
            pending_entry.selected_entity_name,
            pending_entry.selected_entity_id,
            pending_entry.edit_world_version,
            pending_world.version,
        )
        manager.create_new_scene("Other", activate=True)
        active_key = manager.active_scene_key
        keys_before = tuple(item["key"] for item in manager.list_open_scenes())
        source_path_before = pending_entry.source_path
        callbacks: list[str] = []
        manager.register_on_scene_saved(lambda path, _info: callbacks.append(path))
        storage = _FailIfCalledStorage()

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "inactive.scene"
            with (
                patch.object(manager._edit_sync, "flush_pending") as flush,
                patch.object(manager._workspace, "rebuild_edit_world") as rebuild,
                patch.object(manager._projection, "validate_payload") as validate,
                patch.object(
                    manager._persistence,
                    "save",
                    wraps=manager._persistence.save,
                ) as persist,
            ):
                saved = manager.save_scene_to_file(
                    target.as_posix(),
                    key=pending_key,
                    storage=storage,
                )

            self.assertFalse(saved)
            self.assertFalse(target.exists())
            flush.assert_not_called()
            rebuild.assert_not_called()
            validate.assert_not_called()
            persist.assert_not_called()

        self.assertEqual(storage.save_calls, 0)
        self.assertEqual(storage.load_calls, 0)
        self.assertEqual(callbacks, [])
        self.assertFalse(history.can_undo())
        self.assertFalse(history.can_redo())
        self.assertEqual(manager.active_scene_key, active_key)
        self.assertEqual(
            tuple(item["key"] for item in manager.list_open_scenes()),
            keys_before,
        )
        self.assertIs(manager.resolve_entry(pending_key), pending_entry)
        self.assertEqual(pending_entry.key, pending_key)
        self.assertEqual(pending_entry.source_path, source_path_before)
        self.assertIs(pending_entry.scene, pending_scene)
        self.assertIs(pending_entry.edit_world, pending_world)
        self.assertEqual(pending_entry.scene.to_dict(), scene_payload)
        self.assertEqual(pending_entry.edit_world.serialize(), world_payload)
        self.assertEqual(
            (
                pending_entry.dirty,
                pending_entry.dirty_before_pending_edit_world_sync,
                pending_entry.pending_edit_world_sync_reason,
                pending_entry.selected_entity_name,
                pending_entry.selected_entity_id,
                pending_entry.edit_world_version,
                pending_entry.edit_world.version,
            ),
            pending_state,
        )

    def test_post_replace_failures_preserve_memory_without_rolling_back_disk(self) -> None:
        failure_phases = ("readback", "migration", "validation", "entity_count", "install")

        for phase in failure_phases:
            with self.subTest(phase=phase):
                manager, entry, memory_before, key_before = self._dirty_manager()
                callbacks: list[str] = []
                manager.register_on_scene_saved(lambda path, _info: callbacks.append(path))

                with tempfile.TemporaryDirectory() as temp_dir:
                    target = Path(temp_dir) / "scene.json"
                    target.write_text('{"name": "previous"}', encoding="utf-8")
                    with ExitStack() as stack:
                        if phase == "readback":
                            stack.enter_context(
                                patch(
                                    "engine.scenes.scene_persistence.JsonSceneStorage.load",
                                    side_effect=OSError("readback failed"),
                                )
                            )
                        elif phase == "migration":
                            stack.enter_context(
                                patch(
                                    "engine.scenes.scene_persistence.migrate_scene_data",
                                    side_effect=ValueError("migration failed"),
                                )
                            )
                        elif phase == "validation":
                            stack.enter_context(
                                patch(
                                    "engine.scenes.scene_persistence.validate_scene_data",
                                    return_value=["post-write validation failed"],
                                )
                            )
                        elif phase == "entity_count":
                            mismatched = copy.deepcopy(memory_before)
                            mismatched["entities"] = []
                            stack.enter_context(
                                patch(
                                    "engine.scenes.scene_persistence.JsonSceneStorage.load",
                                    return_value=mismatched,
                                )
                            )
                        else:
                            stack.enter_context(
                                patch.object(
                                    SceneWorkspace,
                                    "install_entry_state",
                                    side_effect=ValueError("install failed"),
                                )
                            )

                        saved = manager.save_scene_to_file(target.as_posix())

                    self.assertFalse(saved)
                    persisted = json.loads(target.read_text(encoding="utf-8"))
                    self.assertEqual(persisted["name"], "PersistenceContract")
                    self.assertEqual(len(persisted["entities"]), 2)
                    self.assertEqual(persisted["entities"][0]["tag"], "Edited")
                    self.assertFalse(target.with_name("scene.json.tmp").exists())

                self.assertEqual(callbacks, [])
                self._assert_failed_save_preserves_memory(manager, entry, memory_before, key_before)


if __name__ == "__main__":
    unittest.main()
