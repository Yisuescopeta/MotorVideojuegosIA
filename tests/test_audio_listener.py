"""
tests/test_audio_listener.py - Tests for AudioListener2D component and spatial audio.
"""

import math
import unittest

from engine.components.audio_listener_2d import AudioListener2D
from engine.components.audiosource import AudioSource
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.audio_system import AudioSystem


class AudioListener2DComponentTests(unittest.TestCase):
    """Test AudioListener2D component creation, serialization, and defaults."""

    def test_default_values(self) -> None:
        listener = AudioListener2D()
        self.assertTrue(listener.enabled)
        self.assertTrue(listener.is_active)
        self.assertEqual(listener.max_distance, 1000.0)
        self.assertEqual(listener.attenuation_mode, "inverse")
        self.assertEqual(listener.pan_strength, 1.0)

    def test_custom_values(self) -> None:
        listener = AudioListener2D(
            enabled=True,
            is_active=False,
            max_distance=500.0,
            attenuation_mode="linear",
            pan_strength=0.5,
        )
        self.assertTrue(listener.enabled)
        self.assertFalse(listener.is_active)
        self.assertEqual(listener.max_distance, 500.0)
        self.assertEqual(listener.attenuation_mode, "linear")
        self.assertEqual(listener.pan_strength, 0.5)

    def test_to_dict(self) -> None:
        listener = AudioListener2D(
            is_active=True,
            max_distance=300.0,
            attenuation_mode="exponential",
            pan_strength=0.8,
        )
        data = listener.to_dict()
        self.assertEqual(data["enabled"], True)
        self.assertEqual(data["is_active"], True)
        self.assertEqual(data["max_distance"], 300.0)
        self.assertEqual(data["attenuation_mode"], "exponential")
        self.assertEqual(data["pan_strength"], 0.8)

    def test_from_dict(self) -> None:
        data = {
            "enabled": False,
            "is_active": True,
            "max_distance": 750.0,
            "attenuation_mode": "linear",
            "pan_strength": 0.3,
        }
        listener = AudioListener2D.from_dict(data)
        self.assertFalse(listener.enabled)
        self.assertTrue(listener.is_active)
        self.assertEqual(listener.max_distance, 750.0)
        self.assertEqual(listener.attenuation_mode, "linear")
        self.assertEqual(listener.pan_strength, 0.3)

    def test_from_dict_roundtrip(self) -> None:
        original = AudioListener2D(
            is_active=True,
            max_distance=400.0,
            attenuation_mode="inverse",
            pan_strength=0.6,
        )
        data = original.to_dict()
        restored = AudioListener2D.from_dict(data)
        self.assertEqual(restored.is_active, original.is_active)
        self.assertEqual(restored.max_distance, original.max_distance)
        self.assertEqual(restored.attenuation_mode, original.attenuation_mode)
        self.assertEqual(restored.pan_strength, original.pan_strength)


