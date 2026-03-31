"""Tests for parent-child hierarchy operations.

Covers: reparenting, unparenting, delete-orphan, cycle prevention,
serialization round-trip, and hierarchical movement.
"""

import copy
import unittest

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


def _make_entity(name: str, x: float = 0.0, y: float = 0.0, parent: str | None = None) -> dict:
    data: dict = {
        "name": name,
        "active": True,
        "tag": "Untagged",
        "layer": "Default",
        "components": {
            "Transform": {
                "enabled": True,
                "x": x,
                "y": y,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            }
        },
    }
    if parent is not None:
        data["parent"] = parent
    return data


class TestReparentPreservesWorldPosition(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = SceneManager(create_default_registry())
        self.sm.load_scene({
            "name": "Test",
            "entities": [
                _make_entity("A", x=100.0, y=50.0),
                _make_entity("B", x=200.0, y=150.0),
            ],
            "rules": [],
            "feature_metadata": {},
        })

    def test_reparent_preserves_world_position(self) -> None:
        """Reparenting B under A should keep B at (200, 150) world."""
        result = self.sm.set_entity_parent("B", "A")
        self.assertTrue(result)

        world = self.sm.get_edit_world()
        b = world.get_entity_by_name("B")
        self.assertIsNotNone(b)
        t = b.get_component(Transform)
        self.assertIsNotNone(t)
        # World position should be preserved
        self.assertAlmostEqual(t.x, 200.0, places=3)
        self.assertAlmostEqual(t.y, 150.0, places=3)
        # Local should be offset from parent
        self.assertAlmostEqual(t.local_x, 100.0, places=3)
        self.assertAlmostEqual(t.local_y, 100.0, places=3)
        # Parent link should be set
        self.assertEqual(b.parent_name, "A")


class TestUnparentPreservesWorldPosition(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = SceneManager(create_default_registry())
        self.sm.load_scene({
            "name": "Test",
            "entities": [
                _make_entity("Parent", x=100.0, y=50.0),
                _make_entity("Child", x=30.0, y=20.0, parent="Parent"),
            ],
            "rules": [],
            "feature_metadata": {},
        })

    def test_unparent_preserves_world_position(self) -> None:
        """Unparenting Child should keep it at world (130, 70)."""
        world = self.sm.get_edit_world()
        child = world.get_entity_by_name("Child")
        t = child.get_component(Transform)
        # Before unparent: world pos = 100+30, 50+20
        self.assertAlmostEqual(t.x, 130.0, places=3)
        self.assertAlmostEqual(t.y, 70.0, places=3)

        result = self.sm.set_entity_parent("Child", None)
        self.assertTrue(result)

        world = self.sm.get_edit_world()
        child = world.get_entity_by_name("Child")
        t = child.get_component(Transform)
        self.assertIsNone(child.parent_name)
        self.assertAlmostEqual(t.x, 130.0, places=3)
        self.assertAlmostEqual(t.y, 70.0, places=3)
        self.assertAlmostEqual(t.local_x, 130.0, places=3)
        self.assertAlmostEqual(t.local_y, 70.0, places=3)


class TestDeleteParentOrphansChildren(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = SceneManager(create_default_registry())
        self.sm.load_scene({
            "name": "Test",
            "entities": [
                _make_entity("Parent", x=100.0, y=50.0),
                _make_entity("Child1", x=10.0, y=20.0, parent="Parent"),
                _make_entity("Child2", x=30.0, y=40.0, parent="Parent"),
            ],
            "rules": [],
            "feature_metadata": {},
        })

    def test_delete_parent_orphans_children(self) -> None:
        """Deleting Parent should keep Child1 and Child2 as roots at their world positions."""
        result = self.sm.remove_entity("Parent")
        self.assertTrue(result)

        world = self.sm.get_edit_world()
        self.assertIsNone(world.get_entity_by_name("Parent"))

        c1 = world.get_entity_by_name("Child1")
        self.assertIsNotNone(c1)
        self.assertIsNone(c1.parent_name)
        t1 = c1.get_component(Transform)
        # World pos was 100+10=110, 50+20=70
        self.assertAlmostEqual(t1.x, 110.0, places=3)
        self.assertAlmostEqual(t1.y, 70.0, places=3)

        c2 = world.get_entity_by_name("Child2")
        self.assertIsNotNone(c2)
        self.assertIsNone(c2.parent_name)
        t2 = c2.get_component(Transform)
        # World pos was 100+30=130, 50+40=90
        self.assertAlmostEqual(t2.x, 130.0, places=3)
        self.assertAlmostEqual(t2.y, 90.0, places=3)

    def test_delete_middle_preserves_grandchildren(self) -> None:
        """Delete middle entity in a 3-level hierarchy."""
        self.sm.load_scene({
            "name": "Test3",
            "entities": [
                _make_entity("Grand", x=10.0, y=10.0),
                _make_entity("Mid", x=20.0, y=20.0, parent="Grand"),
                _make_entity("Leaf", x=5.0, y=5.0, parent="Mid"),
            ],
            "rules": [],
            "feature_metadata": {},
        })

        # Leaf world pos = 10+20+5=35, 10+20+5=35
        result = self.sm.remove_entity("Mid")
        self.assertTrue(result)

        world = self.sm.get_edit_world()
        self.assertIsNone(world.get_entity_by_name("Mid"))

        leaf = world.get_entity_by_name("Leaf")
        self.assertIsNotNone(leaf)
        # Leaf should be reparented to Grand (Mid's parent)
        self.assertEqual(leaf.parent_name, "Grand")
        t = leaf.get_component(Transform)
        # World pos should still be 35, 35
        self.assertAlmostEqual(t.x, 35.0, places=3)
        self.assertAlmostEqual(t.y, 35.0, places=3)
        # Local should be relative to Grand: 35-10=25
        self.assertAlmostEqual(t.local_x, 25.0, places=3)
        self.assertAlmostEqual(t.local_y, 25.0, places=3)


class TestCyclePrevention(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = SceneManager(create_default_registry())
        self.sm.load_scene({
            "name": "Test",
            "entities": [
                _make_entity("A", x=0.0, y=0.0),
                _make_entity("B", x=10.0, y=10.0, parent="A"),
            ],
            "rules": [],
            "feature_metadata": {},
        })

    def test_cycle_rejected(self) -> None:
        """A is parent of B. Trying to make B parent of A should fail."""
        result = self.sm.set_entity_parent("A", "B")
        self.assertFalse(result)
        # Verify hierarchy unchanged
        world = self.sm.get_edit_world()
        a = world.get_entity_by_name("A")
        self.assertIsNone(a.parent_name)

    def test_self_parent_rejected(self) -> None:
        """An entity cannot be its own parent."""
        result = self.sm.set_entity_parent("A", "A")
        self.assertFalse(result)


class TestSerializeDeserializeHierarchy(unittest.TestCase):
    def test_round_trip(self) -> None:
        """Save and load a scene with hierarchy; verify structure intact."""
        sm = SceneManager(create_default_registry())
        sm.load_scene({
            "name": "HierTest",
            "entities": [
                _make_entity("Root", x=50.0, y=50.0),
                _make_entity("ChildA", x=10.0, y=10.0, parent="Root"),
                _make_entity("ChildB", x=20.0, y=20.0, parent="Root"),
                _make_entity("GrandChild", x=5.0, y=5.0, parent="ChildA"),
            ],
            "rules": [],
            "feature_metadata": {},
        })

        # Serialize
        world = sm.get_edit_world()
        data = world.serialize()

        # Reload from serialized data
        sm2 = SceneManager(create_default_registry())
        sm2.load_scene({"name": "HierTest", **data})

        world2 = sm2.get_edit_world()

        root = world2.get_entity_by_name("Root")
        self.assertIsNotNone(root)
        self.assertIsNone(root.parent_name)

        child_a = world2.get_entity_by_name("ChildA")
        self.assertIsNotNone(child_a)
        self.assertEqual(child_a.parent_name, "Root")

        child_b = world2.get_entity_by_name("ChildB")
        self.assertIsNotNone(child_b)
        self.assertEqual(child_b.parent_name, "Root")

        gc = world2.get_entity_by_name("GrandChild")
        self.assertIsNotNone(gc)
        self.assertEqual(gc.parent_name, "ChildA")

        # Verify world positions are correct
        t_gc = gc.get_component(Transform)
        # GrandChild world = 50+10+5=65
        self.assertAlmostEqual(t_gc.x, 65.0, places=3)
        self.assertAlmostEqual(t_gc.y, 65.0, places=3)


class TestMoveParentMovesChildren(unittest.TestCase):
    def test_move_parent_propagates(self) -> None:
        """Moving a parent should change children's world positions."""
        sm = SceneManager(create_default_registry())
        sm.load_scene({
            "name": "Move",
            "entities": [
                _make_entity("P", x=0.0, y=0.0),
                _make_entity("C", x=10.0, y=10.0, parent="P"),
            ],
            "rules": [],
            "feature_metadata": {},
        })

        world = sm.get_edit_world()
        p = world.get_entity_by_name("P")
        c = world.get_entity_by_name("C")
        pt = p.get_component(Transform)
        ct = c.get_component(Transform)

        # Initial world position of child
        self.assertAlmostEqual(ct.x, 10.0, places=3)
        self.assertAlmostEqual(ct.y, 10.0, places=3)

        # Move parent via global setter (like gizmo does)
        pt.x = 50.0
        pt.y = 30.0

        # Child's world position should now be parent + local
        self.assertAlmostEqual(ct.x, 60.0, places=3)
        self.assertAlmostEqual(ct.y, 40.0, places=3)
        # Child's local should be unchanged
        self.assertAlmostEqual(ct.local_x, 10.0, places=3)
        self.assertAlmostEqual(ct.local_y, 10.0, places=3)


class TestHierarchyAuthoringScenarios(unittest.TestCase):
    def test_create_child_entity_uses_local_transform_payload(self) -> None:
        sm = SceneManager(create_default_registry())
        sm.load_scene(
            {
                "name": "ChildLocal",
                "entities": [_make_entity("Parent", x=100.0, y=200.0)],
                "rules": [],
                "feature_metadata": {},
            }
        )

        created = sm.create_child_entity(
            "Parent",
            "Child",
            {
                "Transform": {
                    "enabled": True,
                    "x": 12.0,
                    "y": 8.0,
                    "rotation": 0.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                }
            },
        )

        self.assertTrue(created)
        child_scene = sm.current_scene.find_entity("Child")
        self.assertEqual(child_scene["parent"], "Parent")
        self.assertEqual(child_scene["components"]["Transform"]["x"], 12.0)
        self.assertEqual(child_scene["components"]["Transform"]["y"], 8.0)

        child = sm.get_edit_world().get_entity_by_name("Child")
        child_transform = child.get_component(Transform)
        self.assertEqual(child_transform.local_x, 12.0)
        self.assertEqual(child_transform.local_y, 8.0)
        self.assertEqual(child_transform.x, 112.0)
        self.assertEqual(child_transform.y, 208.0)

    def test_duplicate_subtree_remaps_prefab_root_name(self) -> None:
        sm = SceneManager(create_default_registry())
        sm.load_scene(
            {
                "name": "DuplicatePrefabRoot",
                "entities": [
                    {
                        **_make_entity("Rig", x=0.0, y=0.0),
                        "prefab_root_name": "Rig",
                    },
                    {
                        **_make_entity("Rig/Tool", x=4.0, y=2.0, parent="Rig"),
                        "prefab_root_name": "Rig",
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        duplicated = sm.duplicate_entity_subtree("Rig", new_root_name="RigCopy")

        self.assertTrue(duplicated)
        duplicated_root = sm.current_scene.find_entity("RigCopy")
        duplicated_child = sm.current_scene.find_entity("RigCopy/Tool")
        self.assertEqual(duplicated_root["prefab_root_name"], "RigCopy")
        self.assertEqual(duplicated_child["prefab_root_name"], "RigCopy")
        self.assertEqual(duplicated_child["parent"], "RigCopy")


class TestTransformHierarchyCore(unittest.TestCase):
    """Test the Transform component hierarchy directly."""

    def test_set_parent_preserves_global(self) -> None:
        parent = Transform(x=100.0, y=50.0)
        child = Transform(x=200.0, y=150.0)
        # Reparent: child should keep world pos (200, 150)
        child.set_parent(parent)
        self.assertAlmostEqual(child.x, 200.0, places=3)
        self.assertAlmostEqual(child.y, 150.0, places=3)
        self.assertAlmostEqual(child.local_x, 100.0, places=3)
        self.assertAlmostEqual(child.local_y, 100.0, places=3)

    def test_unparent_preserves_global(self) -> None:
        parent = Transform(x=100.0, y=50.0)
        child = Transform(x=30.0, y=20.0)
        child.parent = parent
        parent.children.append(child)
        # World pos is 130, 70
        self.assertAlmostEqual(child.x, 130.0, places=3)
        child.set_parent(None)
        # After unparent, world pos preserved
        self.assertAlmostEqual(child.x, 130.0, places=3)
        self.assertAlmostEqual(child.y, 70.0, places=3)

    def test_depth(self) -> None:
        a = Transform()
        b = Transform()
        c = Transform()
        b.set_parent(a)
        c.set_parent(b)
        self.assertEqual(a.depth, 0)
        self.assertEqual(b.depth, 1)
        self.assertEqual(c.depth, 2)

    def test_scale_multiplicative(self) -> None:
        parent = Transform(scale_x=2.0, scale_y=3.0)
        child = Transform(scale_x=0.5, scale_y=0.5)
        child.parent = parent
        parent.children.append(child)
        self.assertAlmostEqual(child.scale_x, 1.0, places=3)
        self.assertAlmostEqual(child.scale_y, 1.5, places=3)


if __name__ == "__main__":
    unittest.main()
