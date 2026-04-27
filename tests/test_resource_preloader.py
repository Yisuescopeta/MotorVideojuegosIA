"""
tests/test_resource_preloader.py - Tests para ResourcePreloader.
"""

import unittest

from engine.assets.asset_reference import normalize_asset_reference
from engine.components.resource_preloader import ResourcePreloader


class TestResourcePreloader(unittest.TestCase):
    """Tests del componente ResourcePreloader."""

    def test_default_initialization(self) -> None:
        """Verifica que el componente se inicializa con valores por defecto correctos."""
        preloader = ResourcePreloader()
        self.assertTrue(preloader.enabled)
        self.assertTrue(preloader.auto_scan)
        self.assertTrue(preloader.include_textures)
        self.assertTrue(preloader.include_audio)
        self.assertEqual(preloader.assets, [])

    def test_custom_initialization(self) -> None:
        """Verifica que se pueden configurar propiedades personalizadas."""
        ref = normalize_asset_reference({"path": "assets/test.png"})
        preloader = ResourcePreloader(
            auto_scan=False,
            assets=[ref],
            include_textures=True,
            include_audio=False,
        )
        self.assertTrue(preloader.enabled)
        self.assertFalse(preloader.auto_scan)
        self.assertTrue(preloader.include_textures)
        self.assertFalse(preloader.include_audio)
        self.assertEqual(len(preloader.assets), 1)

    def test_serialization(self) -> None:
        """Verifica que to_dict y from_dict funcionan correctamente."""
        ref = normalize_asset_reference({"path": "assets/test.png"})
        original = ResourcePreloader(
            auto_scan=False,
            assets=[ref],
            include_textures=True,
            include_audio=False,
        )

        data = original.to_dict()
        self.assertEqual(data["auto_scan"], False)
        self.assertEqual(data["include_textures"], True)
        self.assertEqual(data["include_audio"], False)
        self.assertEqual(len(data["assets"]), 1)

        restored = ResourcePreloader.from_dict(data)
        self.assertEqual(restored.auto_scan, original.auto_scan)
        self.assertEqual(restored.include_textures, original.include_textures)
        self.assertEqual(restored.include_audio, original.include_audio)
        self.assertEqual(len(restored.assets), len(original.assets))

    def test_from_dict_with_missing_fields(self) -> None:
        """Verifica que from_dict usa valores por defecto para campos faltantes."""
        data = {"enabled": True}
        restored = ResourcePreloader.from_dict(data)
        self.assertTrue(restored.auto_scan)
        self.assertTrue(restored.include_textures)
        self.assertTrue(restored.include_audio)
        self.assertEqual(restored.assets, [])


if __name__ == "__main__":
    unittest.main()
