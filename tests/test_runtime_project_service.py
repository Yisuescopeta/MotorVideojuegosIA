from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.assets.asset_database import AssetDatabase
from engine.assets.asset_resolver import AssetResolver
from engine.runtime.runtime_project_service import RuntimeProjectService
from engine.systems.ui_render_system import UIRenderSystem


class RuntimeProjectServiceTests(unittest.TestCase):
    def test_get_project_path_resolves_key_under_runtime_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = RuntimeProjectService(tmp)

            self.assertEqual(service.get_project_path("assets"), (Path(tmp) / "assets").resolve())

    def test_to_relative_path_returns_portable_base_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = RuntimeProjectService(tmp)

            self.assertEqual(service.to_relative_path(Path(tmp) / "assets" / "hero.png"), "assets/hero.png")

    def test_resolve_path_extracts_asset_from_pak_when_missing_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "game.pak", "w") as pak:
                pak.writestr("assets/ui/background.png", b"fake_png")
            service = RuntimeProjectService(root)

            resolved = service.resolve_path("assets/ui/background.png")

            self.assertEqual(resolved, (root / "content" / "assets" / "ui" / "background.png").resolve())
            self.assertEqual(resolved.read_bytes(), b"fake_png")

    def test_resolve_path_caches_missing_pak_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "game.pak", "w") as pak:
                pak.writestr("assets/ui/background.png", b"fake_png")
            service = RuntimeProjectService(root)
            real_zipfile = zipfile.ZipFile

            with patch("engine.runtime.runtime_project_service.zipfile.ZipFile", wraps=real_zipfile) as zip_cls:
                first = service.resolve_path("assets/ui/missing.png")
                second = service.resolve_path("assets/ui/missing.png")

            self.assertEqual(first, (root / "assets" / "ui" / "missing.png").resolve())
            self.assertEqual(second, first)
            self.assertEqual(zip_cls.call_count, 1)

    def test_extract_packed_scripts_returns_scripts_import_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "game.pak", "w") as pak:
                pak.writestr("scripts/player_powerups.py", b"VALUE = 3\n")
                pak.writestr("scripts/gameplay/helpers.py", b"HELPER = True\n")
            service = RuntimeProjectService(root)

            scripts_root = service.extract_packed_scripts()

            self.assertIsNotNone(scripts_root)
            self.assertEqual((scripts_root / "player_powerups.py").read_bytes(), b"VALUE = 3\n")
            self.assertEqual((scripts_root / "gameplay" / "helpers.py").read_bytes(), b"HELPER = True\n")

    def test_resolve_asset_entry_uses_manifest_by_path_and_guid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "content" / "assets" / "ui" / "button.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"fake_png")
            (root / "game.manifest.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "path": "assets/ui/button.png",
                                "guid": "guid_button",
                                "kind": "texture",
                                "dependencies": ["assets/ui/button.meta"],
                            }
                        ],
                        "scripts": [
                            {
                                "path": "scripts/gameplay/player.py",
                                "guid": "guid_script",
                                "kind": "script",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service = RuntimeProjectService(root)

            by_path = service.resolve_asset_entry({"path": "assets/ui/button.png"})
            by_guid = service.resolve_asset_entry({"guid": "guid_button"})
            script = service.resolve_asset_entry({"path": "scripts/gameplay/player.py"})

            self.assertEqual(by_path["guid"], "guid_button")
            self.assertEqual(by_guid["path"], "assets/ui/button.png")
            self.assertEqual(by_path["absolute_path"], asset.resolve().as_posix())
            self.assertEqual(by_path["reference"], {"path": "assets/ui/button.png", "guid": "guid_button"})
            self.assertEqual(by_path["dependencies"], ["assets/ui/button.meta"])
            self.assertEqual(script["path"], "scripts/gameplay/player.py")

    def test_asset_resolver_uses_runtime_manifest_without_asset_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "content" / "assets").mkdir(parents=True)
            (root / "content" / "assets" / "hero.png").write_bytes(b"fake_png")
            (root / "game.manifest.json").write_text(
                json.dumps({"assets": [{"path": "assets/hero.png", "guid": "guid_hero"}]}),
                encoding="utf-8",
            )
            resolver = AssetResolver(RuntimeProjectService(root))

            with patch.object(AssetDatabase, "get_asset_entry", side_effect=AssertionError("authoring DB used")):
                entry = resolver.resolve_entry({"path": "assets/hero.png"})

            self.assertEqual(entry["guid"], "guid_hero")
            self.assertTrue(entry["absolute_path"].endswith("content/assets/hero.png"))

    def test_asset_database_read_only_does_not_refresh_catalog_for_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "content" / "assets" / "hero.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"fake_png")
            database = AssetDatabase(RuntimeProjectService(root))

            with patch.object(database, "refresh_catalog", side_effect=AssertionError("refresh_catalog used")):
                entry = database.get_asset_entry({"path": "assets/hero.png"})

            self.assertIsNone(entry)

    def test_ui_render_uses_runtime_manifest_without_authoring_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "content" / "assets" / "ui" / "button.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"fake_png")
            (root / "game.manifest.json").write_text(
                json.dumps({"assets": [{"path": "assets/ui/button.png", "guid": "guid_button"}]}),
                encoding="utf-8",
            )
            renderer = UIRenderSystem()
            renderer.set_project_service(RuntimeProjectService(root))

            with (
                patch.object(AssetDatabase, "refresh_catalog", side_effect=AssertionError("authoring catalog used")),
                patch.object(
                    renderer._texture_manager,
                    "load",
                    return_value=SimpleNamespace(id=1, width=16, height=16),
                ) as load_texture,
            ):
                texture = renderer._load_texture({"path": "assets/ui/button.png"})

            self.assertEqual(texture.id, 1)
            load_texture.assert_called_once_with(asset.resolve().as_posix(), cache_key="guid_button")


if __name__ == "__main__":
    unittest.main()
