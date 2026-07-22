import copy
import inspect
import unittest
from unittest.mock import Mock, patch

import engine.scenes.prefab_overrides as prefab_overrides_module
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.contracts import PrefabOverridePort
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.scene import Scene
from engine.scenes.scene_manager import SceneManager
from engine.scenes.structural_authoring import (
    ScenePrefabAuthoring,
    SceneStructuralAuthoring,
)
from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


def _entry(
    *,
    legacy_overrides: dict | None = None,
    serialized_root_name: str = "Instance",
    runtime_root_name: str = "Instance",
) -> tuple[SceneWorkspaceEntry, dict]:
    scene = Scene(
        name="Prefab Overrides",
        data={
            "name": "Prefab Overrides",
            "entities": [
                {
                    "name": serialized_root_name,
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "prefab_instance": {
                        "prefab_path": "prefabs/enemy.prefab",
                        "root_name": "Enemy",
                        "overrides": copy.deepcopy(legacy_overrides or {}),
                    },
                    "components": {},
                }
            ],
            "rules": [],
            "feature_metadata": {},
        },
    )
    root_scene_data = scene._find_entity_mutable(serialized_root_name)
    assert root_scene_data is not None

    world = World()
    root = Entity(runtime_root_name)
    root.serialized_id = root_scene_data["id"]
    root.prefab_root_name = runtime_root_name
    root.prefab_source_path = ""
    root.prefab_instance = copy.deepcopy(root_scene_data["prefab_instance"])
    world.add_entity(root)

    child = Entity(f"{runtime_root_name}/Weapon")
    child.prefab_root_name = runtime_root_name
    child.prefab_source_path = "Weapon"
    world.add_entity(child)

    return (
        SceneWorkspaceEntry(key="prefab-scene", scene=scene, edit_world=world),
        root_scene_data,
    )


class PrefabOverrideServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PrefabOverrideService()

    def test_update_component_property_targets_child_copies_and_upserts(self) -> None:
        entry, root = _entry()
        value = {"curve": [1, 2]}

        self.assertTrue(
            self.service.update_component_property(
                entry,
                "Instance/Weapon",
                "Transform",
                "x",
                value,
            )
        )
        value["curve"].append(3)
        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"][0]["value"],
            {"curve": [1, 2]},
        )
        self.assertTrue(
            self.service.update_component_property(
                entry,
                "Instance/Weapon",
                "Transform",
                "x",
                {"curve": [4]},
            )
        )

        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"],
            [
                {
                    "op": "set_field",
                    "target": "Weapon",
                    "component": "Transform",
                    "field": "x",
                    "value": {"curve": [4]},
                }
            ],
        )

    def test_update_entity_property_targets_root_copies_and_upserts(self) -> None:
        entry, root = _entry()
        groups = ["enemy"]

        self.assertTrue(self.service.update_entity_property(entry, "Instance", "groups", groups))
        groups.append("boss")
        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"][0]["value"],
            ["enemy"],
        )
        self.assertTrue(self.service.update_entity_property(entry, "Instance", "groups", ["elite"]))

        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"],
            [
                {
                    "op": "set_entity_property",
                    "target": "",
                    "field": "groups",
                    "value": ["elite"],
                }
            ],
        )

    def test_replace_component_copies_and_upserts_by_target_component(self) -> None:
        entry, root = _entry()
        component = {"enabled": True, "points": [[1, 2]]}

        self.assertTrue(
            self.service.replace_component(entry, "Instance/Weapon", "Collider", component)
        )
        component["points"][0].append(3)
        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"][0]["data"],
            {"enabled": True, "points": [[1, 2]]},
        )
        self.assertTrue(
            self.service.replace_component(
                entry,
                "Instance/Weapon",
                "Collider",
                {"enabled": False},
            )
        )

        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"],
            [
                {
                    "op": "replace_component",
                    "target": "Weapon",
                    "component": "Collider",
                    "data": {"enabled": False},
                }
            ],
        )

    def test_remove_component_replaces_previous_component_operations(self) -> None:
        entry, root = _entry()
        self.assertTrue(
            self.service.update_component_property(
                entry,
                "Instance/Weapon",
                "Collider",
                "width",
                12.0,
            )
        )
        self.assertTrue(
            self.service.replace_component(
                entry,
                "Instance/Weapon",
                "Collider",
                {"enabled": True},
            )
        )
        self.assertTrue(
            self.service.update_entity_property(entry, "Instance/Weapon", "tag", "Blade")
        )

        self.assertTrue(
            self.service.remove_component(entry, "Instance/Weapon", "Collider")
        )

        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"],
            [
                {
                    "op": "set_entity_property",
                    "target": "Weapon",
                    "field": "tag",
                    "value": "Blade",
                },
                {
                    "op": "remove_component",
                    "target": "Weapon",
                    "component": "Collider",
                },
            ],
        )

    def test_legacy_override_map_is_migrated_before_new_operation(self) -> None:
        legacy = {
            "": {
                "active": False,
                "components": {"Transform": {"x": 3.0}},
            },
            "Weapon": {
                "tag": "LegacyBlade",
                "components": {"Sprite": {"texture": "blade.png"}},
            },
        }
        entry, root = _entry(legacy_overrides=legacy)

        self.assertTrue(self.service.update_entity_property(entry, "Instance/Weapon", "layer", "Actors"))

        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"],
            [
                {"op": "set_entity_property", "target": "", "field": "active", "value": False},
                {
                    "op": "replace_component",
                    "target": "",
                    "component": "Transform",
                    "data": {"x": 3.0},
                },
                {
                    "op": "set_entity_property",
                    "target": "Weapon",
                    "field": "tag",
                    "value": "LegacyBlade",
                },
                {
                    "op": "replace_component",
                    "target": "Weapon",
                    "component": "Sprite",
                    "data": {"texture": "blade.png"},
                },
                {
                    "op": "set_entity_property",
                    "target": "Weapon",
                    "field": "layer",
                    "value": "Actors",
                },
            ],
        )

    def test_root_resolution_falls_back_to_serialized_id(self) -> None:
        entry, root = _entry(
            serialized_root_name="SerializedInstance",
            runtime_root_name="RuntimeInstance",
        )

        self.assertTrue(
            self.service.update_component_property(
                entry,
                "RuntimeInstance/Weapon",
                "Transform",
                "x",
                9.0,
            )
        )

        self.assertEqual(
            root["prefab_instance"]["overrides"]["operations"][0]["target"],
            "Weapon",
        )

    def test_invalid_targets_do_not_mutate_scene(self) -> None:
        entry, _root = _entry()
        before = entry.scene.to_dict()

        self.assertFalse(
            self.service.update_component_property(entry, "Missing", "Transform", "x", 2.0)
        )
        self.assertFalse(self.service.update_entity_property(entry, "Missing", "tag", "Enemy"))
        self.assertFalse(self.service.replace_component(entry, "Missing", "Sprite", {}))
        self.assertFalse(self.service.remove_component(entry, "Missing", "Sprite"))
        self.assertEqual(entry.scene.to_dict(), before)

        entry.edit_world = None
        self.assertFalse(self.service.update_entity_property(entry, "Instance", "tag", "Enemy"))
        self.assertEqual(entry.scene.to_dict(), before)

    def test_write_is_published_once_through_scene_primitive(self) -> None:
        entry, root = _entry()
        before = entry.scene.to_dict()
        root_id = root["id"]
        original_update = entry.scene.update_entity_property_by_id

        def install(entity_id, property_name, value):
            self.assertEqual(entry.scene.to_dict(), before)
            return original_update(entity_id, property_name, value)

        with patch.object(
            entry.scene,
            "update_entity_property_by_id",
            side_effect=install,
        ) as update:
            self.assertTrue(
                self.service.update_component_property(
                    entry,
                    "Instance/Weapon",
                    "Transform",
                    "x",
                    2.0,
                )
            )

        update.assert_called_once()
        self.assertEqual(update.call_args.args[:2], (root_id, "prefab_instance"))

    def test_primitive_failure_or_exception_leaves_scene_exact(self) -> None:
        for name, primitive in (
            ("false", False),
            ("exception", RuntimeError("install failed")),
        ):
            with self.subTest(name=name):
                entry, _root = _entry()
                before = entry.scene.to_dict()
                kwargs = (
                    {"side_effect": primitive}
                    if isinstance(primitive, Exception)
                    else {"return_value": primitive}
                )

                with patch.object(entry.scene, "update_entity_property_by_id", **kwargs):
                    self.assertFalse(
                        self.service.update_component_property(
                            entry,
                            "Instance/Weapon",
                            "Transform",
                            "x",
                            2.0,
                        )
                    )

                self.assertEqual(entry.scene.to_dict(), before)

    def test_port_and_service_dependency_surface_stays_narrow(self) -> None:
        port_methods = {
            name
            for name, value in vars(PrefabOverridePort).items()
            if callable(value) and not name.startswith("_")
        }
        source = inspect.getsource(prefab_overrides_module)

        self.assertEqual(
            port_methods,
            {
                "update_component_property",
                "update_entity_property",
                "replace_component",
                "remove_component",
                "update_component_property_by_id",
                "replace_component_by_id",
                "remove_component_by_id",
            },
        )
        for forbidden in (
            "structural_authoring",
            "scene_manager",
            "PrefabManager",
            "record_scene_change",
            "rebuild_edit_world",
            "SceneHierarchyAuthoring",
        ):
            self.assertNotIn(forbidden, source)

        structural_source = inspect.getsource(ScenePrefabAuthoring)
        self.assertNotIn('entity_data["prefab_instance"]["overrides"] = {}', structural_source)


