_MIC_MUTED = False

def mic_control(state: str) -> str:
    global _MIC_MUTED

    state = state.lower()
    if state == "mute":
        _MIC_MUTED = True
        return "PC microphone muted (simulated)"
    if state == "unmute":
        _MIC_MUTED = False
        return "PC microphone unmuted (simulated)"
    raise ValueError("Unsupported mic state")
