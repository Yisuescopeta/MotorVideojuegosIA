"""
tests/test_audio_system.py - Tests for AudioSource component, AudioSystem, and RuntimeAPI audio endpoints.
"""

import tempfile
import time
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.audiosource import AudioSource
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.audio_system import AudioSystem


class AudioSourceSerializationTests(unittest.TestCase):
    """Test AudioSource serialization and runtime properties."""

    def test_to_dict_contains_all_serializable_fields(self) -> None:
        audio = AudioSource(
            asset_path="assets/test.wav",
            volume=0.8,
            pitch=1.5,
            loop=True,
            play_on_awake=True,
            spatial_blend=0.5,
        )
        audio.is_playing = True
        data = audio.to_dict()
        self.assertEqual(data["asset_path"], "assets/test.wav")
        self.assertEqual(data["volume"], 0.8)
        self.assertEqual(data["pitch"], 1.5)
        self.assertTrue(data["loop"])
        self.assertTrue(data["play_on_awake"])
        self.assertEqual(data["spatial_blend"], 0.5)
        self.assertTrue(data["is_playing"])
        self.assertNotIn("playback_position", data)
        self.assertNotIn("playback_duration", data)
        self.assertNotIn("is_paused", data)

    def test_from_dict_roundtrip(self) -> None:
        original = AudioSource(
            asset_path="assets/test.wav",
            volume=0.8,
            pitch=1.5,
            loop=True,
            play_on_awake=True,
            spatial_blend=0.5,
        )
        original.is_playing = True
        data = original.to_dict()
        restored = AudioSource.from_dict(data)
        self.assertEqual(restored.asset_path, "assets/test.wav")
        self.assertEqual(restored.volume, 0.8)
        self.assertEqual(restored.pitch, 1.5)
        self.assertTrue(restored.loop)
        self.assertTrue(restored.play_on_awake)
        self.assertEqual(restored.spatial_blend, 0.5)
        self.assertTrue(restored.is_playing)

    def test_from_dict_backward_compat_without_new_fields(self) -> None:
        legacy_data = {
            "enabled": True,
            "asset": {"guid": "", "path": "assets/legacy.wav"},
            "asset_path": "assets/legacy.wav",
            "volume": 0.5,
            "pitch": 1.0,
            "loop": False,
            "play_on_awake": True,
            "spatial_blend": 0.0,
            "is_playing": False,
        }
        audio = AudioSource.from_dict(legacy_data)
        self.assertEqual(audio.asset_path, "assets/legacy.wav")
        self.assertEqual(audio.volume, 0.5)
        self.assertFalse(audio.is_paused)
        self.assertEqual(audio.playback_position, 0.0)
        self.assertEqual(audio.playback_duration, 0.0)

    def test_runtime_properties_default_values(self) -> None:
        audio = AudioSource()
        self.assertEqual(audio.playback_position, 0.0)
        self.assertEqual(audio.playback_duration, 0.0)
        self.assertFalse(audio.is_paused)

    def test_playback_position_setter(self) -> None:
        audio = AudioSource()
        audio.playback_position = 5.0
        self.assertEqual(audio.playback_position, 5.0)
        audio.playback_position = 0.0
        self.assertEqual(audio.playback_position, 0.0)
        audio.playback_position = -10.0
        self.assertEqual(audio.playback_position, 0.0)

    def test_playback_duration_setter(self) -> None:
        audio = AudioSource()
        audio.playback_duration = 10.0
        self.assertEqual(audio.playback_duration, 10.0)
        audio.playback_duration = 0.0
        self.assertEqual(audio.playback_duration, 0.0)
        audio.playback_duration = -5.0
        self.assertEqual(audio.playback_duration, 0.0)

    def test_playback_position_frozen_when_paused(self) -> None:
        audio = AudioSource()
        audio._is_paused = True
        audio._playback_position = 3.5
        self.assertEqual(audio.playback_position, 3.5)

    def test_playback_position_computed_when_playing(self) -> None:
        audio = AudioSource()
        audio.is_playing = True
        audio._is_paused = False
        audio._playback_start_time = time.time()
        audio._playback_position = 1.0
        pos = audio.playback_position
        self.assertGreaterEqual(pos, 1.0)


