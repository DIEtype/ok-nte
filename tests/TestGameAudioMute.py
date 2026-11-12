import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pycaw.constants import AudioSessionState

from src.audio.mute import mute_game_audio


class TestGameAudioMute(unittest.TestCase):
    def setUp(self):
        self.window = SimpleNamespace(hwnd=123, to_handle_mute=True)
        self.devices = Mock()
        self.devices.GetCount.return_value = 1
        device = self.devices.Item.return_value
        manager = device.Activate.return_value.QueryInterface.return_value
        self.sessions = manager.GetSessionEnumerator.return_value

        patches = (
            patch("comtypes.CoInitializeEx"),
            patch("comtypes.CoUninitialize"),
            patch("win32process.GetWindowThreadProcessId", return_value=(1, 42)),
            patch("pycaw.utils.AudioSession", side_effect=lambda session: session),
            patch("pycaw.utils.AudioUtilities.GetDeviceEnumerator"),
        )
        for patcher in patches:
            self.addCleanup(patcher.stop)
        _, self.uninitialize, _, _, enumerator = [patcher.start() for patcher in patches]
        enumerator.return_value.EnumAudioEndpoints.return_value = self.devices

    def audio_session(self, pid, muted, state=AudioSessionState.Active):
        volume = Mock()
        volume.GetMute.side_effect = lambda: muted

        def set_mute(value, _context):
            nonlocal muted
            muted = value

        volume.SetMute.side_effect = set_mute
        return SimpleNamespace(ProcessId=pid, State=state, SimpleAudioVolume=volume)

    def set_sessions(self, *sessions):
        self.sessions.GetCount.return_value = len(sessions)
        controls = []
        for session in sessions:
            control = Mock()
            control.QueryInterface.return_value = session
            controls.append(control)
        self.sessions.GetSession.side_effect = controls

    def test_restores_only_changed_game_sessions_after_error(self):
        unmuted_game = self.audio_session(42, False)
        already_muted = self.audio_session(42, True)
        another_app = self.audio_session(99, False)
        expired_game = self.audio_session(42, False, AudioSessionState.Expired)
        self.set_sessions(unmuted_game, already_muted, another_app, expired_game)

        with self.assertRaisesRegex(RuntimeError, "task stopped"):
            with mute_game_audio(self.window):
                self.assertTrue(unmuted_game.SimpleAudioVolume.GetMute())
                self.assertFalse(another_app.SimpleAudioVolume.GetMute())
                self.assertFalse(self.window.to_handle_mute)
                raise RuntimeError("task stopped")

        self.assertFalse(unmuted_game.SimpleAudioVolume.GetMute())
        self.assertTrue(already_muted.SimpleAudioVolume.GetMute())
        self.assertTrue(self.window.to_handle_mute)
        self.uninitialize.assert_called_once()
        already_muted.SimpleAudioVolume.SetMute.assert_not_called()
        another_app.SimpleAudioVolume.SetMute.assert_not_called()
        expired_game.SimpleAudioVolume.SetMute.assert_not_called()

    def test_no_game_audio_leaves_background_policy_active(self):
        self.set_sessions(self.audio_session(99, False))
        with mute_game_audio(self.window):
            self.assertTrue(self.window.to_handle_mute)
            self.uninitialize.assert_called_once()

    def test_restores_original_background_policy(self):
        self.window.to_handle_mute = False
        unmuted_game = self.audio_session(42, False)
        self.set_sessions(unmuted_game)

        with mute_game_audio(self.window):
            self.assertTrue(unmuted_game.SimpleAudioVolume.GetMute())

        self.assertFalse(unmuted_game.SimpleAudioVolume.GetMute())
        self.assertFalse(self.window.to_handle_mute)
