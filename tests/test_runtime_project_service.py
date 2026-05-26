from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from engine.runtime.runtime_project_service import RuntimeProjectService


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


if __name__ == "__main__":
    unittest.main()