class AudioSystemUnitTests(unittest.TestCase):
    """Test AudioSystem play/stop/pause/resume/update logic."""

    def _make_world_with_audio(self, asset_path: str = "assets/test.wav") -> tuple[World, Entity]:
        world = World()
        entity = Entity("TestAudio")
        audio = AudioSource(asset_path=asset_path, volume=1.0, loop=False)
        entity.add_component(audio)
        world.add_entity(entity)
        return world, entity

    def test_play_sets_is_playing_and_initializes_runtime_state(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()

        result = system.play(world, "TestAudio")
        self.assertTrue(result)
        audio = entity.get_component(AudioSource)
        assert audio is not None
        self.assertTrue(audio.is_playing)
        self.assertFalse(audio.is_paused)
        self.assertGreater(audio._playback_start_time, 0)

    def test_play_returns_false_for_missing_entity(self) -> None:
        system = AudioSystem()
        world, _ = self._make_world_with_audio()

        result = system.play(world, "NonExistent")
        self.assertFalse(result)

    def test_play_returns_false_for_disabled_component(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.enabled = False

        result = system.play(world, "TestAudio")
        self.assertFalse(result)

    def test_play_returns_false_for_entity_without_audio(self) -> None:
        system = AudioSystem()
        world = World()
        entity = Entity("NoAudio")
        world.add_entity(entity)

        result = system.play(world, "NoAudio")
        self.assertFalse(result)

    def test_stop_resets_is_playing_and_runtime_state(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        system.play(world, "TestAudio")
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio._playback_position = 5.0
        audio._playback_duration = 10.0

        result = system.stop(world, "TestAudio")
        self.assertTrue(result)
        self.assertFalse(audio.is_playing)
        self.assertEqual(audio._playback_position, 0.0)
        self.assertEqual(audio._playback_start_time, 0.0)
        self.assertFalse(audio._is_paused)

    def test_stop_returns_false_for_missing_entity(self) -> None:
        system = AudioSystem()
        world, _ = self._make_world_with_audio()

        result = system.stop(world, "NonExistent")
        self.assertFalse(result)

    def test_pause_freezes_position_and_sets_paused_flag(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        system.play(world, "TestAudio")
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio._playback_position = 3.0

        result = system.pause(world, "TestAudio")
        self.assertTrue(result)
        self.assertTrue(audio.is_paused)
        self.assertEqual(audio._playback_position, 3.0)
        self.assertEqual(audio._playback_start_time, 0.0)
        self.assertTrue(audio.is_playing)

    def test_pause_returns_false_when_not_playing(self) -> None:
        system = AudioSystem()
        world, _ = self._make_world_with_audio()

        result = system.pause(world, "TestAudio")
        self.assertFalse(result)

    def test_pause_returns_false_when_already_paused(self) -> None:
        system = AudioSystem()
        world, _ = self._make_world_with_audio()
        system.play(world, "TestAudio")
        system.pause(world, "TestAudio")

        result = system.pause(world, "TestAudio")
        self.assertFalse(result)

    def test_resume_restarts_from_frozen_position(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        system.play(world, "TestAudio")
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio._playback_position = 3.0
        system.pause(world, "TestAudio")

        result = system.resume(world, "TestAudio")
        self.assertTrue(result)
        self.assertFalse(audio.is_paused)
        self.assertGreater(audio._playback_start_time, 0)

    def test_resume_returns_false_when_not_paused(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        system.play(world, "TestAudio")

        result = system.resume(world, "TestAudio")
        self.assertFalse(result)

    def test_resume_returns_false_for_missing_entity(self) -> None:
        system = AudioSystem()
        world, _ = self._make_world_with_audio()

        result = system.resume(world, "NonExistent")
        self.assertFalse(result)

    def test_update_sets_is_playing_for_play_on_awake(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.play_on_awake = True
        audio.is_playing = False

        system.update(world)
        self.assertTrue(audio.is_playing)

    def test_update_auto_stops_non_looping_audio_at_duration(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.loop = False
        audio._playback_duration = 5.0
        audio._playback_position = 4.9
        audio._playback_start_time = time.time() - 4.9
        audio.is_playing = True
        audio._is_paused = False

        system.update(world)
        self.assertFalse(audio.is_playing)
        self.assertEqual(audio._playback_position, 0.0)

    def test_update_does_not_stop_looping_audio(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.loop = True
        audio._playback_duration = 5.0
        audio._playback_position = 4.9
        audio._playback_start_time = time.time() - 4.9
        audio.is_playing = True
        audio._is_paused = False

        system.update(world)
        self.assertTrue(audio.is_playing)

    def test_play_on_awake_initializes_playback_start_time(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.play_on_awake = True
        audio.is_playing = False
        audio._playback_start_time = 0.0

        system.update(world)
        self.assertTrue(audio.is_playing)
        self.assertGreater(audio._playback_start_time, 0)

    def test_play_on_awake_with_game_time_uses_deterministic_time(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.play_on_awake = True
        audio.is_playing = False
        audio._playback_start_time = 0.0

        game_time = 100.0
        system.update(world, game_time=game_time)
        self.assertTrue(audio.is_playing)
        self.assertEqual(audio._playback_start_time, game_time)

    def test_playback_position_uses_effective_time(self) -> None:
        audio = AudioSource(asset_path="assets/test.wav")
        audio.is_playing = True
        audio._is_paused = False
        audio._playback_start_time = 10.0
        audio._playback_position = 0.0

        audio.set_effective_time(15.0)
        self.assertEqual(audio.playback_position, 5.0)

    def test_playback_position_uses_wall_time_when_no_effective(self) -> None:
        audio = AudioSource(asset_path="assets/test.wav")
        audio.is_playing = True
        audio._is_paused = False
        audio._playback_start_time = time.time() - 5.0
        audio._playback_position = 0.0

        audio.clear_effective_time()
        pos = audio.playback_position
        self.assertGreaterEqual(pos, 5.0)

    def test_update_with_game_time_uses_deterministic_position(self) -> None:
        system = AudioSystem()
        world, entity = self._make_world_with_audio()
        audio = entity.get_component(AudioSource)
        assert audio is not None
        audio.play_on_awake = True
        audio.is_playing = False
        audio._playback_start_time = 0.0
        audio._playback_duration = 0.0

        game_time = 100.0
        system.update(world, game_time=game_time)

        self.assertTrue(audio.is_playing)
        self.assertEqual(audio._playback_start_time, game_time)
        audio.set_effective_time(game_time)
        self.assertEqual(audio.playback_position, 0.0)

        game_time_2 = 105.0
        audio.set_effective_time(game_time_2)
        self.assertEqual(audio.playback_position, 5.0)


class RuntimeAPIAudioIntegrationTests(unittest.TestCase):
    """Test RuntimeAPI audio endpoints through EngineAPI."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        levels_dir = self.project_root / "levels"
        levels_dir.mkdir(parents=True, exist_ok=True)
        source_level = Path(__file__).resolve().parents[1] / "levels" / "demo_level.json"
        (levels_dir / "demo_level.json").write_text(source_level.read_text(encoding="utf-8"), encoding="utf-8")
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _make_api_with_audio(self) -> None:
        self.api.create_audio_source(
            "TestAudio",
            audio={"asset_path": "assets/test.wav", "volume": 0.8, "loop": False},
        )

    def test_play_audio_sets_is_playing(self) -> None:
        self._make_api_with_audio()
        result = self.api.play_audio("TestAudio")
        self.assertTrue(result["success"])
        state = self.api.get_audio_state("TestAudio")
        self.assertTrue(state["is_playing"])

    def test_stop_audio_clears_is_playing(self) -> None:
        self._make_api_with_audio()
        self.api.play_audio("TestAudio")
        result = self.api.stop_audio("TestAudio")
        self.assertTrue(result["success"])
        state = self.api.get_audio_state("TestAudio")
        self.assertFalse(state["is_playing"])

    def test_pause_audio_sets_paused_flag(self) -> None:
        self._make_api_with_audio()
        self.api.play_audio("TestAudio")
        result = self.api.pause_audio("TestAudio")
        self.assertTrue(result["success"])
        state = self.api.get_audio_state("TestAudio")
        self.assertTrue(state["is_paused"])
        self.assertTrue(state["is_playing"])

    def test_resume_audio_clears_paused_flag(self) -> None:
        self._make_api_with_audio()
        self.api.play_audio("TestAudio")
        self.api.pause_audio("TestAudio")
        result = self.api.resume_audio("TestAudio")
        self.assertTrue(result["success"])
        state = self.api.get_audio_state("TestAudio")
        self.assertFalse(state["is_paused"])
        self.assertTrue(state["is_playing"])

    def test_get_audio_state_includes_runtime_fields(self) -> None:
        self._make_api_with_audio()
        self.api.play_audio("TestAudio")
        state = self.api.get_audio_state("TestAudio")
        self.assertIn("playback_position", state)
        self.assertIn("playback_duration", state)
        self.assertIn("is_paused", state)
        self.assertIsInstance(state["playback_position"], float)
        self.assertIsInstance(state["playback_duration"], float)
        self.assertIsInstance(state["is_paused"], bool)

    def test_get_audio_state_includes_serializable_fields(self) -> None:
        self._make_api_with_audio()
        state = self.api.get_audio_state("TestAudio")
        self.assertIn("asset_path", state)
        self.assertIn("volume", state)
        self.assertIn("pitch", state)
        self.assertIn("loop", state)
        self.assertIn("play_on_awake", state)
        self.assertIn("spatial_blend", state)
        self.assertIn("is_playing", state)

    def test_pause_audio_fails_when_not_playing(self) -> None:
        self._make_api_with_audio()
        result = self.api.pause_audio("TestAudio")
        self.assertFalse(result["success"])

    def test_resume_audio_fails_when_not_paused(self) -> None:
        self._make_api_with_audio()
        self.api.play_audio("TestAudio")
        result = self.api.resume_audio("TestAudio")
        self.assertFalse(result["success"])

    def test_play_audio_fails_for_nonexistent_entity(self) -> None:
        result = self.api.play_audio("NonExistent")
        self.assertFalse(result["success"])

    def test_stop_audio_fails_for_nonexistent_entity(self) -> None:
        result = self.api.stop_audio("NonExistent")
        self.assertFalse(result["success"])

    def test_pause_resume_play_cycle_maintains_state(self) -> None:
        self._make_api_with_audio()
        self.api.play_audio("TestAudio")
        self.api.pause_audio("TestAudio")
        state_paused = self.api.get_audio_state("TestAudio")
        self.assertTrue(state_paused["is_paused"])
        self.assertTrue(state_paused["is_playing"])

        self.api.resume_audio("TestAudio")
        state_resumed = self.api.get_audio_state("TestAudio")
        self.assertFalse(state_resumed["is_paused"])
        self.assertTrue(state_resumed["is_playing"])

        self.api.stop_audio("TestAudio")
        state_stopped = self.api.get_audio_state("TestAudio")
        self.assertFalse(state_stopped["is_playing"])
        self.assertFalse(state_stopped["is_paused"])


if __name__ == "__main__":
    unittest.main()
