"""Audio switching tool — delegates to tools.system.audio_switcher."""

def exec_switch_audio_output(device_name: str) -> str:
    from tools.system.audio_switcher import switch_audio_output
    return switch_audio_output(device_name.strip())
