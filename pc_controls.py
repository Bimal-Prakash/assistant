import logging
import os
import subprocess
import time
from typing import Any, Dict

logger = logging.getLogger("jarvis.pc_controls")

try:
    import pyautogui  # type: ignore
except Exception:  # pragma: no cover
    pyautogui = None

try:
    import screen_brightness_control as sbc  # type: ignore
except Exception:  # pragma: no cover
    sbc = None

try:
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
except Exception:  # pragma: no cover
    CLSCTX_ALL = None
    AudioUtilities = None
    IAudioEndpointVolume = None

_MIC_MUTED = False

PREVIOUS_TRACK_PRESS_COUNT = max(2, int(os.getenv("JARVIS_PREVIOUS_TRACK_PRESS_COUNT", "2")))
PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS = float(os.getenv("JARVIS_PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS", "0.18"))


def _volume_control(level: str) -> str:
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


def get_endpoint_volume_percent() -> int:
    if AudioUtilities is None or IAudioEndpointVolume is None or CLSCTX_ALL is None:
        raise RuntimeError("Windows endpoint volume API is unavailable")

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = interface.QueryInterface(IAudioEndpointVolume)
    return round(float(volume.GetMasterVolumeLevelScalar()) * 100)


def _brightness_control(level: str) -> str:
    if sbc is None:
        raise RuntimeError("screen_brightness_control is not installed")

    level = level.lower()
    current = int(sbc.get_brightness(display=0)[0])

    if level == "up":
        sbc.set_brightness(min(100, current + 15), display=0)
        return "Increasing PC brightness"
    if level == "down":
        sbc.set_brightness(max(0, current - 15), display=0)
        return "Decreasing PC brightness"
    if level == "max":
        sbc.set_brightness(100, display=0)
        return "Setting PC brightness to max"
    if level == "min":
        sbc.set_brightness(5, display=0)
        return "Setting PC brightness to minimum"
    if level.isdigit():
        value = int(level)
        if value < 0 or value > 100:
            raise ValueError("Brightness percentage must be between 0 and 100")
        sbc.set_brightness(value, display=0)
        return f"Setting PC brightness to {value}%"
    raise ValueError("Unsupported brightness level")


def _power_control(power_type: str, delay_seconds: int = 3) -> str:
    power_type = power_type.lower()

    if power_type == "shutdown":
        command = ["shutdown", "/s", "/t", "1"]
        message = "Shutting down PC"
    elif power_type == "restart":
        command = ["shutdown", "/r", "/t", "1"]
        message = "Restarting PC"
    elif power_type == "sleep":
        command = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
        message = "Putting PC to sleep"
    else:
        raise ValueError("Unsupported power type")

    logger.warning("Power action requested: %s. Executing in %s seconds.", power_type, delay_seconds)
    time.sleep(delay_seconds)
    subprocess.run(command, check=False)
    return message


def _mic_control(state: str) -> str:
    global _MIC_MUTED

    state = state.lower()
    if state == "mute":
        _MIC_MUTED = True
        return "PC microphone muted (simulated)"
    if state == "unmute":
        _MIC_MUTED = False
        return "PC microphone unmuted (simulated)"
    raise ValueError("Unsupported mic state")


def _media_control(command: str) -> str:
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
        # Most players jump to track start on first press; subsequent presses move backward.
        for idx in range(PREVIOUS_TRACK_PRESS_COUNT):
            pyautogui.press("prevtrack")
            if idx < PREVIOUS_TRACK_PRESS_COUNT - 1:
                time.sleep(max(0.05, PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS))
        return "Going to previous track"
    raise ValueError("Unsupported media command")


def _wifi_interface_name() -> str:
    # Try to find the actual Wi-Fi adapter name from netsh output.
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "").lower()
    for line in output.splitlines():
        if "wi-fi" in line or "wifi" in line or "wireless" in line:
            parts = line.split()
            if parts:
                return " ".join(parts[3:]) if len(parts) > 3 else parts[-1]
    return "Wi-Fi"


def _network_control(network_type: str, state: str) -> str:
    network_type = network_type.lower().strip()
    state = state.lower().strip()

    if network_type == "wifi":
        if state == "open":
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:network-wifi"], shell=False)
            return "Opened Wi-Fi settings."
        admin_state = "enabled" if state == "on" else "disabled"
        iface = _wifi_interface_name()
        command = ["netsh", "interface", "set", "interface", iface, f"admin={admin_state}"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return f"Wi-Fi turned {state}"
        error_text = (result.stderr or result.stdout or "Failed to toggle Wi-Fi").strip()
        if "requires elevation" in error_text.lower() or "run as administrator" in error_text.lower():
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:network-wifi"], shell=False)
            return "Wi-Fi toggle needs administrator access. Opened Wi-Fi settings for manual control."
        raise RuntimeError(error_text)

    if network_type == "bluetooth":
        if state in {"on", "off"}:
            desired = "On" if state == "on" else "Off"
            ps_script = (
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$null = [Windows.Devices.Radios.Radio,Windows.Devices.Radios,ContentType=WindowsRuntime]; "
                "$null = [Windows.Devices.Radios.RadioAccessStatus,Windows.Devices.Radios,ContentType=WindowsRuntime]; "
                "$null = [Windows.Devices.Radios.RadioState,Windows.Devices.Radios,ContentType=WindowsRuntime]; "
                "$access = [Windows.Devices.Radios.Radio]::RequestAccessAsync().AsTask().GetAwaiter().GetResult(); "
                "if ($access -ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed) { exit 5 }; "
                "$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().AsTask().GetAwaiter().GetResult(); "
                "$bt = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth } | Select-Object -First 1; "
                "if ($null -eq $bt) { exit 6 }; "
                f"$result = $bt.SetStateAsync([Windows.Devices.Radios.RadioState]::{desired}).AsTask().GetAwaiter().GetResult(); "
                "if ($result -ne [Windows.Devices.Radios.RadioAccessStatus]::Allowed) { exit 7 }; "
                "exit 0"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return f"Bluetooth turned {state}"

        # Fallback when direct toggle is blocked by OS policy/environment.
        subprocess.Popen(["cmd", "/c", "start", "ms-settings:bluetooth"], shell=False)
        if state in {"on", "off"}:
            return "Could not toggle Bluetooth automatically here. Opened Bluetooth settings."
        return "Opened Bluetooth settings."

    raise ValueError("Unsupported network type")


def execute_pc_system_action(action_obj: Dict[str, Any]) -> Dict[str, Any]:
    action = str(action_obj.get("action", "")).lower()

    try:
        if action == "volume_control":
            level = str(action_obj.get("level", "")).lower()
            message = _volume_control(level)
        elif action == "brightness_control":
            level = str(action_obj.get("level", "")).lower()
            message = _brightness_control(level)
        elif action == "power_control":
            power_type = str(action_obj.get("type", "")).lower()
            message = _power_control(power_type, delay_seconds=3)
        elif action == "mic_control":
            state = str(action_obj.get("state", "")).lower()
            message = _mic_control(state)
        elif action == "media_control":
            command = str(action_obj.get("state", action_obj.get("type", ""))).lower()
            message = _media_control(command)
        elif action == "network_control":
            network_type = str(action_obj.get("type", "")).lower()
            state = str(action_obj.get("state", "")).lower()
            message = _network_control(network_type, state)
        else:
            return {"ok": False, "message": "Unsupported PC control action"}

        return {"ok": True, "message": message}
    except Exception as exc:
        logger.exception("PC control failed for action=%s", action)
        return {"ok": False, "message": f"PC control failed: {exc}"}

