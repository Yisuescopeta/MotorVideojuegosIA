"""
tests/test_ui_ninepatch.py - Tests for UINinePatchRect and UITextureButton components.
"""

from __future__ import annotations

import json
import unittest

from engine.components.ui_ninepatch import UINinePatchRect
from engine.components.ui_texture_button import UITextureButton
from engine.levels.component_registry import create_default_registry


class TestUINinePatchRect(unittest.TestCase):
    def test_create_ninepatch(self) -> None:
        np = UINinePatchRect()
        self.assertTrue(np.enabled)
        self.assertEqual(np.texture_path, "")
        self.assertEqual(np.patch_margin_left, 8)
        self.assertEqual(np.patch_margin_right, 8)
        self.assertEqual(np.patch_margin_top, 8)
        self.assertEqual(np.patch_margin_bottom, 8)
        self.assertTrue(np.draw_center)
        self.assertEqual(np.modulate, (255, 255, 255, 255))

    def test_ninepatch_serialization(self) -> None:
        np = UINinePatchRect(
            enabled=True,
            texture_path="res://ui/panel_9slice.png",
            patch_margin_left=12,
            patch_margin_right=12,
            patch_margin_top=8,
            patch_margin_bottom=8,
            draw_center=False,
            modulate=(200, 150, 100, 255),
        )
        data = np.to_dict()
        restored = UINinePatchRect.from_dict(data)
        self.assertEqual(restored.enabled, np.enabled)
        self.assertEqual(restored.texture_path, np.texture_path)
        self.assertEqual(restored.patch_margin_left, np.patch_margin_left)
        self.assertEqual(restored.patch_margin_right, np.patch_margin_right)
        self.assertEqual(restored.patch_margin_top, np.patch_margin_top)
        self.assertEqual(restored.patch_margin_bottom, np.patch_margin_bottom)
        self.assertEqual(restored.draw_center, np.draw_center)
        self.assertEqual(restored.modulate, np.modulate)

    def test_ninepatch_margins(self) -> None:
        np = UINinePatchRect(
            patch_margin_left=16,
            patch_margin_right=24,
            patch_margin_top=32,
            patch_margin_bottom=48,
        )
        self.assertEqual(np.patch_margin_left, 16)
        self.assertEqual(np.patch_margin_right, 24)
        self.assertEqual(np.patch_margin_top, 32)
        self.assertEqual(np.patch_margin_bottom, 48)

    def test_ninepatch_serialization_json(self) -> None:
        np = UINinePatchRect(
            texture_path="res://ui/frame.png",
            patch_margin_left=10,
            patch_margin_right=10,
            patch_margin_top=10,
            patch_margin_bottom=10,
            draw_center=True,
            modulate=(128, 128, 128, 200),
        )
        payload = np.to_dict()
        raw = json.dumps(payload)
        loaded = json.loads(raw)
        restored = UINinePatchRect.from_dict(loaded)
        self.assertEqual(restored.texture_path, np.texture_path)
        self.assertEqual(restored.modulate, np.modulate)

    def test_ninepatch_from_dict_defaults(self) -> None:
        np = UINinePatchRect.from_dict({})
        self.assertTrue(np.enabled)
        self.assertEqual(np.texture_path, "")
        self.assertEqual(np.patch_margin_left, 8)
        self.assertTrue(np.draw_center)
        self.assertEqual(np.modulate, (255, 255, 255, 255))


