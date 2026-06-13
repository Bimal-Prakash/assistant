"""Brightness control tool — delegates to tools.system.brightness."""


def exec_brightness_control(level: str) -> str:
    from tools.system.brightness import brightness_control
    return brightness_control(level.strip().lower())
