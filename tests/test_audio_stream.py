import unittest

from engine.components.audio_stream_player_2d import AudioStreamPlayer2D
from engine.levels.component_registry import create_default_registry
from engine.resources.audio_stream_resource import AudioStreamResource


class AudioStreamResourceTests(unittest.TestCase):
    def test_create_audio_stream_resource(self) -> None:
        resource = AudioStreamResource()
        self.assertEqual(resource.resource_id, "")
        self.assertEqual(resource.resource_name, "New AudioStream")
        self.assertEqual(resource.audio_type, "wav")
        self.assertEqual(resource.data_path, "")
        self.assertFalse(resource.loop)
        self.assertEqual(resource.volume_db, 0.0)
        self.assertEqual(resource.pitch_scale, 1.0)
        self.assertFalse(resource.stream)

    def test_audio_stream_serialization(self) -> None:
        resource = AudioStreamResource(
            resource_id="audio_001",
            resource_name="Explosion",
            audio_type="ogg",
            data_path="assets/sfx/explosion.ogg",
            loop=False,
            volume_db=-3.0,
            pitch_scale=1.2,
            stream=True,
        )
        data = resource.to_dict()
        restored = AudioStreamResource.from_dict(data)

        self.assertEqual(restored.resource_id, "audio_001")
        self.assertEqual(restored.resource_name, "Explosion")
        self.assertEqual(restored.audio_type, "ogg")
        self.assertEqual(restored.data_path, "assets/sfx/explosion.ogg")
        self.assertFalse(restored.loop)
        self.assertEqual(restored.volume_db, -3.0)
        self.assertEqual(restored.pitch_scale, 1.2)
        self.assertTrue(restored.stream)


class AudioStreamPlayer2DTests(unittest.TestCase):
    def test_create_audio_player(self) -> None:
        player = AudioStreamPlayer2D()
        self.assertTrue(player.enabled)
        self.assertEqual(player.audio_stream_path, "")
        self.assertFalse(player.autoplay)
        self.assertEqual(player.volume_db, 0.0)
        self.assertEqual(player.pitch_scale, 1.0)
        self.assertFalse(player.playing)
        self.assertFalse(player.loop)
        self.assertEqual(player._playback_position, 0.0)

    def test_player_serialization(self) -> None:
        player = AudioStreamPlayer2D(
            enabled=True,
            audio_stream_path="audio/music.json",
            autoplay=True,
            volume_db=-6.0,
            pitch_scale=0.9,
            playing=True,
            loop=True,
        )
        data = player.to_dict()
        restored = AudioStreamPlayer2D.from_dict(data)

        self.assertTrue(restored.enabled)
        self.assertEqual(restored.audio_stream_path, "audio/music.json")
        self.assertTrue(restored.autoplay)
        self.assertEqual(restored.volume_db, -6.0)
        self.assertEqual(restored.pitch_scale, 0.9)
        self.assertTrue(restored.playing)
        self.assertTrue(restored.loop)

    def test_player_play_stop(self) -> None:
        player = AudioStreamPlayer2D()
        self.assertFalse(player.playing)
        self.assertEqual(player._playback_position, 0.0)

        player.play()
        self.assertTrue(player.playing)
        self.assertEqual(player._playback_position, 0.0)

        player.stop()
        self.assertFalse(player.playing)
        self.assertEqual(player._playback_position, 0.0)

    def test_player_autoplay(self) -> None:
        player = AudioStreamPlayer2D(autoplay=True)
        self.assertTrue(player.autoplay)
        self.assertFalse(player.playing)

        player.play()
        self.assertTrue(player.playing)

    def test_player_loop(self) -> None:
        player = AudioStreamPlayer2D(loop=True)
        self.assertTrue(player.loop)

        player2 = AudioStreamPlayer2D(loop=False)
        self.assertFalse(player2.loop)

    def test_registry_creation(self) -> None:
        registry = create_default_registry()
        player = registry.create("AudioStreamPlayer2D", {
            "audio_stream_path": "sfx/hit.wav",
            "autoplay": True,
            "volume_db": -3.0,
            "loop": True,
        })
        self.assertIsInstance(player, AudioStreamPlayer2D)
        self.assertEqual(player.audio_stream_path, "sfx/hit.wav")
        self.assertTrue(player.autoplay)
        self.assertEqual(player.volume_db, -3.0)
        self.assertTrue(player.loop)


if __name__ == "__main__":
    unittest.main()