class TestUITextureButton(unittest.TestCase):
    def test_create_texture_button(self) -> None:
        btn = UITextureButton()
        self.assertTrue(btn.enabled)
        self.assertTrue(btn.interactable)
        self.assertEqual(btn.texture_normal_path, "")
        self.assertEqual(btn.texture_hover_path, "")
        self.assertEqual(btn.texture_pressed_path, "")
        self.assertEqual(btn.texture_disabled_path, "")
        self.assertFalse(btn.expand_icon)
        self.assertEqual(btn.stretch_mode, "scale")
        self.assertEqual(btn.on_click, {})

    def test_texture_button_serialization(self) -> None:
        btn = UITextureButton(
            enabled=True,
            interactable=True,
            texture_normal_path="res://ui/btn_normal.png",
            texture_hover_path="res://ui/btn_hover.png",
            texture_pressed_path="res://ui/btn_pressed.png",
            texture_disabled_path="res://ui/btn_disabled.png",
            expand_icon=True,
            stretch_mode="tile",
            on_click={"action": "start_game"},
        )
        data = btn.to_dict()
        restored = UITextureButton.from_dict(data)
        self.assertEqual(restored.enabled, btn.enabled)
        self.assertEqual(restored.interactable, btn.interactable)
        self.assertEqual(restored.texture_normal_path, btn.texture_normal_path)
        self.assertEqual(restored.texture_hover_path, btn.texture_hover_path)
        self.assertEqual(restored.texture_pressed_path, btn.texture_pressed_path)
        self.assertEqual(restored.texture_disabled_path, btn.texture_disabled_path)
        self.assertEqual(restored.expand_icon, btn.expand_icon)
        self.assertEqual(restored.stretch_mode, btn.stretch_mode)
        self.assertEqual(restored.on_click, btn.on_click)

    def test_texture_button_states(self) -> None:
        btn = UITextureButton(
            texture_normal_path="res://ui/n.png",
            texture_hover_path="res://ui/h.png",
            texture_pressed_path="res://ui/p.png",
            texture_disabled_path="res://ui/d.png",
            stretch_mode="keep",
        )
        # Initial state
        self.assertEqual(btn.texture_normal_path, "res://ui/n.png")
        self.assertEqual(btn.texture_hover_path, "res://ui/h.png")
        self.assertEqual(btn.texture_pressed_path, "res://ui/p.png")
        self.assertEqual(btn.texture_disabled_path, "res://ui/d.png")
        self.assertEqual(btn.stretch_mode, "keep")
        # Runtime state not serialized
        data = btn.to_dict()
        self.assertNotIn("_is_hovered", data)
        self.assertNotIn("_is_pressed", data)

    def test_texture_button_serialization_json(self) -> None:
        btn = UITextureButton(
            texture_normal_path="res://ui/play.png",
            stretch_mode="keep_centered",
            on_click={"action": "resume"},
        )
        payload = btn.to_dict()
        raw = json.dumps(payload)
        loaded = json.loads(raw)
        restored = UITextureButton.from_dict(loaded)
        self.assertEqual(restored.texture_normal_path, btn.texture_normal_path)
        self.assertEqual(restored.stretch_mode, btn.stretch_mode)
        self.assertEqual(restored.on_click, btn.on_click)

    def test_texture_button_from_dict_defaults(self) -> None:
        btn = UITextureButton.from_dict({})
        self.assertTrue(btn.enabled)
        self.assertTrue(btn.interactable)
        self.assertEqual(btn.texture_normal_path, "")
        self.assertEqual(btn.stretch_mode, "scale")
        self.assertEqual(btn.on_click, {})


class TestComponentRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_registry_ninepatch(self) -> None:
        cls = self.registry.get("UINinePatchRect")
        self.assertIsNotNone(cls)
        self.assertIs(cls, UINinePatchRect)
        np = self.registry.create(
            "UINinePatchRect",
            {"texture_path": "res://ui/border.png", "patch_margin_left": 16},
        )
        self.assertIsInstance(np, UINinePatchRect)
        self.assertEqual(np.texture_path, "res://ui/border.png")
        self.assertEqual(np.patch_margin_left, 16)

    def test_registry_ninepatch_defaults(self) -> None:
        np = self.registry.create("UINinePatchRect", {})
        self.assertIsInstance(np, UINinePatchRect)
        self.assertTrue(np.enabled)
        self.assertEqual(np.patch_margin_left, 8)

    def test_registry_texture_button(self) -> None:
        cls = self.registry.get("UITextureButton")
        self.assertIsNotNone(cls)
        self.assertIs(cls, UITextureButton)
        btn = self.registry.create(
            "UITextureButton",
            {"texture_normal_path": "res://ui/btn.png", "stretch_mode": "tile"},
        )
        self.assertIsInstance(btn, UITextureButton)
        self.assertEqual(btn.texture_normal_path, "res://ui/btn.png")
        self.assertEqual(btn.stretch_mode, "tile")

    def test_registry_texture_button_defaults(self) -> None:
        btn = self.registry.create("UITextureButton", {})
        self.assertIsInstance(btn, UITextureButton)
        self.assertTrue(btn.enabled)
        self.assertTrue(btn.interactable)
        self.assertEqual(btn.stretch_mode, "scale")

    def test_registry_metadata_ninepatch(self) -> None:
        descriptor = self.registry.get_descriptor("UINinePatchRect")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.name, "UINinePatchRect")
        self.assertEqual(descriptor.origin, "native")
        self.assertIn("ui", descriptor.editor_tags)
        self.assertIn("9patch", descriptor.editor_tags)

    def test_registry_metadata_texture_button(self) -> None:
        descriptor = self.registry.get_descriptor("UITextureButton")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.name, "UITextureButton")
        self.assertIn("button", descriptor.editor_tags)
        self.assertIn("texture", descriptor.editor_tags)


if __name__ == "__main__":
    unittest.main()