class AudioSpatialAttenuationTests(unittest.TestCase):
    """Test spatial audio attenuation and pan calculations."""

    def test_attenuation_inverse_mode(self) -> None:
        result = AudioSystem._spatial_attenuation(0.0, 1000.0, "inverse")
        self.assertAlmostEqual(result, 1.0, places=4)

        result = AudioSystem._spatial_attenuation(100.0, 1000.0, "inverse")
        self.assertAlmostEqual(result, 0.5, places=4)

        result = AudioSystem._spatial_attenuation(1000.0, 1000.0, "inverse")
        expected = 1.0 / 11.0
        self.assertAlmostEqual(result, expected, places=4)

    def test_attenuation_linear_mode(self) -> None:
        result = AudioSystem._spatial_attenuation(0.0, 1000.0, "linear")
        self.assertAlmostEqual(result, 1.0, places=4)

        result = AudioSystem._spatial_attenuation(500.0, 1000.0, "linear")
        self.assertAlmostEqual(result, 0.5, places=4)

        result = AudioSystem._spatial_attenuation(1000.0, 1000.0, "linear")
        self.assertAlmostEqual(result, 0.0, places=4)

        result = AudioSystem._spatial_attenuation(1500.0, 1000.0, "linear")
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_attenuation_exponential_mode(self) -> None:
        result = AudioSystem._spatial_attenuation(0.0, 1000.0, "exponential")
        self.assertAlmostEqual(result, 1.0, places=4)

        # exp(-100 * 0.005) = exp(-0.5) ≈ 0.6065
        result = AudioSystem._spatial_attenuation(100.0, 1000.0, "exponential")
        self.assertAlmostEqual(result, 0.6065, places=3)

    def test_compute_spatial_volume_no_blend(self) -> None:
        volume = AudioSystem._compute_spatial_volume(1.0, 0.0, 100.0, 1000.0, "inverse")
        self.assertAlmostEqual(volume, 1.0, places=4)

    def test_compute_spatial_volume_full_blend(self) -> None:
        volume = AudioSystem._compute_spatial_volume(1.0, 1.0, 0.0, 1000.0, "inverse")
        self.assertAlmostEqual(volume, 1.0, places=4)

        volume = AudioSystem._compute_spatial_volume(1.0, 1.0, 100.0, 1000.0, "inverse")
        self.assertAlmostEqual(volume, 0.5, places=4)

    def test_compute_spatial_volume_half_blend(self) -> None:
        volume = AudioSystem._compute_spatial_volume(1.0, 0.5, 0.0, 1000.0, "inverse")
        self.assertAlmostEqual(volume, 1.0, places=4)

        # attenuation at 100 = 0.5, blend 0.5 => 1.0 * (1 + (0.5-1)*0.5) = 0.75
        volume = AudioSystem._compute_spatial_volume(1.0, 0.5, 100.0, 1000.0, "inverse")
        self.assertAlmostEqual(volume, 0.75, places=4)

    def test_spatial_pan_center(self) -> None:
        pan = AudioSystem._spatial_pan(0.0, 0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(pan, 0.0, places=4)

    def test_spatial_pan_right(self) -> None:
        pan = AudioSystem._spatial_pan(10.0, 0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(pan, 0.0, places=4)

        pan = AudioSystem._spatial_pan(10.0, 10.0, 0.0, 0.0, 1.0)
        expected = math.sin(math.pi / 4)
        self.assertAlmostEqual(pan, expected, places=4)

    def test_spatial_pan_left(self) -> None:
        pan = AudioSystem._spatial_pan(-10.0, 0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(pan, 0.0, places=4)

        pan = AudioSystem._spatial_pan(-10.0, 10.0, 0.0, 0.0, 1.0)
        expected = math.sin(3 * math.pi / 4)
        self.assertAlmostEqual(pan, expected, places=4)

    def test_spatial_pan_strength(self) -> None:
        pan_full = AudioSystem._spatial_pan(10.0, 10.0, 0.0, 0.0, 1.0)
        pan_half = AudioSystem._spatial_pan(10.0, 10.0, 0.0, 0.0, 0.5)
        self.assertAlmostEqual(pan_half, pan_full * 0.5, places=4)


class AudioSystemSpatialTests(unittest.TestCase):
    """Test AudioSystem spatial audio integration with listener and sources."""

    def _make_world_with_listener(
        self,
        listener_x: float = 0.0,
        listener_y: float = 0.0,
    ) -> tuple[World, Entity, AudioSystem]:
        world = World()
        system = AudioSystem()
        listener_entity = Entity("Listener")
        listener_entity.add_component(Transform(x=listener_x, y=listener_y))
        listener_entity.add_component(AudioListener2D(is_active=True))
        world.add_entity(listener_entity)
        return world, listener_entity, system

    def _make_world_with_audio_source(
        self,
        source_x: float = 0.0,
        source_y: float = 0.0,
        spatial_blend: float = 1.0,
        volume: float = 1.0,
    ) -> tuple[World, Entity, AudioSystem]:
        world, _, system = self._make_world_with_listener()
        entity = Entity("TestSource")
        entity.add_component(Transform(x=source_x, y=source_y))
        audio = AudioSource(
            asset_path="assets/test.wav",
            volume=volume,
            spatial_blend=spatial_blend,
            play_on_awake=True,
        )
        entity.add_component(audio)
        world.add_entity(entity)
        return world, entity, system

    def test_update_with_listener_applies_spatial_volume(self) -> None:
        world, entity, system = self._make_world_with_audio_source(
            source_x=100.0, source_y=0.0, spatial_blend=1.0, volume=1.0,
        )

        system.update(world, game_time=10.0)
        voice = system._runtime.get_voice("TestSource")
        self.assertIsNotNone(voice)
        assert voice is not None
        self.assertLess(voice.volume, 1.0)

    def test_update_no_listener_preserves_base_volume(self) -> None:
        world = World()
        system = AudioSystem()
        entity = Entity("TestSource")
        entity.add_component(Transform(x=100.0, y=0.0))
        audio = AudioSource(
            asset_path="assets/test.wav",
            volume=1.0,
            spatial_blend=1.0,
            play_on_awake=True,
        )
        entity.add_component(audio)
        world.add_entity(entity)

        system.update(world, game_time=10.0)
        voice = system._runtime.get_voice("TestSource")
        self.assertIsNotNone(voice)
        assert voice is not None
        self.assertAlmostEqual(voice.volume, 1.0, places=4)

    def test_update_spatial_blend_zero_no_attenuation(self) -> None:
        world, entity, system = self._make_world_with_audio_source(
            source_x=200.0, source_y=0.0, spatial_blend=0.0, volume=1.0,
        )

        system.update(world, game_time=10.0)
        voice = system._runtime.get_voice("TestSource")
        self.assertIsNotNone(voice)
        assert voice is not None
        self.assertAlmostEqual(voice.volume, 1.0, places=4)

    def test_update_disabled_listener_no_attenuation(self) -> None:
        world, listener_entity, system = self._make_world_with_listener()
        listener = listener_entity.get_component(AudioListener2D)
        assert listener is not None
        listener.is_active = False

        entity = Entity("TestSource")
        entity.add_component(Transform(x=100.0, y=0.0))
        audio = AudioSource(
            asset_path="assets/test.wav",
            volume=1.0,
            spatial_blend=1.0,
            play_on_awake=True,
        )
        entity.add_component(audio)
        world.add_entity(entity)

        system.update(world, game_time=10.0)
        voice = system._runtime.get_voice("TestSource")
        self.assertIsNotNone(voice)
        assert voice is not None
        self.assertAlmostEqual(voice.volume, 1.0, places=4)

    def test_update_attenuation_increases_with_distance(self) -> None:
        world = World()
        system = AudioSystem()
        listener_entity = Entity("Listener")
        listener_entity.add_component(Transform(x=0.0, y=0.0))
        listener_entity.add_component(AudioListener2D(is_active=True, attenuation_mode="inverse"))
        world.add_entity(listener_entity)

        source_near = Entity("NearSource")
        source_near.add_component(Transform(x=10.0, y=0.0))
        audio_near = AudioSource(
            asset_path="assets/test.wav",
            volume=1.0,
            spatial_blend=1.0,
            play_on_awake=True,
        )
        source_near.add_component(audio_near)
        world.add_entity(source_near)

        source_far = Entity("FarSource")
        source_far.add_component(Transform(x=200.0, y=0.0))
        audio_far = AudioSource(
            asset_path="assets/test.wav",
            volume=1.0,
            spatial_blend=1.0,
            play_on_awake=True,
        )
        source_far.add_component(audio_far)
        world.add_entity(source_far)

        system.update(world, game_time=10.0)

        voice_near = system._runtime.get_voice("NearSource")
        voice_far = system._runtime.get_voice("FarSource")
        self.assertIsNotNone(voice_near)
        self.assertIsNotNone(voice_far)
        assert voice_near is not None
        assert voice_far is not None
        self.assertGreater(voice_near.volume, voice_far.volume)

    def test_play_with_listener_applies_spatial_volume_immediately(self) -> None:
        world, listener_entity, system = self._make_world_with_listener()
        entity = Entity("TestSource")
        entity.add_component(Transform(x=100.0, y=0.0))
        audio = AudioSource(
            asset_path="assets/test.wav",
            volume=1.0,
            spatial_blend=1.0,
        )
        entity.add_component(audio)
        world.add_entity(entity)

        result = system.play(world, "TestSource", game_time=10.0)
        self.assertTrue(result)
        voice = system._runtime.get_voice("TestSource")
        self.assertIsNotNone(voice)
        assert voice is not None
        self.assertLess(voice.volume, 1.0)


if __name__ == "__main__":
    unittest.main()
