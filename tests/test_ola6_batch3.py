"""
tests/test_ola6_batch3.py - Tests for OLA6 batch 3: UITree + Line2D gradient.
"""

from __future__ import annotations

import unittest

from engine.components.line2d import Line2D
from engine.components.ui_tree import UITree, UITreeItem
from engine.levels.component_registry import create_default_registry


# =============================================================================
# 1. UITreeItem
# =============================================================================

class TestUITreeItem(unittest.TestCase):
    def test_default_values(self) -> None:
        item = UITreeItem()
        self.assertEqual(item.text, "")
        self.assertEqual(item.icon_path, "")
        self.assertFalse(item.expandable)
        self.assertFalse(item.expanded)
        self.assertFalse(item.selected)
        self.assertEqual(item.children, [])
        self.assertEqual(item.metadata, {})
        self.assertFalse(item.disabled)
        self.assertFalse(item.checked)
        self.assertFalse(item.checkable)

    def test_full_init(self) -> None:
        item = UITreeItem(text="Node1", icon_path="res://icon.png", expandable=True)
        self.assertEqual(item.text, "Node1")
        self.assertEqual(item.icon_path, "res://icon.png")
        self.assertTrue(item.expandable)

    def test_to_dict_from_dict_roundtrip(self) -> None:
        item = UITreeItem(text="Root", expandable=True)
        child = UITreeItem(text="Child", checkable=True, checked=True)
        item.children.append(child)
        item.metadata = {"id": 42, "highlight": True}

        data = item.to_dict()
        restored = UITreeItem.from_dict(data)

        self.assertEqual(restored.text, "Root")
        self.assertTrue(restored.expandable)
        self.assertEqual(len(restored.children), 1)
        self.assertEqual(restored.children[0].text, "Child")
        self.assertTrue(restored.children[0].checkable)
        self.assertTrue(restored.children[0].checked)
        self.assertEqual(restored.metadata["id"], 42)
        self.assertTrue(restored.metadata["highlight"])

    def test_nested_children_roundtrip(self) -> None:
        root = UITreeItem(text="A", expandable=True, expanded=True)
        b = UITreeItem(text="B", expandable=True)
        c = UITreeItem(text="C")
        b.children.append(c)
        root.children.append(b)

        data = root.to_dict()
        restored = UITreeItem.from_dict(data)

        self.assertEqual(len(restored.children), 1)
        self.assertEqual(restored.children[0].text, "B")
        self.assertEqual(len(restored.children[0].children), 1)
        self.assertEqual(restored.children[0].children[0].text, "C")

    def test_disabled_serialization(self) -> None:
        item = UITreeItem(text="Disabled Node", disabled=True)
        data = item.to_dict()
        self.assertTrue(data["disabled"])
        restored = UITreeItem.from_dict(data)
        self.assertTrue(restored.disabled)


# =============================================================================
# 2. UITree Component
# =============================================================================

class TestUITreeComponent(unittest.TestCase):
    def test_default_values(self) -> None:
        tree = UITree()
        self.assertTrue(tree.enabled)
        self.assertFalse(tree.allow_reselect)
        self.assertFalse(tree.allow_rmb_select)
        self.assertTrue(tree.hide_root)
        self.assertEqual(tree.select_mode, "single")
        self.assertEqual(tree.drop_mode_flags, 0)
        self.assertEqual(tree.columns, 1)
        self.assertEqual(tree.column_titles, [])
        self.assertTrue(tree.scroll_horizontal)
        self.assertTrue(tree.scroll_vertical)
        self.assertIsNone(tree.get_selected())

    def test_select_mode_validation(self) -> None:
        tree = UITree(select_mode="invalid")
        self.assertEqual(tree.select_mode, "single")

    def test_valid_select_modes(self) -> None:
        for mode in ("single", "multi", "row"):
            tree = UITree(select_mode=mode)
            self.assertEqual(tree.select_mode, mode)

    def test_create_item_on_root(self) -> None:
        tree = UITree()
        item = tree.create_item()
        self.assertIsInstance(item, UITreeItem)
        self.assertEqual(len(tree.root.children), 1)

    def test_create_item_on_parent(self) -> None:
        tree = UITree()
        parent = tree.create_item()
        child = tree.create_item(parent=parent)
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(parent.children[0], child)

    def test_create_item_at_index(self) -> None:
        tree = UITree()
        tree.create_item()  # index 0
        tree.create_item()  # index 1
        inserted = tree.create_item(index=1)
        self.assertEqual(tree.root.children[1], inserted)
        self.assertEqual(len(tree.root.children), 3)

    def test_clear(self) -> None:
        tree = UITree()
        tree.create_item()
        tree.create_item()
        self.assertEqual(len(tree.root.children), 2)
        tree.clear()
        self.assertEqual(len(tree.root.children), 0)
        self.assertIsNone(tree.get_selected())

    def test_to_dict_from_dict_roundtrip(self) -> None:
        tree = UITree(
            allow_reselect=True,
            hide_root=False,
            select_mode="multi",
            columns=3,
            column_titles=["Name", "Type", "Value"],
        )
        tree.create_item().text = "Item1"
        parent = tree.create_item()
        parent.text = "Folder"
        parent.expandable = True
        parent.expanded = True
        child = tree.create_item(parent=parent)
        child.text = "SubItem"

        data = tree.to_dict()
        restored = UITree.from_dict(data)

        self.assertTrue(restored.allow_reselect)
        self.assertFalse(restored.hide_root)
        self.assertEqual(restored.select_mode, "multi")
        self.assertEqual(restored.columns, 3)
        self.assertEqual(restored.column_titles, ["Name", "Type", "Value"])

        # Root children restored through root dict
        self.assertEqual(len(restored.root.children), 2)
        self.assertEqual(restored.root.children[0].text, "Item1")
        self.assertEqual(restored.root.children[1].text, "Folder")
        self.assertTrue(restored.root.children[1].expandable)
        self.assertTrue(restored.root.children[1].expanded)
        self.assertEqual(len(restored.root.children[1].children), 1)
        self.assertEqual(restored.root.children[1].children[0].text, "SubItem")

    def test_from_dict_preserves_enabled(self) -> None:
        tree = UITree.from_dict({"enabled": False, "columns": 2})
        self.assertFalse(tree.enabled)
        self.assertEqual(tree.columns, 2)


