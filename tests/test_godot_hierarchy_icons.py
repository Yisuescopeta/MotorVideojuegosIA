from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.editor.ui import icon_provider
from engine.editor.ui.icons import ICON_ENTITY, draw_icon, icon_exists


class GodotHierarchyIconTests(unittest.TestCase):
    def setUp(self) -> None:
        icon_provider.reset_cache()
        self.root = Path(__file__).resolve().parents[1]

    def tearDown(self) -> None:
        icon_provider.reset_cache()

    def test_manifest_tracks_light_substitution(self) -> None:
        manifest_path = self.root / "engine/editor/resources/icons/godot/godot_hierarchy_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_commit"], "72cc0fc9a75bf041e84b9d37e7e31e17cb114a9e")
        self.assertEqual(manifest["icons"]["light"]["source"], "DirectionalLight2D.svg")
        self.assertEqual(manifest["icons"]["light"]["substitution_from"], "Light2D.svg")

    def test_icon_exists_recognizes_godot_hierarchy_icons(self) -> None:
        self.assertTrue(icon_exists("entity"))
        self.assertTrue(icon_exists("sprite"))
        self.assertTrue(icon_exists("camera"))
        self.assertTrue(icon_exists("tilemap"))

    def test_draw_icon_prefers_godot_pack_for_hierarchy_icons(self) -> None:
        with patch("engine.editor.ui.icons._draw_icon_from_pack", return_value=True) as draw_from_pack, patch(
            "engine.editor.ui.icons._draw_lucide_icon", return_value=False
        ) as lucide_draw:
            draw_icon(ICON_ENTITY, (0.0, 0.0, 16.0, 16.0), size=16)

        draw_from_pack.assert_called_once()
        pack_id, icon_name = draw_from_pack.call_args.args[:2]
        self.assertEqual(pack_id, "godot_hierarchy")
        self.assertEqual(icon_name, ICON_ENTITY)
        lucide_draw.assert_not_called()

    def test_draw_icon_falls_back_when_godot_pack_missing(self) -> None:
        with patch("engine.editor.ui.icons._draw_icon_from_pack", return_value=False) as draw_from_pack, patch(
            "engine.editor.ui.icons._draw_lucide_icon", return_value=True
        ) as lucide_draw:
            draw_icon(ICON_ENTITY, (0.0, 0.0, 16.0, 16.0), size=16)

        draw_from_pack.assert_called_once()
        lucide_draw.assert_called_once()


if __name__ == "__main__":
    unittest.main()
