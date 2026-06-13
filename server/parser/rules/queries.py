import re

def _is_conversational_query(normalized: str) -> bool:
    text = re.sub(r"\s+", " ", (normalized or "").strip().lower())
    if not text:
        return False

    command_prefixes = (
        "open ", "close ", "play ", "pause", "resume", "next", "previous", "skip",
        "search ", "find ", "turn ", "set ", "make volume", "increase ", "decrease ",
        "raise ", "lower ", "mute", "unmute", "shutdown", "restart", "sleep",
        "call ", "text ", "message ", "send ",
    )
    if text.startswith(command_prefixes):
        return False

    question_prefixes = (
        "what ", "whats ", "what's ", "who ", "where ", "when ", "why ", "how ",
        "do you ", "can you tell ", "tell me ", "explain ", "define ", "give me ", "say ",
    )
    if text.startswith(question_prefixes):
        return True
    if "?" in text:
        return True
    if text in {"tell me something", "say something", "tell me a joke", "tell me another joke"}:
        return True
    return False
