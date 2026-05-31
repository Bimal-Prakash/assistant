import json
import logging
import re
import time
from threading import Lock
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from fastapi import FastAPI
from pydantic import BaseModel, Field

from config import (
    ALLOWED_ACTIONS,
    CONTACTS_FILE,
    HOST,
    JARVIS_MEMORY_DATABASE_URL,
    JARVIS_MEMORY_FACT_LIMIT,
    JARVIS_MEMORY_HISTORY_LIMIT,
    PORT,
    WAKE_WORDS,
)
from memory_store import PostgresMemoryStore
from model import ModelError, OllamaCommandModel
from pc_controls import execute_pc_system_action, get_endpoint_volume_percent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("jarvis.api")

app = FastAPI(title="Jarvis Backend", version="1.1.0")
model_client = OllamaCommandModel()


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, description="User speech converted to text")
    client: Optional[str] = Field(default=None, description="android or pc")


class ActionResponse(BaseModel):
    action: str
    app: Optional[str] = None
    url: Optional[str] = None
    contact: Optional[str] = None
    phone: Optional[str] = None
    text: Optional[str] = None
    message: Optional[str] = None
    response: Optional[str] = None
    level: Optional[str] = None
    type: Optional[str] = None
    state: Optional[str] = None
    target: Optional[str] = None


def _normalize_contact_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    return re.sub(r"\D", "", phone)


def _load_contacts(path: Path) -> Dict[str, str]:
    if not path.exists():
        logger.warning("Contacts file not found at %s; continuing with empty contacts", path)
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("contacts.json must contain a JSON object map of name->phone")

    contacts: Dict[str, str] = {}
    for raw_name, raw_phone in data.items():
        if not isinstance(raw_name, str) or not isinstance(raw_phone, str):
            continue
        key = _normalize_contact_key(raw_name)
        if key:
            contacts[key] = _normalize_phone(raw_phone)

    return contacts


CONTACTS = _load_contacts(CONTACTS_FILE)
PENDING_POWER_CONFIRMATIONS: Dict[str, Dict[str, str]] = {}
PENDING_SYSTEM_CONTROL_CLARIFICATIONS: Dict[str, Dict[str, Any]] = {}
SYSTEM_CONTROL_CLARIFY_TTL_SECONDS = 20
_CONFIRMATION_LOCK = Lock()
MEMORY_STORE = PostgresMemoryStore(
    database_url=JARVIS_MEMORY_DATABASE_URL,
    history_limit=JARVIS_MEMORY_HISTORY_LIMIT,
    fact_limit=JARVIS_MEMORY_FACT_LIMIT,
)