class _RecordingOverridePort:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def update_component_property(self, *args) -> bool:
        self.calls.append(("update_component_property", *args))
        return True

    def update_entity_property(self, *args) -> bool:
        self.calls.append(("update_entity_property", *args))
        return True

    def replace_component(self, *args) -> bool:
        self.calls.append(("replace_component", *args))
        return True

    def remove_component(self, *args) -> bool:
        self.calls.append(("remove_component", *args))
        return True


class SceneStructuralOverrideDelegationTests(unittest.TestCase):
    def test_structural_authoring_delegates_only_the_four_override_operations(self) -> None:
        entry, _root = _entry()
        port = _RecordingOverridePort()

        structural = SceneStructuralAuthoring(
            Mock(),
            Mock(),
            Mock(),
            port,
        )

        self.assertTrue(
            structural.update_prefab_component_override(
                entry,
                "Instance/Weapon",
                "Transform",
                "x",
                2.0,
            )
        )
        self.assertTrue(
            structural.update_prefab_entity_override(
                entry,
                "Instance/Weapon",
                "tag",
                "Blade",
            )
        )
        self.assertTrue(
            structural.replace_prefab_component_override(
                entry,
                "Instance/Weapon",
                "Collider",
                {"enabled": True},
            )
        )
        self.assertTrue(
            structural.remove_prefab_component_override(
                entry,
                "Instance/Weapon",
                "Collider",
            )
        )

        self.assertEqual(
            [call[0] for call in port.calls],
            [
                "update_component_property",
                "update_entity_property",
                "replace_component",
                "remove_component",
            ],
        )


class ScenePrefabApplyOverrideMutationTests(unittest.TestCase):
    @staticmethod
    def _authoring(entry):
        workspace = Mock()
        workspace.get_active_entry.return_value = entry
        pipeline = Mock()
        pipeline.begin.return_value = (object(), copy.deepcopy(entry.scene.to_dict()))
        pipeline.commit_snapshot.return_value = True
        serializable_entities = Mock()
        return ScenePrefabAuthoring(workspace, pipeline, serializable_entities), pipeline

    def test_apply_overrides_clears_via_primitive_after_save(self) -> None:
        entry, root = _entry(legacy_overrides={"": {"tag": "Enemy"}})
        before = entry.scene.to_dict()
        root_id = root["id"]
        authoring, pipeline = self._authoring(entry)
        original_update = entry.scene.update_entity_property_by_id

        def install(entity_id, property_name, value):
            self.assertEqual(entry.scene.to_dict(), before)
            return original_update(entity_id, property_name, value)

        with patch("engine.assets.prefab.PrefabManager.save_prefab", return_value=True), patch.object(
            entry.scene,
            "update_entity_property_by_id",
            side_effect=install,
        ) as update:
            self.assertTrue(authoring.apply_prefab_overrides("Instance"))

        update.assert_called_once()
        self.assertEqual(update.call_args.args[:2], (root_id, "prefab_instance"))
        self.assertEqual(entry.scene.find_entity("Instance")["prefab_instance"]["overrides"], {})
        pipeline.begin.assert_called_once_with(
            entry,
            failure_context="apply_prefab_overrides:Instance",
            clone_world=True,
        )
        pipeline.commit_snapshot.assert_called_once()
        pipeline.rollback.assert_not_called()

    def test_apply_overrides_install_failure_is_atomic(self) -> None:
        for name, primitive in (
            ("false", False),
            ("exception", RuntimeError("install failed")),
        ):
            with self.subTest(name=name):
                entry, _root = _entry(legacy_overrides={"": {"tag": "Enemy"}})
                before = entry.scene.to_dict()
                authoring, pipeline = self._authoring(entry)
                kwargs = (
                    {"side_effect": primitive}
                    if isinstance(primitive, Exception)
                    else {"return_value": primitive}
                )

                with patch(
                    "engine.assets.prefab.PrefabManager.save_prefab",
                    return_value=True,
                ), patch.object(entry.scene, "update_entity_property_by_id", **kwargs):
                    self.assertFalse(authoring.apply_prefab_overrides("Instance"))

                self.assertEqual(entry.scene.to_dict(), before)
                pipeline.rollback.assert_called_once()
                pipeline.commit_snapshot.assert_not_called()

    def test_apply_overrides_commit_false_does_not_run_second_rollback(self) -> None:
        entry, _root = _entry(legacy_overrides={"": {"tag": "Enemy"}})
        authoring, pipeline = self._authoring(entry)
        pipeline.commit_snapshot.return_value = False

        with patch(
            "engine.assets.prefab.PrefabManager.save_prefab",
            return_value=True,
        ):
            self.assertFalse(authoring.apply_prefab_overrides("Instance"))

        pipeline.commit_snapshot.assert_called_once()
        pipeline.rollback.assert_not_called()

    def test_apply_overrides_commit_exception_rolls_back_and_returns_false(self) -> None:
        entry, _root = _entry(legacy_overrides={"": {"tag": "Enemy"}})
        authoring, pipeline = self._authoring(entry)
        token = pipeline.begin.return_value[0]
        pipeline.commit_snapshot.side_effect = RuntimeError("commit failed")

        with patch(
            "engine.assets.prefab.PrefabManager.save_prefab",
            return_value=True,
        ):
            self.assertFalse(authoring.apply_prefab_overrides("Instance"))

        pipeline.commit_snapshot.assert_called_once()
        pipeline.rollback.assert_called_once_with(entry, token)


