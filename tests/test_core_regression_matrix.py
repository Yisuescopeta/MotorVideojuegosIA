import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.transform import Transform
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager


class CoreRegressionMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        ProjectService(self.project_root)
        self._apis: list[EngineAPI] = []

    def tearDown(self) -> None:
        for api in reversed(self._apis):
            api.shutdown()
        self._temp_dir.cleanup()

    def _make_api(self) -> EngineAPI:
        api = EngineAPI(project_root=self.project_root.as_posix())
        self._apis.append(api)
        return api

    def _make_scene_manager(self) -> SceneManager:
        manager = SceneManager(create_default_registry())
        manager.set_history_manager(UndoRedoManager())
        return manager

    def _scene_path(self, filename: str) -> Path:
        return self.project_root / "levels" / filename

    def _prefab_path(self, filename: str) -> Path:
        return self.project_root / "prefabs" / filename

    def _write_json(self, path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _empty_scene(self, name: str) -> dict:
        return {"name": name, "entities": [], "rules": [], "feature_metadata": {}}

    def _transform(
        self,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> dict:
        return {
            "enabled": True,
            "x": x,
            "y": y,
            "rotation": rotation,
            "scale_x": scale_x,
            "scale_y": scale_y,
        }

    def _sprite(self, texture_path: str = "assets/hero.png", width: int = 32, height: int = 32) -> dict:
        return {
            "enabled": True,
            "texture_path": texture_path,
            "width": width,
            "height": height,
            "origin_x": 0.5,
            "origin_y": 0.5,
            "flip_x": False,
            "flip_y": False,
            "tint": [255, 255, 255, 255],
        }

    def _rect_transform(
        self,
        anchored_x: float = 0.0,
        anchored_y: float = 0.0,
        width: float = 200.0,
        height: float = 80.0,
    ) -> dict:
        return {
            "enabled": True,
            "anchor_min_x": 0.5,
            "anchor_min_y": 0.5,
            "anchor_max_x": 0.5,
            "anchor_max_y": 0.5,
            "pivot_x": 0.5,
            "pivot_y": 0.5,
            "anchored_x": anchored_x,
            "anchored_y": anchored_y,
            "width": width,
            "height": height,
            "rotation": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }

    def _button(self, target: str = "next_scene") -> dict:
        return {
            "enabled": True,
            "interactable": True,
            "label": "Play",
            "normal_color": [72, 72, 72, 255],
            "hover_color": [92, 92, 92, 255],
            "pressed_color": [56, 56, 56, 255],
            "disabled_color": [48, 48, 48, 200],
            "transition_scale_pressed": 0.96,
            "on_click": {"type": "load_scene_flow", "target": target},
        }

    def _scene_link(self, target_path: str = "levels/next.json", flow_key: str = "next_scene") -> dict:
        return {
            "enabled": True,
            "target_path": target_path,
            "flow_key": flow_key,
            "preview_label": "Next Scene",
        }

    def _find_entity(self, payload: dict, name: str) -> dict:
        for entity in payload.get("entities", []):
            if entity.get("name") == name:
                return entity
        raise AssertionError(f"Entity not found: {name}")

    def _build_dense_scene_payload(self, name: str) -> dict:
        return {
            "name": name,
            "entities": [
                {
                    "name": "Root",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {"Transform": self._transform(100.0, 50.0)},
                    "component_metadata": {"Transform": {"origin": "fixture"}},
                },
                {
                    "name": "Hero",
                    "parent": "Root",
                    "active": True,
                    "tag": "Player",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": self._transform(10.0, 5.0),
                        "Sprite": self._sprite(),
                    },
                    "component_metadata": {
                        "Transform": {"origin": "fixture"},
                        "Sprite": {"origin": "fixture", "note": "baseline"},
                    },
                },
                {
                    "name": "Companion",
                    "parent": "Hero",
                    "active": True,
                    "tag": "Support",
                    "layer": "Gameplay",
                    "components": {"Transform": self._transform(3.0, 4.0)},
                    "component_metadata": {"Transform": {"origin": "fixture"}},
                },
                {
                    "name": "MenuButton",
                    "parent": "Root",
                    "active": True,
                    "tag": "UI",
                    "layer": "UI",
                    "components": {
                        "RectTransform": self._rect_transform(24.0, -16.0, 220.0, 72.0),
                        "UIButton": self._button(),
                    },
                    "component_metadata": {"UIButton": {"origin": "fixture"}},
                },
            ],
            "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "keep"}]}],
            "feature_metadata": {
                "scene_flow": {"next_scene": "levels/next.json"},
                "render_2d": {"sorting_layers": ["Default", "Gameplay", "UI"]},
            },
        }

    def _build_equivalent_scene_via_api(self, api: EngineAPI) -> dict:
        scene_path = self._scene_path("equivalent_api.json")
        self._write_json(scene_path, self._empty_scene("EquivalentScene"))
        api.load_level("levels/equivalent_api.json")

        self.assertTrue(self.api_result(api.create_entity("Root", {"Transform": self._transform(16.0, 8.0)})))
        self.assertTrue(
            self.api_result(
                api.create_child_entity(
                    "Root",
                    "Hero",
                    {"Transform": self._transform(5.0, 2.0)},
                )
            )
        )
        self.assertTrue(self.api_result(api.add_component("Hero", "Sprite", self._sprite("assets/equivalent.png", 16, 16))))
        self.assertTrue(self.api_result(api.edit_component("Hero", "Transform", "x", 24.0)))
        self.assertTrue(self.api_result(api.set_entity_tag("Hero", "Player")))
        self.assertTrue(self.api_result(api.set_entity_layer("Hero", "Gameplay")))
        self.assertTrue(self.api_result(api.add_component("Root", "SceneLink", self._scene_link())))
        self.assertTrue(self.api_result(api.set_feature_metadata("render_2d", {"sorting_layers": ["Default", "Gameplay"]})))

        return api.scene_manager.current_scene.to_dict()

    def _build_equivalent_scene_via_manager(self, manager: SceneManager) -> dict:
        manager.load_scene(self._empty_scene("EquivalentScene"))

        self.assertTrue(manager.create_entity("Root", {"Transform": self._transform(16.0, 8.0)}))
        self.assertTrue(manager.create_child_entity("Root", "Hero", {"Transform": self._transform(5.0, 2.0)}))
        self.assertTrue(manager.add_component_to_entity("Hero", "Sprite", self._sprite("assets/equivalent.png", 16, 16)))
        self.assertTrue(manager.apply_edit_to_world("Hero", "Transform", "x", 24.0))
        self.assertTrue(manager.update_entity_property("Hero", "tag", "Player"))
        self.assertTrue(manager.update_entity_property("Hero", "layer", "Gameplay"))
        self.assertTrue(manager.add_component_to_entity("Root", "SceneLink", self._scene_link()))
        self.assertTrue(manager.set_feature_metadata("render_2d", {"sorting_layers": ["Default", "Gameplay"]}))

        return manager.current_scene.to_dict()

    def api_result(self, result: dict) -> bool:
        return bool(result.get("success"))

    def test_load_edit_save_load_preserves_relevant_serializable_content(self) -> None:
        scene_path = self._scene_path("matrix_dense_scene.json")
        self._write_json(scene_path, self._build_dense_scene_payload("DenseMatrix"))

        api = self._make_api()
        api.load_level("levels/matrix_dense_scene.json")

        self.assertTrue(api.scene_manager.set_selected_entity("Companion"))
        self.assertTrue(self.api_result(api.edit_component("Hero", "Transform", "x", 42.0)))
        self.assertTrue(self.api_result(api.edit_component("Hero", "Transform", "y", 18.0)))
        self.assertTrue(api.scene_manager.set_component_metadata("Hero", "Sprite", {"origin": "matrix", "note": "edited"}))
        self.assertTrue(self.api_result(api.set_feature_metadata("input_profile", {"source": "regression"})))
        self.assertTrue(self.api_result(api.save_scene(path=scene_path.as_posix())))

        persisted = self._read_json(scene_path)
        self.assertEqual(api.scene_manager.current_scene.to_dict(), persisted)
        self.assertEqual(api.game.world.selected_entity_name, "Hero")

        hero = api.game.world.get_entity_by_name("Hero")
        companion = api.game.world.get_entity_by_name("Companion")
        self.assertEqual(hero.parent_name, "Root")
        self.assertEqual(companion.parent_name, "Hero")
        self.assertEqual(hero.get_component(Transform).local_x, 42.0)
        self.assertEqual(companion.get_component(Transform).x, 145.0)

        reloaded_api = self._make_api()
        reloaded_api.load_level("levels/matrix_dense_scene.json")

        self.assertEqual(reloaded_api.scene_manager.current_scene.to_dict(), persisted)
        reloaded_hero = reloaded_api.game.world.get_entity_by_name("Hero")
        reloaded_companion = reloaded_api.game.world.get_entity_by_name("Companion")
        reloaded_button = reloaded_api.game.world.get_entity_by_name("MenuButton")
        self.assertEqual(reloaded_hero.parent_name, "Root")
        self.assertEqual(reloaded_companion.parent_name, "Hero")
        self.assertEqual(reloaded_hero.get_component(Transform).x, 142.0)
        self.assertEqual(reloaded_hero.get_component(Transform).y, 68.0)
        self.assertEqual(reloaded_companion.get_component(Transform).x, 145.0)
        self.assertEqual(reloaded_companion.get_component(Transform).y, 72.0)
        self.assertEqual(reloaded_button.parent_name, "Root")
        self.assertEqual(
            self._find_entity(persisted, "Hero")["component_metadata"]["Sprite"],
            {"origin": "matrix", "note": "edited"},
        )
        self.assertEqual(persisted["feature_metadata"]["input_profile"], {"source": "regression"})

    def test_edit_play_stop_runtime_mutation_does_not_contaminate_edit_scene(self) -> None:
        scene_path = self._scene_path("matrix_play_stop_scene.json")
        self._write_json(scene_path, self._build_dense_scene_payload("PlayStopMatrix"))

        api = self._make_api()
        api.load_level("levels/matrix_play_stop_scene.json")

        self.assertTrue(api.scene_manager.set_selected_entity("Hero"))
        self.assertTrue(self.api_result(api.edit_component("Hero", "Transform", "x", 30.0)))
        baseline_payload = api.scene_manager.current_scene.to_dict()

        api.play()
        runtime_world = api.game.world
        runtime_hero = runtime_world.get_entity_by_name("Hero")
        runtime_hero_transform = runtime_hero.get_component(Transform)
        runtime_hero_transform.x = 999.0
        runtime_world.feature_metadata["runtime_only"] = {"mutated": True}

        api.stop()

        self.assertEqual(api.scene_manager.current_scene.to_dict(), baseline_payload)
        self.assertTrue(api.scene_manager.is_dirty)
        self.assertEqual(api.game.world.selected_entity_name, "Hero")
        stopped_hero = api.game.world.get_entity_by_name("Hero")
        self.assertEqual(stopped_hero.get_component(Transform).x, 130.0)
        self.assertNotIn("runtime_only", api.scene_manager.current_scene.feature_metadata)

        self.assertTrue(self.api_result(api.save_scene(path=scene_path.as_posix())))
        self.assertEqual(self._read_json(scene_path), baseline_payload)

    def test_api_and_direct_authoring_routes_produce_equivalent_scene_payloads(self) -> None:
        api = self._make_api()
        api_payload = self._build_equivalent_scene_via_api(api)

        manager = self._make_scene_manager()
        manager_payload = self._build_equivalent_scene_via_manager(manager)

        self.assertEqual(api_payload, manager_payload)

        api_world = api.scene_manager.get_edit_world()
        manager_world = manager.get_edit_world()
        self.assertEqual(api_world.get_entity_by_name("Hero").parent_name, "Root")
        self.assertEqual(manager_world.get_entity_by_name("Hero").parent_name, "Root")
        self.assertEqual(api_world.get_entity_by_name("Hero").tag, "Player")
        self.assertEqual(manager_world.get_entity_by_name("Hero").tag, "Player")
        self.assertEqual(
            api_world.get_entity_by_name("Hero").get_component(Transform).x,
            manager_world.get_entity_by_name("Hero").get_component(Transform).x,
        )
        self.assertEqual(
            self._find_entity(api_payload, "Root")["components"]["SceneLink"],
            self._find_entity(manager_payload, "Root")["components"]["SceneLink"],
        )
        self.assertEqual(api_payload["feature_metadata"], manager_payload["feature_metadata"])

    def test_hierarchy_save_load_and_duplicate_preserve_parent_child_structure(self) -> None:
        scene_path = self._scene_path("matrix_duplicate_scene.json")
        manager = self._make_scene_manager()
        manager.load_scene(
            {
                "name": "DuplicateMatrix",
                "entities": [
                    {"name": "Root", "active": True, "tag": "Untagged", "layer": "Default", "components": {"Transform": self._transform(100.0, 50.0)}},
                    {"name": "Root/Child", "parent": "Root", "active": True, "tag": "Untagged", "layer": "Default", "components": {"Transform": self._transform(10.0, 5.0)}},
                    {"name": "Root/Child/Leaf", "parent": "Root/Child", "active": True, "tag": "Untagged", "layer": "Default", "components": {"Transform": self._transform(2.0, 1.0)}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        self.assertTrue(manager.duplicate_entity_subtree("Root", new_root_name="RootCopy"))
        self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))

        persisted = self._read_json(scene_path)
        copied_child = self._find_entity(persisted, "RootCopy/Child")
        copied_leaf = self._find_entity(persisted, "RootCopy/Child/Leaf")
        self.assertEqual(copied_child["parent"], "RootCopy")
        self.assertEqual(copied_leaf["parent"], "RootCopy/Child")

        reloaded = self._make_scene_manager()
        reloaded.load_scene_from_file(scene_path.as_posix())

        root_copy = reloaded.get_edit_world().get_entity_by_name("RootCopy")
        child_copy = reloaded.get_edit_world().get_entity_by_name("RootCopy/Child")
        leaf_copy = reloaded.get_edit_world().get_entity_by_name("RootCopy/Child/Leaf")
        self.assertEqual(child_copy.parent_name, "RootCopy")
        self.assertEqual(leaf_copy.parent_name, "RootCopy/Child")
        self.assertEqual(root_copy.get_component(Transform).x, 100.0)
        self.assertEqual(child_copy.get_component(Transform).x, 110.0)
        self.assertEqual(leaf_copy.get_component(Transform).x, 112.0)

    def test_prefab_instance_save_load_preserves_hierarchy_and_prefab_links(self) -> None:
        scene_path = self._scene_path("matrix_prefab_scene.json")
        prefab_path = self._prefab_path("enemy.prefab")
        self._write_json(scene_path, self._empty_scene("PrefabMatrix"))
        self._write_json(
            prefab_path,
            {
                "root_name": "Enemy",
                "entities": [
                    {
                        "name": "Enemy",
                        "active": True,
                        "tag": "Enemy",
                        "layer": "Actors",
                        "components": {"Transform": self._transform(0.0, 0.0)},
                    },
                    {
                        "name": "Weapon",
                        "parent": "",
                        "active": True,
                        "tag": "Weapon",
                        "layer": "Actors",
                        "components": {"Transform": self._transform(4.0, 0.0)},
                    },
                ],
            },
        )

        api = self._make_api()
        api.load_level("levels/matrix_prefab_scene.json")
        self.assertTrue(
            self.api_result(
                api.instantiate_prefab(
                    "prefabs/enemy.prefab",
                    name="EnemyA",
                    overrides={"": {"components": {"Transform": {"x": 40.0, "y": 10.0}}}},
                )
            )
        )
        self.assertTrue(self.api_result(api.save_scene(path=scene_path.as_posix())))

        persisted = self._read_json(scene_path)
        self.assertEqual(len(persisted["entities"]), 1)
        self.assertEqual(persisted["entities"][0]["name"], "EnemyA")
        self.assertIn("prefab_instance", persisted["entities"][0])

        reloaded_api = self._make_api()
        reloaded_api.load_level("levels/matrix_prefab_scene.json")

        enemy = reloaded_api.game.world.get_entity_by_name("EnemyA")
        weapon = reloaded_api.game.world.get_entity_by_name("EnemyA/Weapon")
        self.assertIsNotNone(enemy)
        self.assertIsNotNone(weapon)
        self.assertEqual(weapon.parent_name, "EnemyA")
        self.assertEqual(weapon.prefab_root_name, "EnemyA")
        self.assertEqual(enemy.get_component(Transform).x, 40.0)
        self.assertEqual(enemy.get_component(Transform).y, 10.0)
        self.assertEqual(weapon.get_component(Transform).x, 44.0)
        self.assertEqual(weapon.get_component(Transform).y, 10.0)

    def test_selection_persists_between_modes_and_isolated_scene_switches(self) -> None:
        scene_a_path = self._scene_path("selection_a.json")
        scene_b_path = self._scene_path("selection_b.json")
        self._write_json(
            scene_a_path,
            {
                "name": "SelectionA",
                "entities": [{"name": "HeroA", "active": True, "tag": "Untagged", "layer": "Default", "components": {"Transform": self._transform()}}],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_json(
            scene_b_path,
            {
                "name": "SelectionB",
                "entities": [{"name": "HeroB", "active": True, "tag": "Untagged", "layer": "Default", "components": {"Transform": self._transform()}}],
                "rules": [],
                "feature_metadata": {},
            },
        )

        api = self._make_api()
        api.load_level("levels/selection_a.json")
        self.assertTrue(api.scene_manager.set_selected_entity("HeroA"))

        api.play()
        self.assertEqual(api.game.world.selected_entity_name, "HeroA")
        api.stop()
        self.assertEqual(api.game.world.selected_entity_name, "HeroA")

        self.assertTrue(self.api_result(api.open_scene("levels/selection_b.json")))
        self.assertTrue(self.api_result(api.activate_scene("levels/selection_b.json")))
        self.assertTrue(api.scene_manager.set_selected_entity("HeroB"))
        self.assertEqual(api.game.world.selected_entity_name, "HeroB")

        self.assertTrue(self.api_result(api.activate_scene("levels/selection_a.json")))
        self.assertEqual(api.game.world.selected_entity_name, "HeroA")
        self.assertTrue(self.api_result(api.activate_scene("levels/selection_b.json")))
        self.assertEqual(api.game.world.selected_entity_name, "HeroB")

    def test_multi_scene_workspace_preserves_targeted_dirty_state_and_active_scene(self) -> None:
        scene_a_path = self._scene_path("workspace_a.json")
        scene_b_path = self._scene_path("workspace_b.json")
        self._write_json(scene_a_path, self._empty_scene("WorkspaceA"))
        self._write_json(scene_b_path, self._empty_scene("WorkspaceB"))

        manager = self._make_scene_manager()
        manager.load_scene_from_file(scene_a_path.as_posix())
        key_a = manager.active_scene_key
        manager.load_scene_from_file(scene_b_path.as_posix(), activate=False)
        key_b = next(scene["key"] for scene in manager.list_open_scenes() if scene["path"] == scene_b_path.resolve().as_posix())

        self.assertTrue(manager.create_entity("OnlyA"))
        self.assertTrue(manager.activate_scene(key_b))
        self.assertTrue(manager.create_entity("OnlyB"))
        self.assertEqual(manager.active_scene_key, key_b)
        self.assertTrue(manager.resolve_entry(key_a).dirty)
        self.assertTrue(manager.resolve_entry(key_b).dirty)

        self.assertTrue(manager.save_scene_to_file(scene_a_path.as_posix(), key=key_a))
        self.assertEqual(manager.active_scene_key, key_b)
        self.assertFalse(manager.resolve_entry(key_a).dirty)
        self.assertTrue(manager.resolve_entry(key_b).dirty)
        self.assertFalse(manager.close_scene(key_b, discard_changes=False))
        self.assertIn("OnlyA", [entity["name"] for entity in self._read_json(scene_a_path)["entities"]])
        self.assertEqual(manager.current_scene.name, "WorkspaceB")

    def test_transaction_undo_redo_preserve_structural_and_component_state(self) -> None:
        scene_path = self._scene_path("matrix_transaction_scene.json")
        self._write_json(scene_path, self._empty_scene("TransactionMatrix"))

        api = self._make_api()
        api.load_level("levels/matrix_transaction_scene.json")

        self.assertTrue(self.api_result(api.begin_transaction("matrix-transaction")))
        self.assertTrue(self.api_result(api.apply_change({"kind": "create_entity", "entity": "Parent"})))
        self.assertTrue(self.api_result(api.apply_change({"kind": "create_entity", "entity": "Child"})))
        self.assertTrue(
            self.api_result(
                api.apply_change({"kind": "set_entity_property", "entity": "Child", "field": "parent", "value": "Parent"})
            )
        )
        self.assertTrue(
            self.api_result(
                api.apply_change(
                    {
                        "kind": "add_component",
                        "entity": "Child",
                        "component": "Sprite",
                        "data": self._sprite("assets/tx_child.png", 24, 24),
                    }
                )
            )
        )
        self.assertTrue(
            self.api_result(
                api.apply_change(
                    {"kind": "edit_component", "entity": "Child", "component": "Transform", "field": "x", "value": 24.0}
                )
            )
        )
        committed = api.commit_transaction()
        self.assertTrue(self.api_result(committed))

        committed_payload = api.scene_manager.current_scene.to_dict()
        committed_child = api.game.world.get_entity_by_name("Child")
        self.assertEqual(committed_child.parent_name, "Parent")
        self.assertIn("Sprite", api.get_entity("Child")["components"])

        self.assertTrue(self.api_result(api.undo()))
        self.assertEqual(api.scene_manager.current_scene.to_dict()["entities"], [])

        self.assertTrue(self.api_result(api.redo()))
        self.assertEqual(api.scene_manager.current_scene.to_dict(), committed_payload)
        redone_child = api.game.world.get_entity_by_name("Child")
        self.assertEqual(redone_child.parent_name, "Parent")
        self.assertEqual(redone_child.get_component(Transform).local_x, 24.0)


if __name__ == "__main__":
    unittest.main()
