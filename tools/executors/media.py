"""Media control tool — play/pause, next, previous."""


def exec_media_control(state: str) -> str:
    from tools.system.media import media_control
    return media_control(state.strip().lower())
