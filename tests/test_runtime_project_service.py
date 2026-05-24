from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
