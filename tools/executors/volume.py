"""Volume control tool — delegates to tools.system.volume."""


def exec_volume_control(level: str) -> str:
    from tools.system.volume import volume_control
    return volume_control(level.strip().lower())
