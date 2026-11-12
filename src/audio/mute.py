"""Temporarily mute the Windows audio sessions owned by a game window."""

from contextlib import ExitStack, contextmanager

from ok import Logger

logger = Logger.get_logger(__name__)

RPC_E_CHANGED_MODE = -2147417850


@contextmanager
def mute_game_audio(window):
    with ExitStack() as cleanup:
        try:
            active = _mute_window(window, cleanup)
        except Exception as error:
            # An audio device failure should not prevent fishing.
            logger.warning(f"Could not mute game audio: {type(error).__name__}")
            active = False
        if not active:
            cleanup.close()
            logger.warning("No game audio session could be muted")
        yield


def _mute_window(window, cleanup: ExitStack) -> bool:
    if window is None or not window.hwnd:
        return False

    from comtypes import COINIT_MULTITHREADED, CoInitializeEx, CoUninitialize
    from win32process import GetWindowThreadProcessId

    _, pid = GetWindowThreadProcessId(window.hwnd)
    if not pid:
        return False

    try:
        CoInitializeEx(COINIT_MULTITHREADED)
    except OSError as error:
        if error.winerror != RPC_E_CHANGED_MODE:
            raise
        # The task thread already has a usable COM apartment.
    else:
        cleanup.callback(CoUninitialize)

    cleanup.callback(setattr, window, "to_handle_mute", window.to_handle_mute)
    window.to_handle_mute = False
    return _mute_render_sessions(pid, cleanup)


def _mute_render_sessions(pid: int, cleanup: ExitStack) -> bool:
    from comtypes import CLSCTX_ALL, COMError
    from pycaw.api.audiopolicy import IAudioSessionControl2, IAudioSessionManager2
    from pycaw.constants import AudioSessionState, DEVICE_STATE, EDataFlow
    from pycaw.utils import AudioSession, AudioUtilities

    enumerator = AudioUtilities.GetDeviceEnumerator()
    devices = enumerator.EnumAudioEndpoints(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
    found = False
    for index in range(devices.GetCount()):
        try:
            device = devices.Item(index)
            interface = device.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None)
            manager = interface.QueryInterface(IAudioSessionManager2)
            sessions = manager.GetSessionEnumerator()
        except (COMError, OSError):
            logger.warning("Could not enumerate audio sessions on an output device")
            continue

        for session_index in range(sessions.GetCount()):
            try:
                control = sessions.GetSession(session_index)
                session = AudioSession(control.QueryInterface(IAudioSessionControl2))
                if session.ProcessId != pid or session.State == AudioSessionState.Expired:
                    continue
                volume = session.SimpleAudioVolume
                if not volume.GetMute():
                    volume.SetMute(True, None)
                    cleanup.callback(_restore_mute, volume)
                found = True
            except (COMError, OSError):
                logger.warning("Could not read or mute an audio session")

    return found


def _restore_mute(volume) -> None:
    try:
        volume.SetMute(False, None)
    except Exception as error:
        logger.warning(f"Could not restore a game audio session: {type(error).__name__}")