# =============================================================================
# 3. Line2D Gradient
# =============================================================================

class TestLine2DGradient(unittest.TestCase):
    def test_default_no_gradient(self) -> None:
        line = Line2D()
        self.assertFalse(line.use_gradient)
        self.assertEqual(line.gradient_colors, [])
        self.assertEqual(line.gradient_offsets, [])

    def test_gradient_init(self) -> None:
        colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        offsets = [0.0, 0.5, 1.0]
        line = Line2D(use_gradient=True, gradient_colors=colors, gradient_offsets=offsets)
        self.assertTrue(line.use_gradient)
        self.assertEqual(line.gradient_colors, colors)
        self.assertEqual(line.gradient_offsets, offsets)

    def test_to_dict_with_gradient(self) -> None:
        colors = [(255, 0, 0, 255), (0, 0, 255, 255)]
        offsets = [0.0, 1.0]
        line = Line2D(use_gradient=True, gradient_colors=colors, gradient_offsets=offsets)
        data = line.to_dict()
        self.assertTrue(data["use_gradient"])
        self.assertEqual(data["gradient_colors"], [[255, 0, 0, 255], [0, 0, 255, 255]])
        self.assertEqual(data["gradient_offsets"], [0.0, 1.0])

    def test_from_dict_with_gradient(self) -> None:
        data = {
            "points": [[0, 0], [100, 100]],
            "use_gradient": True,
            "gradient_colors": [[255, 0, 0, 255], [0, 255, 0, 255]],
            "gradient_offsets": [0.0, 1.0],
        }
        line = Line2D.from_dict(data)
        self.assertTrue(line.use_gradient)
        self.assertEqual(line.gradient_colors, [(255, 0, 0, 255), (0, 255, 0, 255)])
        self.assertEqual(line.gradient_offsets, [0.0, 1.0])

    def test_from_dict_gradient_partial_data(self) -> None:
        data = {
            "points": [[0, 0], [50, 50]],
            "use_gradient": True,
            "gradient_colors": [[255, 0, 0]],
        }
        line = Line2D.from_dict(data)
        self.assertTrue(line.use_gradient)
        self.assertEqual(line.gradient_colors, [(255, 0, 0, 255)])
        self.assertEqual(line.gradient_offsets, [])

    def test_roundtrip_with_gradient(self) -> None:
        colors = [(255, 128, 0, 255), (0, 128, 255, 200)]
        offsets = [0.0, 1.0]
        line = Line2D(
            points=[[0, 0], [200, 100], [300, 50]],
            width=4.0,
            use_gradient=True,
            gradient_colors=colors,
            gradient_offsets=offsets,
            joint_mode="round",
            closed=False,
        )
        data = line.to_dict()
        restored = Line2D.from_dict(data)

        self.assertEqual(len(restored.points), 3)
        self.assertEqual(restored.width, 4.0)
        self.assertTrue(restored.use_gradient)
        self.assertEqual(restored.gradient_colors, colors)
        self.assertEqual(restored.gradient_offsets, offsets)
        self.assertEqual(restored.joint_mode, "round")
        self.assertFalse(restored.closed)

    def test_gradient_no_effect_when_disabled(self) -> None:
        """When use_gradient=False, default color is used regardless of gradient data."""
        line = Line2D(
            color=(100, 200, 50, 255),
            use_gradient=False,
            gradient_colors=[(255, 0, 0, 255), (0, 0, 255, 255)],
            gradient_offsets=[0.0, 1.0],
        )
        self.assertFalse(line.use_gradient)
        self.assertEqual(line.color, (100, 200, 50, 255))
        # Gradient data still stored but not used in rendering
        self.assertEqual(len(line.gradient_colors), 2)


# =============================================================================
# 4. Component Registry
# =============================================================================

class TestRegistryBatch3(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_registry_has_ui_tree(self) -> None:
        self.assertIn("UITree", self.registry.list_registered())

    def test_create_ui_tree_from_registry(self) -> None:
        instance = self.registry.create("UITree", {
            "columns": 2,
            "column_titles": ["Name", "Value"],
            "select_mode": "multi",
        })
        self.assertIsInstance(instance, UITree)
        self.assertEqual(instance.columns, 2)
        self.assertEqual(instance.column_titles, ["Name", "Value"])
        self.assertEqual(instance.select_mode, "multi")

    def test_ui_tree_descriptor_has_payload(self) -> None:
        descriptor = self.registry.get_descriptor("UITree")
        self.assertIsNotNone(descriptor)
        if descriptor is not None:
            payload = descriptor.default_payload
            self.assertIsInstance(payload, dict)
            self.assertIn("columns", payload)
            self.assertIn("hide_root", payload)

    def test_registry_has_line2d_unchanged(self) -> None:
        self.assertIn("Line2D", self.registry.list_registered())


if __name__ == "__main__":
    unittest.main()
