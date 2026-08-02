"""Media control tool — play/pause, next, previous."""


def exec_media_control(state: str) -> str:
    from tools.system.media import media_control
    return media_control(state.strip().lower())

def exec_get_current_media_info() -> str:
    from tools.system.media import get_current_media_info
    return get_current_media_info()
