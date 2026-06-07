import unittest
from unittest.mock import patch

from engine.components.camera2d import Camera2D
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.transform import Transform
from engine.ecs.component import Component
from engine.ecs.world import World, WorldCloneError


class LegacyCloneComponent(Component):
    def __init__(self) -> None:
        self.enabled = False
        self.values = [{"value": 1}]

    def clone(self) -> "Component":
        raise RuntimeError("legacy clone")


class UncloneableComponent(Component):
    def clone(self) -> "Component":
        raise RuntimeError("explicit clone failed")

    def __deepcopy__(self, memo: dict[int, object]) -> "Component":
        raise RuntimeError("deepcopy failed")


class ECSCloneTests(unittest.TestCase):
    def _build_world(self) -> World:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay"]}}
        world.selected_entity_name = "Child"

        parent = world.create_entity("Parent")
        parent.serialized_id = "parent-id"
        parent.groups = ("Gameplay",)
        parent_transform = Transform(x=10.0, y=20.0)
        parent.add_component(parent_transform)

        child = world.create_entity("Child")
        child.serialized_id = "child-id"
        child.active = False
        child.tag = "Player"
        child.layer = "Actors"
        child.groups = ("Gameplay", "Players")
        child.parent_name = "Parent"
        child.prefab_instance = {
            "prefab_path": "prefabs/player.prefab",
            "root_name": "Child",
            "overrides": {"components": {"Transform": {"x": 5.0}}},
        }
        child.prefab_source_path = "Child"
        child.prefab_root_name = "Child"
        child_transform = Transform(x=5.0, y=6.0)
        child_transform.enabled = False
        child_transform.parent = parent_transform
        parent_transform.children.append(child_transform)
        child.add_component(
            child_transform,
            metadata={"origin": "prefab", "details": {"editable": True}},
        )
        child.add_component(
            Camera2D(profile_overrides={"combat": {"zoom": 1.5}}),
        )
        child.add_component(
            ScriptBehaviour(public_data={"inventory": [{"id": "key"}]}),
        )
        return world

    def test_world_clone_preserves_state_without_aliasing_mutable_data(self) -> None:
        original = self._build_world()

        cloned = original.clone()

        original_child = original.get_entity_by_name("Child")
        cloned_child = cloned.get_entity_by_name("Child")
        self.assertIsNot(original_child, cloned_child)
        self.assertEqual(cloned_child.serialized_id, "child-id")
        self.assertFalse(cloned_child.active)
        self.assertEqual(cloned_child.tag, "Player")
        self.assertEqual(cloned_child.layer, "Actors")
        self.assertEqual(cloned_child.groups, ("Gameplay", "Players"))
        self.assertEqual(cloned.selected_entity_name, "Child")

        cloned.feature_metadata["render_2d"]["sorting_layers"].append("UI")
        cloned_child.prefab_instance["overrides"]["components"]["Transform"]["x"] = 99.0
        cloned_metadata = cloned_child.get_component_metadata(Transform)
        cloned_metadata["details"]["editable"] = False
        cloned_child.set_component_metadata(Transform, cloned_metadata)
        cloned_child.get_component(Camera2D).profile_overrides["combat"]["zoom"] = 3.0
        cloned_child.get_component(ScriptBehaviour).public_data["inventory"][0]["id"] = "coin"

        self.assertEqual(
            original.feature_metadata["render_2d"]["sorting_layers"],
            ["Default", "Gameplay"],
        )
        self.assertEqual(
            original_child.prefab_instance["overrides"]["components"]["Transform"]["x"],
            5.0,
        )
        self.assertTrue(original_child.get_component_metadata(Transform)["details"]["editable"])
        self.assertEqual(original_child.get_component(Camera2D).profile_overrides["combat"]["zoom"], 1.5)
        self.assertEqual(original_child.get_component(ScriptBehaviour).public_data["inventory"][0]["id"], "key")

    def test_world_clone_rebuilds_transform_hierarchy_and_preserves_enabled(self) -> None:
        original = self._build_world()

        cloned = original.clone()

        original_parent = original.get_entity_by_name("Parent").get_component(Transform)
        original_child = original.get_entity_by_name("Child").get_component(Transform)
        cloned_parent = cloned.get_entity_by_name("Parent").get_component(Transform)
        cloned_child = cloned.get_entity_by_name("Child").get_component(Transform)
        self.assertIsNot(cloned_parent, original_parent)
        self.assertIsNot(cloned_child, original_child)
        self.assertIs(cloned_child.parent, cloned_parent)
        self.assertIn(cloned_child, cloned_parent.children)
        self.assertFalse(cloned_child.enabled)

        cloned_parent.local_x = 100.0
        cloned_child.local_x = 50.0

        self.assertEqual(original_parent.local_x, 10.0)
        self.assertEqual(original_child.local_x, 5.0)

    def test_normal_clone_path_does_not_call_deepcopy(self) -> None:
        world = self._build_world()

        with (
            patch("engine.ecs.world.copy.deepcopy", side_effect=AssertionError("world deepcopy used")),
            patch(
                "engine.serialization.json_value.copy.deepcopy",
                side_effect=AssertionError("json deepcopy used"),
            ),
        ):
            cloned = world.clone()

        self.assertIsNotNone(cloned.get_entity_by_name("Child"))

    def test_component_metadata_is_defensive_on_input_and_output(self) -> None:
        world = World()
        entity = world.create_entity("Metadata")
        source = {"origin": "authoring", "nested": {"editable": True}}
        entity.add_component(Transform(), metadata=source)

        source["nested"]["editable"] = False
        returned = entity.get_component_metadata(Transform)
        returned["nested"]["editable"] = False

        self.assertTrue(entity.get_component_metadata(Transform)["nested"]["editable"])

    def test_legacy_component_uses_deepcopy_fallback(self) -> None:
        world = World()
        entity = world.create_entity("Legacy")
        entity.add_component(LegacyCloneComponent())

        cloned = world.clone()
        cloned_component = cloned.get_entity_by_name("Legacy").get_component(LegacyCloneComponent)
        cloned_component.values[0]["value"] = 2

        self.assertEqual(entity.get_component(LegacyCloneComponent).values[0]["value"], 1)
        self.assertFalse(cloned_component.enabled)

    def test_clone_reports_both_failures_with_entity_context(self) -> None:
        world = World()
        world.create_entity("Broken").add_component(UncloneableComponent())

        with self.assertRaisesRegex(WorldCloneError, "Broken.UncloneableComponent.*clone\\(\\).*deepcopy"):
            world.clone()


if __name__ == "__main__":
    unittest.main()
