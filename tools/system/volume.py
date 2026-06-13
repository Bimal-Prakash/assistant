import logging
try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

try:
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
except Exception:
    CLSCTX_ALL = None
    AudioUtilities = None
    IAudioEndpointVolume = None

logger = logging.getLogger("jarvis.pc_controls.volume")

def _set_endpoint_volume_percent(value: int) -> str:
    if AudioUtilities is not None and IAudioEndpointVolume is not None and CLSCTX_ALL is not None:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(value / 100.0, None)
            try:
                volume.SetMute(0, None)
            except Exception:
                pass
            return f"Setting PC volume to {value}%"
        except Exception:
            logger.exception("Endpoint volume API failed; falling back to volume keys")

    for _ in range(50):
        pyautogui.press("volumedown")
    steps_up = round((value / 100) * 50)
    for _ in range(steps_up):
        pyautogui.press("volumeup")
    return f"Setting PC volume to {value}%"

def volume_control(level: str) -> str:
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed")

    level = level.lower()
    if level in {"100", "maximum"}:
        level = "max"
    if level == "up":
        for _ in range(5):
            pyautogui.press("volumeup")
        return "Increasing PC volume"
    if level == "down":
        for _ in range(5):
            pyautogui.press("volumedown")
        return "Decreasing PC volume"
    if level == "mute":
        pyautogui.press("volumemute")
        return "Muting PC volume"
    if level == "max":
        return _set_endpoint_volume_percent(100)
    if level.isdigit():
        value = int(level)
        if value < 0 or value > 100:
            raise ValueError("Volume percentage must be between 0 and 100")
        return _set_endpoint_volume_percent(value)
    raise ValueError("Unsupported volume level")

def get_endpoint_volume_percent() -> int:
    if AudioUtilities is None or IAudioEndpointVolume is None or CLSCTX_ALL is None:
        raise RuntimeError("Windows endpoint volume API is unavailable")

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = interface.QueryInterface(IAudioEndpointVolume)
    return round(float(volume.GetMasterVolumeLevelScalar()) * 100)
