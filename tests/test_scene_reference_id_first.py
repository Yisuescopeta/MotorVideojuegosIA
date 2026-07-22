import copy
import unittest

from engine.assets.prefab import PrefabManager
from engine.serialization.schema import migrate_scene_data, validate_scene_data
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.scene import Scene
from tests.test_prefab_overrides import _entry


class SceneReferenceIdFirstTests(unittest.TestCase):
    def test_schema_v3_migrates_local_rules_signals_and_scene_links_to_ids(self) -> None:
        payload = migrate_scene_data(
            {
                "schema_version": 2,
                "name": "ReferenceScene",
                "entities": [
                    {
                        "id": "hero-id",
                        "name": "Hero",
                        "components": {"Transform": {}},
                    },
                    {
                        "id": "portal-id",
                        "name": "Portal",
                        "components": {
                            "SceneLink": {
                                "target_entity_name": "Hero",
                            }
                        },
                    },
                ],
                "rules": [
                    {
                        "event": "ready",
                        "do": [{"action": "destroy_entity", "entity": "Hero"}],
                    }
                ],
                "feature_metadata": {
                    "signals": {
                        "connections": [
                            {
                                "id": "connection-1",
                                "source": {"kind": "entity", "name": "Hero", "signal": "ready"},
                                "target": {
                                    "kind": "entity",
                                    "name": "Portal",
                                },
                                "callable": {"method": "handle"},
                            }
                        ]
                    }
                },
            }
        )

        self.assertEqual(payload["rules"][0]["do"][0]["entity_id"], "hero-id")
        link = payload["entities"][1]["components"]["SceneLink"]
        self.assertEqual(link["target_entity_id"], "hero-id")
        connection = payload["feature_metadata"]["signals"]["connections"][0]
        self.assertEqual(connection["source"]["id"], "hero-id")
        self.assertEqual(connection["target"]["id"], "portal-id")
        self.assertEqual(validate_scene_data(payload), [])

    def test_prefab_overrides_keep_target_id_for_child_operations(self) -> None:
        entry, root = _entry()
        child = entry.edit_world.get_entity_by_name("Instance/Weapon")
        self.assertIsNotNone(child)
        child.serialized_id = "weapon-id"

        service = PrefabOverrideService()
        self.assertTrue(
            service.replace_component_by_id(
                entry,
                "weapon-id",
                "Collider",
                {"enabled": True},
            )
        )
        operation = root["prefab_instance"]["overrides"]["operations"][0]
        self.assertEqual(operation["target"], "Weapon")
        self.assertEqual(operation["target_id"], "weapon-id")

        expanded = PrefabManager.expand_prefab_instance(
            {
                "schema_version": 2,
                "root_name": "Enemy",
                "entities": [
                    {"id": "prefab-root", "name": "Enemy", "components": {}},
                    {
                        "id": "weapon-id",
                        "name": "Weapon",
                        "parent": "",
                        "components": {},
                    },
                ],
            },
            instance_name="Instance",
            parent_name=None,
            prefab_path="prefabs/enemy.prefab",
            overrides=copy.deepcopy(root["prefab_instance"]["overrides"]),
        )
        weapon = next(item for item in expanded if item["name"] == "Instance/Weapon")
        self.assertEqual(weapon["components"]["Collider"], {"enabled": True})

    def test_rename_updates_only_reference_hints_and_preserves_ids(self) -> None:
        scene = Scene(
            name="RenameReferences",
            data={
                "schema_version": 3,
                "name": "RenameReferences",
                "entities": [
                    {"id": "hero-id", "name": "Hero", "components": {"Transform": {}}},
                    {
                        "id": "portal-id",
                        "name": "Portal",
                        "components": {
                            "SceneLink": {
                                "target_entity_name": "Hero",
                                "target_entity_id": "hero-id",
                            }
                        },
                    },
                ],
                "rules": [
                    {
                        "event": "ready",
                        "do": [{"action": "destroy_entity", "entity": "Hero", "entity_id": "hero-id"}],
                    }
                ],
                "feature_metadata": {
                    "signals": {
                        "connections": [
                            {
                                "id": "connection-1",
                                "source": {"kind": "entity", "id": "hero-id", "name": "Hero", "signal": "ready"},
                                "target": {"kind": "event_bus", "event": "ready"},
                            }
                        ]
                    }
                },
            },
        )

        self.assertTrue(scene.rename_entity_by_id("hero-id", "Champion"))
        payload = scene.to_dict()
        self.assertEqual(payload["entities"][0]["id"], "hero-id")
        self.assertEqual(payload["entities"][1]["components"]["SceneLink"]["target_entity_id"], "hero-id")
        self.assertEqual(payload["entities"][1]["components"]["SceneLink"]["target_entity_name"], "Champion")
        self.assertEqual(payload["rules"][0]["do"][0]["entity_id"], "hero-id")
        self.assertEqual(payload["rules"][0]["do"][0]["entity"], "Champion")
        self.assertEqual(payload["feature_metadata"]["signals"]["connections"][0]["source"]["id"], "hero-id")
        self.assertEqual(payload["feature_metadata"]["signals"]["connections"][0]["source"]["name"], "Champion")


if __name__ == "__main__":
    unittest.main()
