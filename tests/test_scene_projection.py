import copy
import inspect
import unittest
from unittest.mock import patch

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_projection import SceneProjectionService


def _transform(x: float = 1.0, y: float = 2.0) -> dict[str, object]:
    return {
        "enabled": True,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _scene_payload() -> dict[str, object]:
    return {
        "name": "ProjectionProbe",
        "entities": [
            {
                "name": "Actor",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {"Transform": _transform()},
            }
        ],
        "rules": [{"event": "start", "do": [{"action": "log_message", "message": "probe"}]}],
        "feature_metadata": {"probe": {"enabled": True}},
    }


class SceneProjectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projection = SceneProjectionService(create_default_registry())

    def test_validate_create_scene_and_world_without_manager(self) -> None:
        scene = self.projection.create_scene(_scene_payload(), source_path="projection.json")
        world = self.projection.create_world(scene)

        self.assertEqual(scene.to_dict()["schema_version"], 3)
        self.assertEqual(scene.source_path, "projection.json")
        actor = world.get_entity_by_name("Actor")
        self.assertIsNotNone(actor)
        assert actor is not None
        self.assertEqual(actor.get_component(Transform).x, 1.0)

    def test_validate_payload_rejects_invalid_scene(self) -> None:
        invalid = _scene_payload()
        invalid["entities"] = {}

        with self.assertRaisesRegex(ValueError, "Invalid scene payload"):
            self.projection.validate_payload(invalid)

    def test_validate_payload_does_not_mutate_input(self) -> None:
        source = _scene_payload()
        source_before = copy.deepcopy(source)

        validated = self.projection.validate_payload(source)

        self.assertEqual(source, source_before)
        self.assertIsNot(validated, source)
        self.assertIsNot(validated["entities"], source["entities"])

    def test_registry_canonicalization_does_not_mutate_input(self) -> None:
        source = {"x": 4.0}
        source_before = copy.deepcopy(source)

        canonical = self.projection.canonicalize_component_payload("Transform", source)

        self.assertEqual(source, source_before)
        self.assertEqual(canonical["x"], 4.0)
        self.assertEqual(canonical["y"], 0.0)
        self.assertTrue(canonical["enabled"])

    def test_build_canonical_payload_projects_world_back_to_scene_data(self) -> None:
        scene = self.projection.create_scene(_scene_payload())
        world = self.projection.create_world(scene)
        actor = world.get_entity_by_name("Actor")
        assert actor is not None
        actor.get_component(Transform).x = 9.0

        payload = self.projection.build_canonical_payload(scene, world.serialize())
        validated = self.projection.validate_payload(payload)

        self.assertEqual(validated["entities"][0]["components"]["Transform"]["x"], 9.0)
        self.assertEqual(validated["rules"], scene.rules_data)
        self.assertEqual(validated["feature_metadata"], scene.feature_metadata)

    def test_incremental_materialization_and_world_removal_are_technical_operations(self) -> None:
        scene = self.projection.create_scene(_scene_payload())
        world = self.projection.create_world(scene)

        added = self.projection.add_entity(
            scene,
            world,
            {"id": "added-id", "name": "Added", "components": {"Transform": _transform(3.0, 4.0)}},
        )

        self.assertIsNotNone(added)
        assert added is not None
        self.assertIsNotNone(scene.find_entity("Added"))
        self.assertIsNotNone(world.get_entity_by_name("Added"))

        self.projection.remove_entity_from_world(world, "Added", str(added["id"]))

        self.assertIsNotNone(scene.find_entity("Added"))
        self.assertIsNone(world.get_entity_by_name("Added"))

    def test_incremental_materialization_failure_rolls_back_scene_and_world(self) -> None:
        scene = self.projection.create_scene(_scene_payload())
        world = self.projection.create_world(scene)

        with patch.object(
            scene,
            "materialize_entity",
            side_effect=RuntimeError("materialization failed"),
        ) as materialize:
            with self.assertRaisesRegex(RuntimeError, "materialization failed"):
                self.projection.add_entity(
                    scene,
                    world,
                    {
                        "id": "rejected-id",
                        "name": "Rejected",
                        "components": {"Transform": _transform(3.0, 4.0)},
                    },
                )

        materialize.assert_called_once()
        self.assertIsNone(scene.find_entity("Rejected"))
        self.assertIsNone(world.get_entity_by_name("Rejected"))
        self.assertIsNotNone(scene.find_entity("Actor"))
        self.assertIsNotNone(world.get_entity_by_name("Actor"))

    def test_projection_has_no_workspace_state_or_lifecycle_decisions(self) -> None:
        source = inspect.getsource(SceneProjectionService)

        self.assertNotIn("SceneManager", source)
        self.assertNotIn("SceneWorkspaceEntry", source)
        self.assertNotIn(".dirty", source)
        self.assertNotIn("pending_edit_world", source)
        self.assertNotIn("selected_entity", source)
        for method_name in (
            "create_scene",
            "create_world",
            "build_canonical_payload",
            "add_entity",
            "remove_entity_from_world",
        ):
            self.assertNotIn("entry", inspect.signature(getattr(SceneProjectionService, method_name)).parameters)


if __name__ == "__main__":
    unittest.main()
