import copy
import inspect
import unittest
from unittest.mock import Mock, patch

import engine.scenes.prefab_overrides as prefab_overrides_module
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.scenes.contracts import PrefabOverridePort
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.scene import Scene
from engine.scenes.structural_authoring import (
    SceneHierarchyAuthoring,
    ScenePrefabAuthoring,
    SceneStructuralAuthoring,
    SceneStructuralAuthoringContext,
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
    root_scene_data = scene.find_entity(serialized_root_name)
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

        def unused(*args, **kwargs):
            return None

        structural = SceneStructuralAuthoring(
            SceneStructuralAuthoringContext(
                get_active_entry=unused,
                resolve_entry=unused,
                flush_pending_edit_world=unused,
                rebuild_edit_world=unused,
                record_scene_change=unused,
                sync_scene_links_from_feature_metadata=unused,
                unique_entity_name=unused,
            ),
            port,
            Mock(),
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
        rebuild = Mock()
        record = Mock()

        def unused(*args, **kwargs):
            return None

        serializable_entities = Mock()
        context = SceneStructuralAuthoringContext(
            get_active_entry=lambda: entry,
            resolve_entry=unused,
            flush_pending_edit_world=unused,
            rebuild_edit_world=rebuild,
            record_scene_change=record,
            sync_scene_links_from_feature_metadata=unused,
            unique_entity_name=unused,
        )
        hierarchy = SceneHierarchyAuthoring(context, serializable_entities)
        return (
            ScenePrefabAuthoring(context, hierarchy, serializable_entities),
            rebuild,
            record,
        )

    def test_apply_overrides_clears_via_primitive_after_save(self) -> None:
        entry, root = _entry(legacy_overrides={"": {"tag": "Enemy"}})
        before = entry.scene.to_dict()
        root_id = root["id"]
        authoring, rebuild, record = self._authoring(entry)
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
        rebuild.assert_called_once_with(entry)
        record.assert_called_once()

    def test_apply_overrides_install_failure_is_atomic(self) -> None:
        for name, primitive in (
            ("false", False),
            ("exception", RuntimeError("install failed")),
        ):
            with self.subTest(name=name):
                entry, _root = _entry(legacy_overrides={"": {"tag": "Enemy"}})
                before = entry.scene.to_dict()
                authoring, rebuild, record = self._authoring(entry)
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
                rebuild.assert_not_called()
                record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
