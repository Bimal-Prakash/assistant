"""Get system information: time, date, battery level."""

import subprocess
from datetime import datetime


def exec_get_system_info(query: str = "time") -> str:
    q = query.strip().lower()

    if "time" in q:
        return f"Current time: {datetime.now().strftime('%I:%M %p')}"

    if "date" in q or "day" in q or "today" in q:
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}"

    if "battery" in q or "charge" in q or "power" in q:
        try:
            r = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance -ClassName Win32_Battery "
                 "| Select-Object -ExpandProperty EstimatedChargeRemaining"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return f"Battery level: {r.stdout.strip()}%"
        except Exception:
            pass
        return "Battery information is not available on this device."

    if "volume" in q or "sound" in q:
        try:
            from tools.system.volume import get_endpoint_volume_percent
            vol = get_endpoint_volume_percent()
            return f"Current volume: {vol}%"
        except Exception as e:
            return f"Could not retrieve volume: {e}"

    if "brightness" in q or "screen" in q:
        try:
            import screen_brightness_control as sbc
            bright = sbc.get_brightness(display=0)[0]
            return f"Current brightness: {bright}%"
        except Exception as e:
            return f"Could not retrieve brightness: {e}"

    # Fallback: return everything
    now = datetime.now()
    try:
        from tools.system.volume import get_endpoint_volume_percent
        vol = f", Volume: {get_endpoint_volume_percent()}%"
    except Exception:
        vol = ""
    return (
        f"Time: {now.strftime('%I:%M %p')}, "
        f"Date: {now.strftime('%A, %B %d, %Y')}{vol}"
    )
