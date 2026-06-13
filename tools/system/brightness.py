import logging
try:
    import screen_brightness_control as sbc  # type: ignore
except Exception:
    sbc = None

logger = logging.getLogger("jarvis.pc_controls.brightness")

def brightness_control(level: str) -> str:
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