class ScenePrefabPostFlushStateTests(unittest.TestCase):
    @staticmethod
    def _authoring(entry):
        workspace = Mock()
        workspace.get_active_entry.return_value = entry
        pipeline = Mock()
        serializable_entities = Mock()
        return ScenePrefabAuthoring(workspace, pipeline, serializable_entities), pipeline

    def test_unpack_prefab_reads_scene_and_world_replaced_by_begin(self) -> None:
        entry, _root = _entry()
        post_entry, _post_root = _entry()
        post_entry.edit_world.get_entity_by_name("Instance/Weapon").parent_name = "Instance"
        stale_world = World()
        stale_root = Entity("Instance")
        stale_world.add_entity(stale_root)
        entry.edit_world = stale_world
        authoring, pipeline = self._authoring(entry)
        token = object()
        before = copy.deepcopy(post_entry.scene.to_dict())

        def begin(current_entry, **_kwargs):
            current_entry.scene = post_entry.scene
            current_entry.edit_world = post_entry.edit_world
            return token, before

        pipeline.begin.side_effect = begin
        pipeline.commit_snapshot.return_value = True

        self.assertTrue(authoring.unpack_prefab("Instance"))

        pipeline.begin.assert_called_once_with(
            entry,
            failure_context="unpack_prefab:Instance",
            clone_world=True,
        )
        self.assertIsNotNone(entry.scene.find_entity("Instance/Weapon"))
        self.assertIsNone(entry.scene.find_entity("Instance").get("prefab_instance"))

    def test_apply_overrides_uses_post_begin_state_and_clones_world(self) -> None:
        entry, _root = _entry()
        post_entry, post_root_data = _entry()
        stale_world = World()
        stale_root = Entity("Instance")
        stale_world.add_entity(stale_root)
        entry.edit_world = stale_world
        authoring, pipeline = self._authoring(entry)
        token = object()
        before = copy.deepcopy(post_entry.scene.to_dict())

        def begin(current_entry, **_kwargs):
            current_entry.scene = post_entry.scene
            current_entry.edit_world = post_entry.edit_world
            return token, before

        pipeline.begin.side_effect = begin
        pipeline.commit_snapshot.return_value = True

        with patch("engine.assets.prefab.PrefabManager.save_prefab", return_value=True) as save:
            self.assertTrue(authoring.apply_prefab_overrides("Instance"))

        pipeline.begin.assert_called_once_with(
            entry,
            failure_context="apply_prefab_overrides:Instance",
            clone_world=True,
        )
        saved_root = post_entry.edit_world.get_entity_by_name("Instance")
        save.assert_called_once_with(
            saved_root,
            "prefabs/enemy.prefab",
            world=post_entry.edit_world,
        )
        self.assertEqual(post_root_data["prefab_instance"]["overrides"], {})

    def test_create_prefab_without_replace_flushes_then_uses_new_world_only(self) -> None:
        entry, _root = _entry()
        post_entry, _post_root = _entry()
        stale_world = World()
        stale_world.add_entity(Entity("Stale"))
        entry.edit_world = stale_world
        authoring, pipeline = self._authoring(entry)

        def flush(current_entry, **_kwargs):
            current_entry.scene = post_entry.scene
            current_entry.edit_world = post_entry.edit_world
            return True

        pipeline.flush_pending.side_effect = flush

        with patch("engine.assets.prefab.PrefabManager.save_prefab", return_value=True) as save:
            self.assertTrue(authoring.create_prefab("Instance", "instance.prefab"))

        pipeline.flush_pending.assert_called_once_with(
            entry,
            failure_context="create_prefab:Instance",
        )
        pipeline.begin.assert_not_called()
        pipeline.commit_snapshot.assert_not_called()
        save.assert_called_once_with(
            post_entry.edit_world.get_entity_by_name("Instance"),
            "instance.prefab",
            world=post_entry.edit_world,
        )

    def test_apply_preserves_empty_override_shapes_only_for_the_owning_operation(self) -> None:
        manager = SceneManager(create_default_registry())
        history = UndoRedoManager()
        manager.set_history_manager(history)
        manager.load_scene(
            {
                "name": "Apply Override Shapes",
                "entities": [
                    {
                        "name": "Instance",
                        "prefab_instance": {
                            "prefab_path": "prefabs/enemy.prefab",
                            "root_name": "Enemy",
                            "overrides": {"": {"tag": "Enemy"}},
                        },
                        "components": {},
                    },
                    {
                        "name": "UnrelatedExplicit",
                        "prefab_instance": {
                            "prefab_path": "prefabs/other.prefab",
                            "root_name": "Other",
                            "overrides": {"operations": []},
                        },
                        "components": {},
                    },
                    {
                        "name": "UnrelatedCanonical",
                        "prefab_instance": {
                            "prefab_path": "prefabs/canonical.prefab",
                            "root_name": "Canonical",
                            "overrides": {"operations": []},
                        },
                        "components": {},
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None
        explicit = copy.deepcopy(
            entry.scene.find_entity("UnrelatedExplicit")["prefab_instance"]
        )
        explicit["overrides"] = {}
        self.assertTrue(
            entry.scene.update_entity_property(
                "UnrelatedExplicit",
                "prefab_instance",
                explicit,
            )
        )
        before_explicit = copy.deepcopy(
            entry.scene.find_entity("UnrelatedExplicit")["prefab_instance"]["overrides"]
        )
        before_canonical = copy.deepcopy(
            entry.scene.find_entity("UnrelatedCanonical")["prefab_instance"]["overrides"]
        )
        before_target = copy.deepcopy(
            entry.scene.find_entity("Instance")["prefab_instance"]["overrides"]
        )

        with patch("engine.assets.prefab.PrefabManager.save_prefab", return_value=True):
            self.assertTrue(manager.apply_prefab_overrides("Instance"))

        self.assertEqual(
            manager.find_entity_data("Instance")["prefab_instance"]["overrides"],
            {},
        )
        self.assertEqual(
            manager.find_entity_data("UnrelatedExplicit")["prefab_instance"]["overrides"],
            before_explicit,
        )
        self.assertEqual(
            manager.find_entity_data("UnrelatedCanonical")["prefab_instance"]["overrides"],
            before_canonical,
        )
        self.assertEqual(before_explicit, {})
        self.assertEqual(before_canonical, {"operations": []})
        edit_root = manager.get_edit_world().get_entity_by_name("Instance")
        self.assertEqual(edit_root.prefab_instance["overrides"], {})

        self.assertTrue(history.undo())
        self.assertEqual(
            manager.find_entity_data("Instance")["prefab_instance"]["overrides"],
            before_target,
        )
        self.assertEqual(
            manager.find_entity_data("UnrelatedExplicit")["prefab_instance"]["overrides"],
            before_explicit,
        )
        self.assertEqual(
            manager.find_entity_data("UnrelatedCanonical")["prefab_instance"]["overrides"],
            before_canonical,
        )
        edit_root = manager.get_edit_world().get_entity_by_name("Instance")
        self.assertEqual(edit_root.prefab_instance["overrides"], before_target)

        self.assertTrue(history.redo())
        self.assertEqual(
            manager.find_entity_data("Instance")["prefab_instance"]["overrides"],
            {},
        )
        self.assertEqual(
            manager.find_entity_data("UnrelatedExplicit")["prefab_instance"]["overrides"],
            before_explicit,
        )
        self.assertEqual(
            manager.find_entity_data("UnrelatedCanonical")["prefab_instance"]["overrides"],
            before_canonical,
        )
        edit_root = manager.get_edit_world().get_entity_by_name("Instance")
        self.assertEqual(edit_root.prefab_instance["overrides"], {})


if __name__ == "__main__":
    unittest.main()