def _strip_wake_word(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    for wake_word in WAKE_WORDS:
        if lowered.startswith(wake_word):
            remainder = stripped[len(wake_word) :].lstrip(" ,:-")
            return remainder.strip()
    return ""


def _resolve_contact_phone(contact_name: str) -> Optional[str]:
    key = _normalize_contact_key(contact_name)
    if key in CONTACTS:
        return CONTACTS[key]

    for contact_key, phone in CONTACTS.items():
        if key in contact_key or contact_key in key:
            return phone
    return None


def _extract_target(action_obj: Dict[str, Any], default: str = "android") -> str:
    target = str(action_obj.get("target", default)).strip().lower()
    return target if target in {"android", "pc"} else default


def _confirmation_key(client: str, target: str) -> str:
    client_key = (client or "unknown").strip().lower() or "unknown"
    target_key = (target or "android").strip().lower() or "android"
    return f"{client_key}:{target_key}"


def _is_close_command(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized in {"close", "close jarvis", "close assistant", "close app"}


def _is_close_like_command(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized.startswith("close")


def _is_power_confirmation(text: str, power_type: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    expected = f"confirm {power_type}".strip()
    generic_confirms = {"confirm", "confirm it", "yes", "yes confirm", "do it"}
    return normalized == expected or normalized in generic_confirms


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


def _normalize_spotify_query(raw_query: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (raw_query or "").strip().lower())
    if not text:
        return None

    corrections = {
        "roberry": "robbery",
        "robary": "robbery",
        "robbary": "robbery",
        "jews world": "juice wrld",
        "use world": "juice wrld",
        "juice world": "juice wrld",
        "juicewrld": "juice wrld",
    }
    for src, dst in corrections.items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)

    generic_values = {"", "some", "any", "something", "anything", "random", "song", "songs", "track", "tracks", "music", "playlist", "playlists"}

    def _clean_segment(segment: str, drop_media_words: bool) -> str:
        value = re.sub(r"\s+", " ", (segment or "").strip().lower())
        value = re.sub(r"^(?:please\s+)?(?:some|any|a|an|the)\s+", "", value)
        if drop_media_words:
            value = re.sub(r"\b(?:song|songs|track|tracks|music|playlist|playlists)\b", " ", value)
        value = re.sub(r"\s+", " ", value).strip(" ,.-")
        return value

    by_match = re.match(r"^(.+?)\s+by\s+(.+)$", text)
    if by_match:
        left_raw, artist_raw = by_match.group(1), by_match.group(2)
        title = _clean_segment(left_raw, drop_media_words=True)
        artist = _clean_segment(artist_raw, drop_media_words=False)
        if not artist:
            return title or None
        if not title or title in generic_values:
            return artist
        return f"{title} {artist}".strip()

    text = _clean_segment(text, drop_media_words=True)
    if text in generic_values:
        return None
    return text or None


def _normalize_media_query(raw_query: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (raw_query or "").strip().lower())
    if not text:
        return None

    corrections = {
        "roberry": "robbery",
        "robary": "robbery",
        "robbary": "robbery",
        "jews world": "juice wrld",
        "use world": "juice wrld",
        "juice world": "juice wrld",
        "juicewrld": "juice wrld",
        "you tube": "youtube",
        "yotube": "youtube",
    }
    for src, dst in corrections.items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)

    text = re.sub(r"^(?:please\s+)?(?:play|put on|listen to|search|find)\s+", "", text).strip()
    text = re.sub(r"\b(?:song|songs|music|track|tracks|video|videos)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    if text in {"", "some", "any", "something", "anything", "random"}:
        return None
    return text


def _youtube_search_action(query: str, default_target: str) -> ActionResponse:
    cleaned = _normalize_media_query(query) or query.strip()
    return ActionResponse(
        action="open_website",
        url=f"https://www.youtube.com/results?search_query={quote_plus(cleaned)}",
        target=default_target,
        response=f"Playing {cleaned} on YouTube.",
    )


def _extract_spotify_query(normalized: str) -> Optional[str]:
    text = normalized.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b(?:in|on)\s+spotify(?:\s+app)?\b", "", text).strip()
    text = re.sub(r"^(?:please\s+)?(?:play|put on|listen to|search|find)\s+", "", text).strip()
    return _normalize_spotify_query(text)


def _is_conversational_query(normalized: str) -> bool:
    text = re.sub(r"\s+", " ", (normalized or "").strip().lower())
    if not text:
        return False

    command_prefixes = (
        "open ",
        "close ",
        "play ",
        "pause",
        "resume",
        "next",
        "previous",
        "skip",
        "search ",
        "find ",
        "turn ",
        "set ",
        "make volume",
        "increase ",
        "decrease ",
        "raise ",
        "lower ",
        "mute",
        "unmute",
        "shutdown",
        "restart",
        "sleep",
        "call ",
        "text ",
        "message ",
        "send ",
    )
    if text.startswith(command_prefixes):
        return False

    question_prefixes = (
        "what ",
        "whats ",
        "what's ",
        "who ",
        "where ",
        "when ",
        "why ",
        "how ",
        "do you ",
        "can you tell ",
        "tell me ",
        "explain ",
        "define ",
        "give me ",
        "say ",
    )
    if text.startswith(question_prefixes):
        return True
    if "?" in text:
        return True
    if text in {"tell me something", "say something", "tell me a joke", "tell me another joke"}:
        return True
    return False


def _rule_based_action(text: str, default_target: str) -> Optional[ActionResponse]:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    normalized = re.sub(r"^(?:hey\s+)?jarvis\s+", "", normalized).strip()
    if not normalized:
        return None

    # Handle time queries
    if re.search(r"\bwhat.*\btime\b|\bcurrent\s+time\b|\bwhat\s+is\s+the\s+time\b", normalized):
        from datetime import datetime
        current_time = datetime.now().strftime("%I:%M %p")
        message = f"The current time is {current_time}"
        return ActionResponse(
            action="type_text",
            text=message,
            target=default_target,
            response=message,
        )

    # Handle date and day queries
    if re.search(r"\bwhat.*\bdate\b|\bwhat\s+is\s+today\b|\btoday.*\bdate\b|\bwhat\s+day\b|\bwhat\s+is\s+the\s+day\b", normalized):
        from datetime import datetime
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        message = f"Today is {current_date}"
        return ActionResponse(
            action="type_text",
            text=message,
            target=default_target,
            response=message,
        )

    # Handle name queries
    if re.search(r"\bwhat.*\bmy\s+name\b|\bwhat\s+is\s+my\s+name\b|\bmy\s+name\b|\bwho\s+am\s+i\b", normalized):
        name = MEMORY_STORE.get_fact(client="android", fact_key="name")
        if name:
            message = f"Your name is {name}."
        else:
            message = "I don't know your name yet. Please tell me your name."
        return ActionResponse(
            action="type_text",
            text=message,
            target=default_target,
            response=message,
        )

    # Handle name setting
    name_match = re.match(r"^(?:my\s+name\s+is|i\s+(?:am|am\s+called))\s+(.+)$", normalized)
    if name_match:
        name = name_match.group(1).strip().strip(".,:;!?")
        if name and len(name) > 1:
            MEMORY_STORE.set_fact(client="android", fact_key="name", fact_value=name)
            message = f"Got it! I'll remember that your name is {name}."
            return ActionResponse(
                action="type_text",
                text=message,
                target=default_target,
                response=message,
            )

    volume_query = (
        "volume" in normalized
        and re.search(r"\b(what|whats|what's|current|right now|tell me|mujhe)\b", normalized)
        and not re.search(r"\b(increase|decrease|raise|lower|set|make|turn|mute|unmute)\b|\d", normalized)
    )
    if volume_query:
        try:
            level = get_endpoint_volume_percent()
            message = f"Current volume is {level}%."
        except Exception:
            message = "I could not read the current volume."
        return ActionResponse(
            action="type_text",
            text=message,
            target=default_target,
            response=message,
        )

    youtube_play = re.match(r"^(?:play|put on|listen to)\s+(.+?)\s+(?:on|in)\s+(?:youtube|you tube|yotube)$", normalized)
    if youtube_play:
        return _youtube_search_action(youtube_play.group(1), default_target)

    youtube_search = re.match(r"^(?:search|find)\s+(.+?)\s+(?:on|in)\s+(?:youtube|you tube|yotube)$", normalized)
    if youtube_search:
        return _youtube_search_action(youtube_search.group(1), default_target)

    youtube_tail = re.match(r"^(.+?)\s+(?:on|in)\s+(?:youtube|you tube|yotube)$", normalized)
    if youtube_tail:
        return _youtube_search_action(youtube_tail.group(1), default_target)

    if normalized in {"cancel", "cancel it", "never mind", "forget it"}:
        return ActionResponse(
            action="type_text",
            text="Cancelled.",
            target=default_target,
            response="Cancelled.",
        )

    if normalized in {"bluetooth", "wifi", "wi-fi"}:
        return ActionResponse(
            action="network_control",
            type="wifi" if normalized in {"wifi", "wi-fi"} else "bluetooth",
            state="open",
            target=default_target,
            response="Opening network controls.",
        )

    toggle_network = re.fullmatch(r"turn\s+(on|off)\s+(bluetooth|wifi|wi-fi)", normalized)
    if toggle_network:
        state = toggle_network.group(1)
        network_type = toggle_network.group(2)
        return ActionResponse(
            action="network_control",
            type="wifi" if network_type in {"wifi", "wi-fi"} else "bluetooth",
            state=state,
            target=default_target,
            response=f"Turning {network_type} {state}.",
        )

    close_match = re.match(r"^close\s+(.+)$", normalized)
    if close_match:
        item = close_match.group(1).strip()
        item = re.sub(r"\bon\s+(?:pc|laptop|computer)\b", "", item).strip()
        if item in {"bluetooth", "wifi", "wi-fi"}:
            return ActionResponse(
                action="network_control",
                type="wifi" if item in {"wifi", "wi-fi"} else "bluetooth",
                state="open",
                target=default_target,
                response=f"Opening {item} settings.",
            )
        if item:
            return ActionResponse(
                action="close_app",
                app=item,
                target=default_target,
                response=f"Closing {item}.",
            )

    text_to_match = re.match(
        r'^(?:text|message|send message|send text)\s+(.+?)\s+to\s+(?:the person named\s+)?["\']?(.+?)["\']?$',
        normalized,
    )
    if text_to_match:
        msg = text_to_match.group(1).strip()
        contact = text_to_match.group(2).strip()
        contact = re.sub(r"\s+in\s+whatsapp$", "", contact).strip()
        if msg and contact:
            resolved = _resolve_contact_phone(contact)
            if not resolved:
                return ActionResponse(
                    action="type_text",
                    text=f"I could not find contact {contact}. Please add it in contacts.json.",
                    target=default_target,
                    response=f"I could not find contact {contact}. Please add it in contacts.json.",
                )
            return ActionResponse(
                action="send_whatsapp",
                contact=contact,
                phone=resolved,
                message=msg,
                target=default_target,
                response=f"Sending message to {contact}.",
            )

    website_aliases = {
        "facebook": "https://www.facebook.com",
        "fb": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "insta": "https://www.instagram.com",
        "x": "https://x.com",
        "twitter": "https://x.com",
        "reddit": "https://www.reddit.com",
        "gmail": "https://mail.google.com",
        "google": "https://www.google.com",
        "gemini": "https://gemini.google.com",
        "copilot": "https://copilot.microsoft.com",
    }
    open_web_alias = re.match(r"^(?:open|launch|start|go to|visit)\s+(.+?)(?:\s+(?:in|on)\s+(?:chrome|browser))?$", normalized)
    if open_web_alias:
        site = open_web_alias.group(1).strip()
        site = re.sub(r"\s+app$", "", site).strip()
        if site in website_aliases:
            return ActionResponse(
                action="open_website",
                url=website_aliases[site],
                target=default_target,
                response=f"Opening {site}.",
            )

    open_spotify_and_play = re.match(r"^open\s+spotify\s+(?:and|then)\s+play\s+(.+)$", normalized)
    if open_spotify_and_play:
        query = _normalize_spotify_query(open_spotify_and_play.group(1).strip())
        if query:
            return ActionResponse(
                action="open_app",
                app="spotify",
                text=query,
                target=default_target,
                response=f"Playing {query} on Spotify.",
            )

    open_and_type_match = re.match(r"^(open|launch|start)\s+(.+?)\s+(?:and|then)\s+type\s+(.+)$", normalized)
    if open_and_type_match:
        app_name = open_and_type_match.group(2).strip()
        type_text = open_and_type_match.group(3).strip()
        app_name = re.sub(r"\bon\s+(?:pc|laptop|computer)\b", "", app_name).strip()
        type_text = re.sub(r"\bon\s+(?:pc|laptop|computer)\b", "", type_text).strip()
        if app_name and type_text:
            return ActionResponse(
                action="open_app",
                app=app_name,
                text=type_text,
                target=default_target,
                response=f"Opening {app_name} and typing {type_text}.",
            )

    play_spotify_match = re.match(r"^play\s+(.+?)\s+(?:on|in)\s+spotify$", normalized)
    if play_spotify_match:
        query = _normalize_spotify_query(play_spotify_match.group(1).strip())
        if query:
            return ActionResponse(
                action="open_app",
                app="spotify",
                text=query,
                target=default_target,
                response=f"Playing {query} on Spotify.",
            )

    play_spotify_app_match = re.match(r"^play\s+(.+?)\s+(?:on|in)\s+spotify(?:\s+app)?$", normalized)
    if play_spotify_app_match:
        query = _normalize_spotify_query(play_spotify_app_match.group(1).strip())
        if query:
            return ActionResponse(
                action="open_app",
                app="spotify",
                text=query,
                target=default_target,
                response=f"Playing {query} on Spotify.",
            )

    search_spotify_match = re.match(r"^(?:search|find)\s+(.+?)\s+(?:on|in)\s+spotify(?:\s+app)?$", normalized)
    if search_spotify_match:
        query = _normalize_spotify_query(search_spotify_match.group(1).strip())
        if query:
            return ActionResponse(
                action="open_app",
                app="spotify",
                text=query,
                target=default_target,
                response=f"Searching {query} on Spotify.",
            )

    if re.fullmatch(r"(?:open\s+)?whatsapp(?:\s+app)?\s+(?:in|on)\s+chrome", normalized):
        return ActionResponse(
            action="open_website",
            url="https://web.whatsapp.com",
            target=default_target,
            response="Opening WhatsApp in Chrome.",
        )

    open_app_match = re.match(r"^(open|launch|start)\s+(.+)$", normalized)
    if open_app_match:
        app_name = open_app_match.group(2).strip()
        # Handle combined commands like "open chrome and type youtube".
        app_name = re.split(r"\b(?:and|then)\b", app_name, maxsplit=1)[0].strip()
        app_name = re.sub(r"\bon\s+(?:pc|laptop|computer)\b", "", app_name).strip()
        app_name = re.sub(r"\bplease\b", "", app_name).strip()
        if app_name.startswith("app "):
            app_name = app_name[4:].strip()
        if app_name:
            return ActionResponse(
                action="open_app",
                app=app_name,
                target=default_target,
                response=f"Opening {app_name}.",
            )

    website_match = re.match(r"^(open|go to|visit)\s+([a-z0-9][a-z0-9\.-]+\.[a-z]{2,})(/\S*)?$", normalized)
    if website_match:
        host = website_match.group(2)
        path = website_match.group(3) or ""
        return ActionResponse(
            action="open_website",
            url=f"https://{host}{path}",
            target=default_target,
            response="Opening website.",
        )

    brightness_percent = re.search(r"\bbrightness\b.*?\b(\d{1,3})\s*%?\b", normalized)
    if brightness_percent:
        value = int(brightness_percent.group(1))
        if 0 <= value <= 100:
            return ActionResponse(
                action="brightness_control",
                level=str(value),
                target=default_target,
                response=f"Setting brightness to {value}%.",
            )

    volume_percent = re.search(r"\bvolume\b.*?\b(\d{1,3})\s*%?\b", normalized)
    if volume_percent:
        value = int(volume_percent.group(1))
        if 0 <= value <= 100:
            return ActionResponse(
                action="volume_control",
                level=str(value),
                target=default_target,
                response=f"Setting volume to {value}%.",
            )

    if "brightness" in normalized:
        on_off_level = _extract_on_off_direction(normalized)
        if on_off_level:
            return ActionResponse(
                action="brightness_control",
                level=on_off_level,
                target=default_target,
                response=f"Adjusting brightness {on_off_level}.",
            )
        for token in ("up", "down", "max", "min"):
            if token in normalized:
                return ActionResponse(
                    action="brightness_control",
                    level=token,
                    target=default_target,
                    response=f"Adjusting brightness {token}.",
                )

    if "volume" in normalized:
        on_off_level = _extract_on_off_direction(normalized)
        if on_off_level:
            return ActionResponse(
                action="volume_control",
                level=on_off_level,
                target=default_target,
                response=f"Adjusting volume {on_off_level}.",
            )
        for token in ("up", "down", "mute", "max"):
            if token in normalized:
                return ActionResponse(
                    action="volume_control",
                    level=token,
                    target=default_target,
                    response=f"Adjusting volume {token}.",
                )

    if re.search(r"\b(click|press|tap)\b.*\bplay\b.*\bbutton\b", normalized) or normalized in {
        "play",
        "pause",
        "resume",
    }:
        return ActionResponse(
            action="media_control",
            state="play_pause",
            target=default_target,
            response="Toggling play/pause.",
        )

    if "next song" in normalized or "next track" in normalized:
        return ActionResponse(
            action="media_control",
            state="next",
            target=default_target,
            response="Skipping to next track.",
        )

    if "previous song" in normalized or "previous track" in normalized:
        return ActionResponse(
            action="media_control",
            state="previous",
            target=default_target,
            response="Going to previous track.",
        )

    if normalized in {"next", "skip", "next song please"}:
        return ActionResponse(
            action="media_control",
            state="next",
            target=default_target,
            response="Skipping to next track.",
        )
    if normalized in {"previous", "back", "prev"}:
        return ActionResponse(
            action="media_control",
            state="previous",
            target=default_target,
            response="Going to previous track.",
        )

    referential_play = re.fullmatch(
        r"(?:play|put on|listen to)\s+(?:that|same|it)(?:\s+(?:song|track|music))?",
        normalized,
    )
    if referential_play:
        try:
            query = MEMORY_STORE.get_last_media_query("pc")
        except Exception:
            query = None
        if not query:
            return ActionResponse(
                action="media_control",
                state="play_pause",
                target=default_target,
                response="Toggling play/pause.",
            )
        return ActionResponse(
            action="open_app",
            app="spotify",
            text=query,
            target=default_target,
            response=f"Playing {query} on Spotify.",
        )

    if normalized.startswith(("play ", "put on ", "listen to ", "search ", "find ")):
        query = _extract_spotify_query(normalized)
        if query is None:
            query = "top hits"
        return ActionResponse(
            action="open_app",
            app="spotify",
            text=query,
            target=default_target,
            response=f"Playing {query} on Spotify.",
        )

    if "shutdown" in normalized:
        return ActionResponse(action="power_control", type="shutdown", target=default_target, response="Shutdown requested.")
    if "restart" in normalized:
        return ActionResponse(action="power_control", type="restart", target=default_target, response="Restart requested.")
    if "sleep" in normalized:
        return ActionResponse(action="power_control", type="sleep", target=default_target, response="Sleep requested.")

    if "whatsapp" in normalized and ("open" in normalized or normalized == "whatsapp"):
        return ActionResponse(action="open_app", app="whatsapp", target=default_target, response="Opening WhatsApp.")

    if "chrome" in normalized and ("open" in normalized or normalized == "chrome"):
        return ActionResponse(action="open_app", app="chrome", target=default_target, response="Opening chrome.")

    return None


def _normalize_action(action_obj: Dict[str, Any], default_target: str = "android") -> ActionResponse:
    action = str(action_obj.get("action", "")).strip().lower()
    response_text = _clean_response_text(action_obj.get("response"))
    if action not in ALLOWED_ACTIONS:
        return ActionResponse(
            action="type_text",
            text="I could not understand that command.",
            response="I could not understand that command.",
            target="android",
        )

    target = _extract_target(action_obj, default=default_target)

    if action == "open_app":
        app_name = str(action_obj.get("app", "")).strip().lower()
        post_text = _clean_slot_text(action_obj.get("text"))
        if not app_name:
            return ActionResponse(action="type_text", text="Please specify which app to open.", target=target)
        return ActionResponse(
            action="open_app",
            app=app_name,
            text=post_text,
            response=response_text or f"Opening {app_name}.",
            target=target,
        )

    if action == "close_app":
        app_name = str(action_obj.get("app", "")).strip().lower()
        if not app_name:
            return ActionResponse(action="type_text", text="Please specify which app to close.", target=target)
        return ActionResponse(
            action="close_app",
            app=app_name,
            response=response_text or f"Closing {app_name}.",
            target=target,
        )

    if action == "open_website":
        url = str(action_obj.get("url", "")).strip()
        if not url:
            return ActionResponse(action="type_text", text="Please specify the website.", target=target)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        return ActionResponse(
            action="open_website",
            url=url,
            response=response_text or "Opening website.",
            target=target,
        )

    if action == "call_contact":
        contact = str(action_obj.get("contact", "")).strip()
        phone = str(action_obj.get("phone", "")).strip()
        if not contact and not phone:
            return ActionResponse(action="type_text", text="Please tell me who to call.", target=target)

        normalized_phone = _normalize_phone(phone) if phone else None
        if not normalized_phone and contact:
            normalized_phone = _resolve_contact_phone(contact)

        if not normalized_phone:
            return ActionResponse(
                action="type_text",
                text=f"I could not find contact {contact or 'that person'}.",
                response=f"I could not find contact {contact or 'that person'}.",
                target=target,
            )

        return ActionResponse(
            action="call_contact",
            contact=contact or "Unknown",
            phone=normalized_phone,
            response=response_text or f"Calling {contact or normalized_phone}.",
            target=target,
        )

    if action == "send_whatsapp":
        contact = str(action_obj.get("contact", "")).strip()
        message = str(action_obj.get("message", action_obj.get("text", ""))).strip()
        phone = str(action_obj.get("phone", "")).strip()

        if not contact and not phone and not message:
            return ActionResponse(
                action="open_app",
                app="whatsapp",
                response=action_obj.get("response") or "Opening WhatsApp.",
                target=target,
            )

        normalized_phone = _normalize_phone(phone) if phone else None
        if not normalized_phone and contact:
            normalized_phone = _resolve_contact_phone(contact)

        if not normalized_phone:
            return ActionResponse(
                action="type_text",
                text=f"I could not find WhatsApp contact {contact or 'that person'}.",
                response=f"I could not find WhatsApp contact {contact or 'that person'}.",
                target=target,
            )

        return ActionResponse(
            action="send_whatsapp",
            contact=contact or "Unknown",
            phone=normalized_phone,
            message=message,
            response=response_text or f"Opening WhatsApp for {contact or normalized_phone}.",
            target=target,
        )

    if action == "volume_control":
        raw_level = str(action_obj.get("level", "")).strip().lower()
        percentage = _parse_percentage_level(raw_level)
        if raw_level not in {"up", "down", "mute", "max"} and percentage is None:
            return ActionResponse(
                action="type_text",
                text="Use volume up, down, mute, max, or a percentage like 50%.",
                target=target,
            )
        level = str(percentage) if percentage is not None else raw_level
        return ActionResponse(
            action="volume_control",
            level=level,
            target=target,
            response=response_text or f"Adjusting volume {level}.",
        )

    if action == "brightness_control":
        raw_level = str(action_obj.get("level", "")).strip().lower()
        percentage = _parse_percentage_level(raw_level)
        if raw_level not in {"up", "down", "max", "min"} and percentage is None:
            return ActionResponse(
                action="type_text",
                text="Use brightness up, down, max, min, or a percentage like 50%.",
                target=target,
            )
        level = str(percentage) if percentage is not None else raw_level
        return ActionResponse(
            action="brightness_control",
            level=level,
            target=target,
            response=response_text or f"Adjusting brightness {level}.",
        )

    if action == "power_control":
        power_type = str(action_obj.get("type", "")).strip().lower()
        if power_type not in {"shutdown", "restart", "sleep"}:
            return ActionResponse(action="type_text", text="Use shutdown, restart or sleep.", target=target)
        return ActionResponse(
            action="power_control",
            type=power_type,
            target=target,
            response=response_text or f"Power action {power_type} requested.",
        )

    if action == "mic_control":
        state = str(action_obj.get("state", "")).strip().lower()
        if state not in {"mute", "unmute"}:
            return ActionResponse(action="type_text", text="Use mic mute or unmute.", target=target)
        return ActionResponse(
            action="mic_control",
            state=state,
            target=target,
            response=response_text or f"Microphone {state}.",
        )

    if action == "media_control":
        media_state = str(action_obj.get("state", action_obj.get("type", ""))).strip().lower()
        if media_state in {"play", "pause", "play_pause", "toggle"}:
            normalized_state = "play_pause"
        elif media_state in {"next", "next_track"}:
            normalized_state = "next"
        elif media_state in {"previous", "prev", "previous_track"}:
            normalized_state = "previous"
        else:
            return ActionResponse(action="type_text", text="Use play, pause, next, or previous.", target=target)
        return ActionResponse(
            action="media_control",
            state=normalized_state,
            target=target,
            response=response_text or f"Media control {normalized_state}.",
        )

    if action == "network_control":
        network_type = str(action_obj.get("type", "")).strip().lower()
        state = str(action_obj.get("state", "")).strip().lower()
        if network_type not in {"wifi", "bluetooth"}:
            return ActionResponse(action="type_text", text="Use wifi or bluetooth.", target=target)
        if state not in {"on", "off", "open"}:
            return ActionResponse(action="type_text", text="Use on, off, or open.", target=target)
        return ActionResponse(
            action="network_control",
            type=network_type,
            state=state,
            target=target,
            response=response_text or f"Network control {network_type} {state}.",
        )

    if action == "system_control":
        control_type = str(action_obj.get("type", "")).strip().lower()
        level = str(action_obj.get("level", "")).strip().lower()
        state = str(action_obj.get("state", "")).strip().lower()

        if control_type == "volume":
            return _normalize_action(
                {"action": "volume_control", "level": level, "target": target, "response": response_text},
                default_target=target,
            )
        if control_type == "brightness":
            return _normalize_action(
                {"action": "brightness_control", "level": level, "target": target, "response": response_text},
                default_target=target,
            )
        if control_type == "mic":
            return _normalize_action(
                {"action": "mic_control", "state": state, "target": target, "response": response_text},
                default_target=target,
            )

        return ActionResponse(
            action="system_control",
            type=control_type,
            level=level or None,
            state=state or None,
            target=target,
            response=response_text or "System control command received.",
        )

    text = str(action_obj.get("text", "")).strip() or "I am not sure how to do that yet."
    return ActionResponse(
        action="type_text",
        text=text,
        response=response_text or text,
        target=target,
    )


def _maybe_execute_pc_control(action: ActionResponse) -> Optional[ActionResponse]:
    if action.target != "pc":
        return None

    pc_supported = {"volume_control", "brightness_control", "power_control", "mic_control", "media_control", "network_control"}
    if action.action not in pc_supported:
        return None

    result = execute_pc_system_action(action.model_dump())
    message = result.get("message", "PC action processed")
    return ActionResponse(action="type_text", text=message, response=message, target="android")


def _remember_and_return(client: str, user_text: str, action: ActionResponse) -> ActionResponse:
    try:
        MEMORY_STORE.remember_interaction(client=client, user_text=user_text, action=action.model_dump())
    except Exception as exc:
        logger.warning("Memory write failed: %s", exc)
    return action


@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "model": model_client.model,
        "host": HOST,
        "port": str(PORT),
    }


@app.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "api": {"up": True},
        "model": {
            "name": model_client.model,
            "api_url": model_client.api_url,
        },
        "memory": {
            "backend": MEMORY_STORE.backend,
            "configured": MEMORY_STORE.configured,
            "enabled": MEMORY_STORE.enabled,
            "last_error": MEMORY_STORE.last_error,
            "history_limit": JARVIS_MEMORY_HISTORY_LIMIT,
            "fact_limit": JARVIS_MEMORY_FACT_LIMIT,
        },
        "server": {"host": HOST, "port": PORT},
    }


@app.post("/command", response_model=ActionResponse)
def command(request: CommandRequest) -> ActionResponse:
    spoken_text = request.text.strip()
    spoken_text = re.sub(r"^(?:hey\s+)?jarvis\s+", "", spoken_text, flags=re.IGNORECASE).strip()
    client = (request.client or "").strip().lower() or "unknown"

    if not spoken_text:
        return _remember_and_return(
            client,
            "",
            ActionResponse(action="type_text", text="I did not hear anything.", target="android"),
        )

    # Desktop client already validates and strips wake word locally.
    if client == "pc":
        cleaned = spoken_text
    else:
        cleaned = _strip_wake_word(spoken_text)

    if not cleaned:
        return _remember_and_return(
            client,
            spoken_text,
            ActionResponse(action="type_text", text="Please say hey jarvis followed by a command.", target="android"),
        )

    logger.info("Received command: %s", spoken_text)
    logger.info("Command after wake-word strip: %s", cleaned)
    default_target = "pc" if client == "pc" else "android"
    confirmation_key = _confirmation_key(client, default_target)
    now_ts = time.time()

    def _finalize(action: ActionResponse) -> ActionResponse:
        return _remember_and_return(client=client, user_text=cleaned, action=action)

    def _finalize_with_pc(action: ActionResponse) -> ActionResponse:
        pc_result = _maybe_execute_pc_control(action)
        if pc_result is not None:
            logger.info("PC control executed: %s", pc_result.model_dump())
            return _finalize(pc_result)
        return _finalize(action)

    with _CONFIRMATION_LOCK:
        pending = PENDING_POWER_CONFIRMATIONS.get(confirmation_key)
        pending_system = PENDING_SYSTEM_CONTROL_CLARIFICATIONS.get(confirmation_key)
        if pending_system and float(pending_system.get("expires_at", 0.0)) <= now_ts:
            PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(confirmation_key, None)
            pending_system = None

    if pending:
        pending_type = pending["type"]
        pending_target = pending["target"]
        cleaned_lower = cleaned.strip().lower()

        if _is_power_confirmation(cleaned, pending_type):
            with _CONFIRMATION_LOCK:
                PENDING_POWER_CONFIRMATIONS.pop(confirmation_key, None)
            confirmed_action = ActionResponse(
                action="power_control",
                type=pending_type,
                target=pending_target,
                response=f"{pending_type.title()} confirmed.",
            )
            pc_result = _maybe_execute_pc_control(confirmed_action)
            if pc_result is not None:
                logger.info("PC power control executed after confirmation: %s", pc_result.model_dump())
                return _finalize(pc_result)
            return _finalize(confirmed_action)

        if cleaned_lower in {"cancel", "cancel it", "no", "stop", "abort"}:
            with _CONFIRMATION_LOCK:
                PENDING_POWER_CONFIRMATIONS.pop(confirmation_key, None)
            message = f"Cancelled {pending_type} request."
            return _finalize(ActionResponse(action="type_text", text=message, response=message, target=pending_target))

        # Any unrelated command should clear stale pending state.
        if pending_type not in cleaned_lower:
            with _CONFIRMATION_LOCK:
                PENDING_POWER_CONFIRMATIONS.pop(confirmation_key, None)
            pending = None
        else:
            message = f"Please confirm by saying 'confirm {pending_type}', or say cancel."
            return _finalize(ActionResponse(action="type_text", text=message, response=message, target=pending_target))

    if client == "pc" and pending_system:
        cleaned_lower = cleaned.strip().lower()
        if cleaned_lower in {"cancel", "cancel it", "no", "stop", "abort"}:
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(confirmation_key, None)
            return _finalize(
                ActionResponse(
                    action="type_text",
                    text="Cancelled. I did not change volume or brightness.",
                    response="Cancelled. I did not change volume or brightness.",
                    target=default_target,
                )
            )

        follow_scope = _extract_volume_brightness_scope(cleaned)
        if follow_scope in {"volume", "brightness"}:
            with _CONFIRMATION_LOCK:
                pending_payload = PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(confirmation_key, {})
            direction = str(pending_payload.get("direction", "up")).strip().lower()
            if direction not in {"up", "down"}:
                direction = "up"
            target = str(pending_payload.get("target", default_target)).strip().lower() or default_target
            return _finalize_with_pc(_build_system_control_action(follow_scope, direction, target))

        if follow_scope is None and _extract_adjust_direction(cleaned) is None:
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(confirmation_key, None)

    # For laptop client usage, prefer deterministic local parsing first so
    # common commands work even if the model is unavailable.
    if client == "pc":
        exact_level_action = _rule_based_action(cleaned, default_target=default_target)
        if (
            exact_level_action is not None
            and exact_level_action.action in {"volume_control", "brightness_control"}
            and str(exact_level_action.level or "").isdigit()
        ):
            return _finalize_with_pc(exact_level_action)

        ambiguous_direction = _extract_adjust_direction(cleaned)
        scope = _extract_volume_brightness_scope(cleaned)

        if ambiguous_direction and scope in {"volume", "brightness"}:
            return _finalize_with_pc(_build_system_control_action(scope, ambiguous_direction, default_target))

        if ambiguous_direction and scope == "both":
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS[confirmation_key] = {
                    "direction": ambiguous_direction,
                    "target": default_target,
                    "expires_at": time.time() + SYSTEM_CONTROL_CLARIFY_TTL_SECONDS,
                }
            return _finalize(
                ActionResponse(
                    action="type_text",
                    text="Do you want to change volume or brightness?",
                    response="Do you want to change volume or brightness?",
                    target=default_target,
                )
            )

        if ambiguous_direction and scope is None and _should_prompt_for_volume_brightness(cleaned):
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS[confirmation_key] = {
                    "direction": ambiguous_direction,
                    "target": default_target,
                    "expires_at": time.time() + SYSTEM_CONTROL_CLARIFY_TTL_SECONDS,
                }
            return _finalize(
                ActionResponse(
                    action="type_text",
                    text="Do you mean volume or brightness?",
                    response="Do you mean volume or brightness?",
                    target=default_target,
                )
            )

        local_action = _rule_based_action(cleaned, default_target=default_target)
        if local_action is not None:
            with _CONFIRMATION_LOCK:
                pending_local = PENDING_POWER_CONFIRMATIONS.get(confirmation_key)
                if pending_local:
                    cleaned_lower = cleaned.strip().lower()
                    pending_type_local = pending_local.get("type", "")
                    if (
                        cleaned_lower not in {"cancel", "no", "stop", "abort"}
                        and not _is_power_confirmation(cleaned, pending_type_local)
                        and pending_type_local not in cleaned_lower
                    ):
                        PENDING_POWER_CONFIRMATIONS.pop(confirmation_key, None)

            if local_action.action == "power_control" and local_action.type in {"shutdown", "restart"}:
                with _CONFIRMATION_LOCK:
                    PENDING_POWER_CONFIRMATIONS[confirmation_key] = {
                        "type": local_action.type,
                        "target": local_action.target or default_target,
                    }
                message = f"Please confirm by saying 'confirm {local_action.type}', or say cancel."
                return _finalize(ActionResponse(action="type_text", text=message, response=message, target=local_action.target))

            return _finalize_with_pc(local_action)

    if _is_close_command(cleaned):
        message = "Close will not shut down your PC. Say exit to stop Jarvis."
        return _finalize(ActionResponse(action="type_text", text=message, response=message, target=default_target))

    cleaned_lower = re.sub(r"\s+", " ", cleaned.strip().lower())
    if cleaned_lower in {"open", "start", "launch", "run"}:
        message = "Which app should I open?"
        return _finalize(ActionResponse(action="type_text", text=message, response=message, target=default_target))

    if (
        "my name" in cleaned_lower
        and (
            "what" in cleaned_lower
            or "know" in cleaned_lower
            or cleaned_lower in {"my name", "no my name"}
        )
    ):
        name = MEMORY_STORE.get_fact(client=client, fact_key="name")
        if name:
            msg = f"Your name is {name}."
        else:
            msg = "I do not know your name yet. So tell me your name."
        return _finalize(ActionResponse(action="type_text", text=msg, response=msg, target=default_target))

    if (
        "what did you open before" in cleaned_lower
        or "what did you open" in cleaned_lower
        or "which app did you open before" in cleaned_lower
        or "what app did you open before" in cleaned_lower
    ):
        last_app = MEMORY_STORE.get_last_opened_app(client=client)
        if last_app:
            msg = f"Last app I opened was {last_app}."
        else:
            msg = "I have no open-app history yet."
        return _finalize(ActionResponse(action="type_text", text=msg, response=msg, target=default_target))

    if (
        "what did i ask last time" in cleaned_lower
        or "what did i ask you last time" in cleaned_lower
        or "what did i ask u last time" in cleaned_lower
        or "what did i tell you last time" in cleaned_lower
        or "what did i tell u last time" in cleaned_lower
        or "what did i ask you to do" in cleaned_lower
        or "what did i ask u to do" in cleaned_lower
        or "what was my last command" in cleaned_lower
        or cleaned_lower == "last command"
    ):
        last_text = MEMORY_STORE.get_last_user_text(client=client)
        if last_text:
            msg = f"Your last command was: {last_text}."
        else:
            msg = "I do not have a previous command saved yet."
        return _finalize(ActionResponse(action="type_text", text=msg, response=msg, target=default_target))

    memory_context = MEMORY_STORE.build_context(client=client)

    if _is_conversational_query(cleaned_lower):
        try:
            response_text = model_client.generate_text(cleaned, memory_context=memory_context)
        except ModelError as exc:
            logger.error("Chat model error: %s", exc)
            response_text = "I cannot reach the local AI model right now."
        return _finalize(
            ActionResponse(
                action="type_text",
                text=response_text,
                response=response_text,
                target=default_target,
            )
        )

    try:
        action_obj = model_client.generate_action(
            cleaned,
            CONTACTS,
            default_target=default_target,
            memory_context=memory_context,
        )
    except ModelError as exc:
        logger.error("Model error: %s", exc)
        fallback = _rule_based_action(cleaned, default_target=default_target)
        if fallback is not None:
            logger.info("Using rule-based fallback action: %s", fallback.model_dump())
            return _finalize_with_pc(fallback)
        return _finalize(
            ActionResponse(
                action="type_text",
                text="I cannot reach the local AI model right now.",
                response="I cannot reach the local AI model right now.",
                target=default_target,
            )
        )

    normalized = _normalize_action(action_obj, default_target=default_target)

    if client == "pc" and normalized.action in {"volume_control", "brightness_control"}:
        scope = _extract_volume_brightness_scope(cleaned)
        if scope is None and _should_prompt_for_volume_brightness(cleaned):
            model_direction = str(normalized.level or "").strip().lower()
            if model_direction not in {"up", "down"}:
                model_direction = _extract_adjust_direction(cleaned) or "up"
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS[confirmation_key] = {
                    "direction": model_direction,
                    "target": default_target,
                    "expires_at": time.time() + SYSTEM_CONTROL_CLARIFY_TTL_SECONDS,
                }
            return _finalize(
                ActionResponse(
                    action="type_text",
                    text="Do you mean volume or brightness?",
                    response="Do you mean volume or brightness?",
                    target=default_target,
                )
            )

    if normalized.action == "type_text":
        cleaned_lower = cleaned.strip().lower()
        echoed = (normalized.text or "").strip().lower()
        if echoed == cleaned_lower or cleaned_lower in {"what", "huh", "ok", "hmm"}:
            message = "Please tell me a specific command, for example: open chrome, play music, or turn off wifi."
            return _finalize(ActionResponse(action="type_text", text=message, response=message, target=default_target))

    if normalized.action == "power_control" and normalized.type in {"shutdown", "restart"}:
        with _CONFIRMATION_LOCK:
            PENDING_POWER_CONFIRMATIONS[confirmation_key] = {
                "type": normalized.type,
                "target": normalized.target or default_target,
            }
        message = f"Please confirm by saying 'confirm {normalized.type}', or say cancel."
        return _finalize(ActionResponse(action="type_text", text=message, response=message, target=normalized.target))

    logger.info("Normalized action: %s", normalized.model_dump())
    return _finalize_with_pc(normalized)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)









