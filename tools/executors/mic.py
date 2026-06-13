"""Microphone control tool — mute/unmute."""


def exec_mic_control(state: str) -> str:
    from tools.system.mic import mic_control
    return mic_control(state.strip().lower())
