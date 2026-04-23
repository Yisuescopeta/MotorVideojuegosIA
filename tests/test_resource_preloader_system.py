"""
tests/test_resource_preloader_system.py - Tests para ResourcePreloaderSystem.
"""

import unittest
from unittest.mock import MagicMock, Mock

from engine.assets.asset_reference import normalize_asset_reference
from engine.components.resource_preloader import ResourcePreloader
from engine.components.sprite import Sprite
from engine.components.animator import Animator
from engine.components.audiosource import AudioSource
from engine.ecs.world import World
from engine.systems.resource_preloader_system import ResourcePreloaderSystem


class MockTextureManager:
    """Mock de TextureManager para tests."""

    def __init__(self) -> None:
        self.loaded: dict[str, str] = {}

    def load(self, path: str, cache_key: str | None = None) -> Mock:
        key = str(cache_key or path)
        self.loaded[key] = path
        return Mock(id=1)


class MockAssetService:
    """Mock de AssetService para tests."""

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {
            "assets/test.png": {
                "absolute_path": "c:/project/assets/test.png",
                "guid": "test-guid-123",
                "path": "assets/test.png",
            },
            "assets/sound.wav": {
                "absolute_path": "c:/project/assets/sound.wav",
                "guid": "sound-guid-456",
                "path": "assets/sound.wav",
            },
        }

    def get_asset_resolver(self) -> Mock:
        resolver = Mock()
        resolver.resolve_entry.side_effect = lambda ref: self.entries.get(ref.get("path", ""))
        return resolver


class TestResourcePreloaderSystem(unittest.TestCase):
    """Tests del sistema ResourcePreloaderSystem."""

    def setUp(self) -> None:
        """Configura mocks para cada test."""
        self.texture_manager = MockTextureManager()
        self.asset_service = MockAssetService()
        self.system = ResourcePreloaderSystem()
        self.system.set_texture_manager(self.texture_manager)
        self.system._asset_service = self.asset_service

    def test_preload_with_manual_assets(self) -> None:
        """Verifica que se precarguen assets manuales desde el componente."""
        world = World()
        entity = world.create_entity()
        ref = normalize_asset_reference({"path": "assets/test.png"})
        preloader = ResourcePreloader(auto_scan=False, assets=[ref], include_textures=True, include_audio=False)
        entity.add_component(preloader)

        texture_count, resolved_count = self.system.preload(world)

        self.assertEqual(texture_count, 1)
        self.assertEqual(resolved_count, 1)
        self.assertIn("test-guid-123", self.texture_manager.loaded)

    def test_preload_auto_scan_sprite(self) -> None:
        """Verifica que se detecte y precargue texturas de Sprite."""
        world = World()
        entity = world.create_entity()
        sprite = Sprite(texture_path="assets/test.png")
        entity.add_component(sprite)

        entity2 = world.create_entity()
        preloader = ResourcePreloader(auto_scan=True)
        entity2.add_component(preloader)

        texture_count, resolved_count = self.system.preload(world)

        self.assertEqual(texture_count, 1)
        self.assertEqual(resolved_count, 1)

    def test_preload_auto_scan_animator(self) -> None:
        """Verifica que se detecte y precargue sprite sheets de Animator."""
        world = World()
        entity = world.create_entity()
        animator = Animator(sprite_sheet="assets/test.png")
        entity.add_component(animator)

        entity2 = world.create_entity()
        preloader = ResourcePreloader(auto_scan=True)
        entity2.add_component(preloader)

        texture_count, resolved_count = self.system.preload(world)

        self.assertEqual(texture_count, 1)
        self.assertEqual(resolved_count, 1)

    def test_preload_auto_scan_audio(self) -> None:
        """Verifica que se detecten assets de audio cuando include_audio=True."""
        world = World()
        entity = world.create_entity()
        audio = AudioSource(asset="assets/sound.wav")
        entity.add_component(audio)

        entity2 = world.create_entity()
        preloader = ResourcePreloader(auto_scan=True, include_audio=True, include_textures=False)
        entity2.add_component(preloader)

        texture_count, resolved_count = self.system.preload(world)

        # Audio solo se resuelve, no se carga en TextureManager
        self.assertEqual(texture_count, 0)
        self.assertEqual(resolved_count, 1)

    def test_preload_without_preloader_component(self) -> None:
        """Verifica que el sistema funcione aunque no haya componente ResourcePreloader."""
        world = World()
        entity = world.create_entity()
        sprite = Sprite(texture_path="assets/test.png")
        entity.add_component(sprite)

        texture_count, resolved_count = self.system.preload(world)

        # Debería escanear por defecto aunque no haya componente
        self.assertEqual(texture_count, 1)
        self.assertEqual(resolved_count, 1)

    def test_preload_with_no_project_service(self) -> None:
        """Verifica que el sistema maneje ausencia de AssetService."""
        system = ResourcePreloaderSystem()
        system.set_texture_manager(self.texture_manager)

        world = World()
        texture_count, resolved_count = system.preload(world)

        self.assertEqual(texture_count, 0)
        self.assertEqual(resolved_count, 0)


if __name__ == "__main__":
    unittest.main()
