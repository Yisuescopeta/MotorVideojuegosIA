"""
tests/test_audio_pyray_backend.py - Unit tests for PyrayAudioBackend.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock

from engine.audio.contracts import AudioPlaybackRequest, AudioVoiceState
from engine.audio.pyray_backend import PyrayAudioBackend


class TestPyrayAudioBackend(unittest.TestCase):

    def setUp(self):
        self.backend = PyrayAudioBackend()

    def _make_request(self, **kwargs):
        defaults = {
            "entity_name": "test_sound",
            "asset_path": "test.wav",
            "resolved_asset_path": "/abs/test.wav",
            "volume": 1.0,
            "pitch": 1.0,
            "loop": False,
        }
        defaults.update(kwargs)
        return AudioPlaybackRequest(**defaults)

    def _make_voice(self, **kwargs):
        defaults = {
            "entity_name": "test_sound",
            "asset_path": "test.wav",
            "resolved_asset_path": "/abs/test.wav",
            "is_playing": True,
        }
        defaults.update(kwargs)
        return AudioVoiceState(**defaults)

    @patch("engine.audio.pyray_backend.rl")
    def test_start_calls_init_and_play(self, mock_rl):
        mock_rl.InitAudioDevice.return_value = None
        mock_rl.LoadSound.return_value = MagicMock(name="sound")
        request = self._make_request()
        voice = self._make_voice()

        self.backend.start(request, voice)

        mock_rl.InitAudioDevice.assert_called()
        mock_rl.LoadSound.assert_called_with("/abs/test.wav")
        mock_rl.SetSoundVolume.assert_called()
        mock_rl.SetSoundPitch.assert_called()
        mock_rl.PlaySound.assert_called()

    @patch("engine.audio.pyray_backend.rl")
    def test_start_noop_when_device_fails(self, mock_rl):
        mock_rl.InitAudioDevice.side_effect = RuntimeError("no device")
        request = self._make_request()
        voice = self._make_voice()

        self.backend.start(request, voice)

        mock_rl.LoadSound.assert_not_called()
        mock_rl.PlaySound.assert_not_called()

    @patch("engine.audio.pyray_backend.rl")
    def test_pause_resume_stop_delegate(self, mock_rl):
        mock_rl.InitAudioDevice.return_value = None
        mock_sound = MagicMock(name="sound")
        mock_rl.LoadSound.return_value = mock_sound

        request = self._make_request()
        voice = self._make_voice()
        self.backend.start(request, voice)

        # Pause
        self.backend.pause(voice)
        mock_rl.PauseSound.assert_called_with(mock_sound)

        # Resume
        self.backend.resume(voice)
        mock_rl.ResumeSound.assert_called_with(mock_sound)

        # Stop
        self.backend.stop(voice)
        mock_rl.StopSound.assert_called_with(mock_sound)

    @patch("engine.audio.pyray_backend.rl")
    def test_update_restarts_looping_sound(self, mock_rl):
        mock_rl.InitAudioDevice.return_value = None
        mock_sound = MagicMock(name="sound")
        mock_rl.LoadSound.return_value = mock_sound

        request = self._make_request(loop=True)
        voice = self._make_voice(loop=True)
        self.backend.start(request, voice)

        # Simulate sound stopped playing -> should restart
        mock_rl.IsSoundPlaying.return_value = False
        mock_rl.PlaySound.reset_mock()

        self.backend.update({"test_sound": voice}, 1.0)

        mock_rl.PlaySound.assert_called_once_with(mock_sound)

    @patch("engine.audio.pyray_backend.rl")
    def test_update_does_not_restart_non_looping(self, mock_rl):
        mock_rl.InitAudioDevice.return_value = None
        mock_sound = MagicMock(name="sound")
        mock_rl.LoadSound.return_value = mock_sound

        request = self._make_request(loop=False)
        voice = self._make_voice()
        self.backend.start(request, voice)

        mock_rl.IsSoundPlaying.return_value = False
        mock_rl.PlaySound.reset_mock()

        self.backend.update({"test_sound": voice}, 1.0)

        mock_rl.PlaySound.assert_not_called()

    @patch("engine.audio.pyray_backend.rl")
    def test_shutdown_unloads_and_closes(self, mock_rl):
        mock_rl.InitAudioDevice.return_value = None
        mock_sound = MagicMock(name="sound")
        mock_rl.LoadSound.return_value = mock_sound

        request = self._make_request()
        voice = self._make_voice()
        self.backend.start(request, voice)

        self.backend.shutdown()

        mock_rl.UnloadSound.assert_called_with(mock_sound)
        mock_rl.CloseAudioDevice.assert_called()

    @patch("engine.audio.pyray_backend.rl")
    def test_graceful_degradation_when_no_device(self, mock_rl):
        """start/pause/resume/stop/shutdown should not raise when device fails."""
        mock_rl.InitAudioDevice.side_effect = RuntimeError("no device")
        request = self._make_request()
        voice = self._make_voice()

        # None of these should raise
        self.backend.start(request, voice)
        self.backend.pause(voice)
        self.backend.resume(voice)
        self.backend.stop(voice)
        self.backend.shutdown()

        mock_rl.LoadSound.assert_not_called()
        mock_rl.PlaySound.assert_not_called()


if __name__ == "__main__":
    unittest.main()
