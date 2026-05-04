"""tests/test_resource_registry.py — Tests para ResourceRegistry."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from engine.resources.resource_registry import ResourceRegistry


class TestResourceRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ResourceRegistry()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_json(self, filename: str, data: dict) -> Path:
        path = self.tmp / filename
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_load_tileset(self):
        """Cargar tileset, cache hit en segunda carga."""
        data = {"resource_id": "ts1", "resource_name": "MyTileset"}
        path = self._write_json("test.tileset", data)

        r1 = self.registry.load(str(path))
        self.assertIsNotNone(r1)
        self.assertEqual(r1.resource_id, "ts1")

        r2 = self.registry.load(str(path))
        self.assertIs(r1, r2)

    def test_refcount(self):
        """Dos cargas = refcount 2, unload baja a 1."""
        data = {"resource_id": "ts2", "resource_name": "Tileset2"}
        path = self._write_json("test2.tileset", data)

        self.registry.load(str(path))
        self.registry.load(str(path))
        entry = self.registry._entries[str(path)]
        self.assertEqual(entry.ref_count, 2)

        self.registry.unload(str(path))
        self.assertEqual(entry.ref_count, 1)
        self.assertTrue(self.registry.is_loaded(str(path)))

    def test_unload_frees(self):
        """Refcount llega a 0, recurso desaparece."""
        data = {"resource_id": "ts3"}
        path = self._write_json("test3.tileset", data)

        self.registry.load(str(path))
        self.registry.unload(str(path))
        self.assertFalse(self.registry.is_loaded(str(path)))

    def test_auto_detect_type(self):
        """Detecta tipo por extensión."""
        registry = ResourceRegistry()
        self.assertEqual(registry._detect_type("file.tileset"), "tileset")
        self.assertEqual(registry._detect_type("file.anim"), "animation")
        self.assertEqual(registry._detect_type("file.sframes"), "sprite_frames")
        self.assertEqual(registry._detect_type("file.shader2d"), "shader2d")
        self.assertEqual(registry._detect_type("file.theme"), "theme")
        self.assertEqual(registry._detect_type("file.json"), "auto")
        self.assertEqual(registry._detect_type("file.unknown"), "auto")
        self.assertEqual(registry._detect_type("nopath"), "auto")

    def test_load_nonexistent(self):
        """Path no existe, retorna None."""
        result = self.registry.load("/nonexistent/path.file")
        self.assertIsNone(result)

        result2 = self.registry.load("")
        self.assertIsNone(result2)

    def test_is_loaded(self):
        """Verificar si un recurso está cargado."""
        data = {"resource_id": "ts4"}
        path = self._write_json("test4.tileset", data)

        self.assertFalse(self.registry.is_loaded(str(path)))
        self.registry.load(str(path))
        self.assertTrue(self.registry.is_loaded(str(path)))

    def test_clear(self):
        """clear() vacía el registry."""
        data1 = {"resource_id": "ts5"}
        data2 = {"resource_id": "ts6"}
        p1 = self._write_json("a.tileset", data1)
        p2 = self._write_json("b.tileset", data2)

        self.registry.load(str(p1))
        self.registry.load(str(p2))
        self.assertTrue(self.registry.is_loaded(str(p1)))
        self.assertTrue(self.registry.is_loaded(str(p2)))

        self.registry.clear()
        self.assertFalse(self.registry.is_loaded(str(p1)))
        self.assertFalse(self.registry.is_loaded(str(p2)))

    def test_multiple_types(self):
        """Cargar diferentes tipos sin conflicto."""
        ts_data = {"resource_id": "ts_multi"}
        anim_data = {"resource_id": "anim_multi", "resource_name": "Idle", "tracks": []}
        sf_data = {"resource_id": "sf_multi", "animations": {}}
        shader_data = {"resource_id": "sh_multi", "uniforms": {}}
        theme_data = {"resource_id": "th_multi", "name": "MyTheme", "styleboxes": {}, "colors": {}, "fonts": {}}

        ts_path = self._write_json("multi.tileset", ts_data)
        anim_path = self._write_json("multi.anim", anim_data)
        sf_path = self._write_json("multi.sframes", sf_data)
        shader_path = self._write_json("multi.shader2d", shader_data)
        theme_path = self._write_json("multi.theme", theme_data)

        ts = self.registry.load(str(ts_path), "tileset")
        anim = self.registry.load(str(anim_path), "animation")
        sf = self.registry.load(str(sf_path), "sprite_frames")
        sh = self.registry.load(str(shader_path), "shader2d")
        th = self.registry.load(str(theme_path), "theme")

        self.assertIsNotNone(ts)
        self.assertIsNotNone(anim)
        self.assertIsNotNone(sf)
        self.assertIsNotNone(sh)
        self.assertIsNotNone(th)

        self.assertTrue(self.registry.is_loaded(str(ts_path)))
        self.assertTrue(self.registry.is_loaded(str(anim_path)))
        self.assertTrue(self.registry.is_loaded(str(sf_path)))
        self.assertTrue(self.registry.is_loaded(str(shader_path)))
        self.assertTrue(self.registry.is_loaded(str(theme_path)))


if __name__ == "__main__":
    unittest.main()
