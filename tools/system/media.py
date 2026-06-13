import os
import time
try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

PREVIOUS_TRACK_PRESS_COUNT = max(2, int(os.getenv("JARVIS_PREVIOUS_TRACK_PRESS_COUNT", "2")))
PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS = float(os.getenv("JARVIS_PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS", "0.18"))

def media_control(command: str) -> str:
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed")

    cmd = command.lower().strip()
    if cmd in {"play", "pause", "play_pause", "toggle"}:
        pyautogui.press("playpause")
        return "Toggling play/pause"
    if cmd in {"next", "next_track"}:
        pyautogui.press("nexttrack")
        return "Skipping to next track"
    if cmd in {"previous", "prev", "previous_track"}:
        for idx in range(PREVIOUS_TRACK_PRESS_COUNT):
            pyautogui.press("prevtrack")
            if idx < PREVIOUS_TRACK_PRESS_COUNT - 1:
                time.sleep(max(0.05, PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS))
        return "Going to previous track"
    raise ValueError("Unsupported media command")
