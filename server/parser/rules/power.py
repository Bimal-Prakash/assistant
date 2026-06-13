import re

def _is_close_command(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized in {"close", "close jarvis", "close assistant", "close app"}

def _is_close_like_command(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized.startswith("close")

def _is_power_confirmation(text: str, power_type: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    expected = f"confirm {power_type}".strip()
    generic_confirms = {
        "confirm", "confirm it", "yes", "yes confirm", "do it",
        "i am sure", "sure", "yep", "yeah", "of course", "go ahead",
        "confirm shutdown", "confirm restart"
    }
    return normalized == expected or normalized in generic_confirms or expected in normalized or "confirm" in normalized or "sure" in normalized
