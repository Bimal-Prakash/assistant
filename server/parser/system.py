import re
from typing import Optional, Dict, Any
from core.schemas import ActionResponse

def _extract_volume_brightness_scope(text: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    has_volume = "volume" in normalized
    has_brightness = "brightness" in normalized
    if has_volume and has_brightness:
        return "both"
    if has_volume:
        return "volume"
    if has_brightness:
        return "brightness"
    return None

def _extract_on_off_direction(text: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    has_on = bool(re.search(r"\bon\b", normalized))
    has_off = bool(re.search(r"\boff\b", normalized))
    if has_on and not has_off:
        return "up"
    if has_off and not has_on:
        return "down"
    return None

def _extract_adjust_direction(text: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", text.strip().lower())

    # Avoid interpreting unrelated "on/off" (e.g., "play song on spotify") as system control.
    control_verbs_present = bool(re.search(r"\b(turn|switch|set|make|change|adjust|increase|decrease|raise|lower)\b", normalized))

    up_patterns = [
        r"\bincrease\b",
        r"\bup\b",
        r"\braise\b",
        r"\blouder\b",
        r"\bhigher\b",
    ]
    down_patterns = [
        r"\bdecrease\b",
        r"\bdown\b",
        r"\breduce\b",
        r"\bquieter\b",
        r"\blower\b",
    ]

    has_up = any(re.search(p, normalized) for p in up_patterns)
    has_down = any(re.search(p, normalized) for p in down_patterns)

    if control_verbs_present:
        if re.search(r"\bon\b", normalized):
            has_up = True
        if re.search(r"\boff\b", normalized):
            has_down = True

    if has_up and not has_down:
        return "up"
    if has_down and not has_up:
        return "down"
    return None

def _build_system_control_action(scope: str, direction: str, target: str) -> ActionResponse:
    if scope == "brightness":
        return ActionResponse(
            action="brightness_control",
            level=direction,
            target=target,
            response=f"Adjusting brightness {direction}.",
        )
    return ActionResponse(
        action="volume_control",
        level=direction,
        target=target,
        response=f"Adjusting volume {direction}.",
    )

def _should_prompt_for_volume_brightness(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if _extract_adjust_direction(normalized) is None:
        return False
    if re.search(r"\b(wifi|wi-fi|bluetooth|mic|microphone|shutdown|restart|sleep|mute|unmute)\b", normalized):
        return False
    if re.search(r"\b(spotify|song|music|track|playlist|play|pause|resume|youtube|video|netflix)\b", normalized):
        return False
    if re.search(r"\b(open|launch|start|run)\b", normalized):
        return False
    return True

def _parse_percentage_level(value: str) -> Optional[int]:
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    match = re.fullmatch(r"(\d{1,3})\s*%?", cleaned)
    if not match:
        return None
    parsed = int(match.group(1))
    if parsed < 0 or parsed > 100:
        return None
    return parsed

def _clean_response_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    placeholders = {
        "<tts_text_optional>",
        "tts_text_optional",
        "<response>",
        "<optional>",
    }
    if lowered in placeholders:
        return None
    if "<" in text and ">" in text:
        return None
    return text

def _clean_slot_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    placeholders = {"<song>", "<text>", "<query>", "<message>", "song", "a song", "any song"}
    if lowered in placeholders:
        return None
    if "<" in text and ">" in text:
        return None
    return text
