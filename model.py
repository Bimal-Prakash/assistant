import json
import logging
from json import JSONDecodeError
from typing import Any, Dict

import requests

from config import OLLAMA_API_URL, OLLAMA_KEEP_ALIVE_SECONDS, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

logger = logging.getLogger("jarvis.model")


class ModelError(Exception):
    pass


def _extract_json(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        raise JSONDecodeError("Empty model response", text, 0)

    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
        raise JSONDecodeError("Root JSON is not an object", text, 0)
    except JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except JSONDecodeError:
            continue

    raise JSONDecodeError("No JSON object found", text, 0)


def _build_prompt(user_text: str, contacts: Dict[str, str], default_target: str, memory_context: str = "") -> str:
    contact_names = ", ".join(sorted(contacts.keys())) if contacts else "none"
    return f"""
You are Jarvis's command router.
Return ONLY one valid JSON object. No markdown, no explanation, no prose.

Allowed actions:
open_app, close_app, open_website, call_contact, send_whatsapp, type_text,
system_control, volume_control, brightness_control, power_control, mic_control, media_control, network_control.

Strict output schema:
- open_app: {{"action":"open_app","app":"<app_name>","text":"<optional_text_to_type_or_search>","target":"android|pc","response":"<tts_text_optional>"}}
- close_app: {{"action":"close_app","app":"<app_name>","target":"android|pc","response":"<tts_text_optional>"}}
- open_website: {{"action":"open_website","url":"https://...","target":"android|pc","response":"<tts_text_optional>"}}
- call_contact: {{"action":"call_contact","contact":"<contact_name>","target":"android","response":"<tts_text_optional>"}}
- send_whatsapp: {{"action":"send_whatsapp","contact":"<contact_name>","message":"<message_optional>","target":"android","response":"<tts_text_optional>"}}
- type_text: {{"action":"type_text","text":"<plain_text_response>","target":"android|pc","response":"<tts_text_optional>"}}
- volume_control: {{"action":"volume_control","level":"up|down|mute|max","target":"android|pc","response":"<tts_text_optional>"}}
- brightness_control: {{"action":"brightness_control","level":"up|down|max|min|0-100","target":"android|pc","response":"<tts_text_optional>"}}
- power_control: {{"action":"power_control","type":"shutdown|restart|sleep","target":"android|pc","response":"<tts_text_optional>"}}
- mic_control: {{"action":"mic_control","state":"mute|unmute","target":"android|pc","response":"<tts_text_optional>"}}
- media_control: {{"action":"media_control","state":"play_pause|next|previous","target":"android|pc","response":"<tts_text_optional>"}}
- network_control: {{"action":"network_control","type":"wifi|bluetooth","state":"on|off|open","target":"android|pc","response":"<tts_text_optional>"}}
- system_control: {{"action":"system_control","type":"volume|brightness|power|mic","level":"<optional>","state":"<optional>","target":"android|pc","response":"<tts_text_optional>"}}

Rules:
1) Output must be strictly valid JSON.
2) Use only one action.
3) If request is unclear or unsupported, use type_text.
4) Default target to "{default_target}" unless user explicitly asks another device.
5) Use these known contacts when relevant: {contact_names}.
6) Never treat "close" as shutdown or restart. If user says only "close", return type_text asking what to close.
6a) Never map "close <anything>" (example: "close bluetooth", "close chrome") to power_control.
6b) Use power_control only when user explicitly says shutdown/restart/sleep intent.
7) If user asks for brightness percentage (for example 50%), return brightness_control with level as that numeric percentage string (for example "50"), not max.
8) If user says "open whatsapp" (without contact/message), prefer open_app with app "whatsapp" instead of send_whatsapp.
9) If user says "open <app> and type <text>", use open_app with app and text fields.
10) If user says "play <song> on spotify", use open_app with app "spotify" and text as the song/query.
11) Never output placeholder strings like "<tts_text_optional>" in response. Use plain natural text or omit response.
12) For "open spotify and play <song>" use open_app with app "spotify" and text set to the song.
13) For play/pause/next/previous media commands, use media_control.
14) If the user says "play song" without a track name, use media_control play_pause (do not emit placeholders like "<song>").
15) For wifi/bluetooth enable-disable commands, prefer network_control.
16) If user says brightness on/off, map to brightness_control level up/down respectively.
17) If user says volume on/off, map to volume_control level up/down respectively.

Memory context (may be empty):\n{memory_context or "none"}\n\nUser command: {user_text}
""".strip()


def _build_chat_prompt(user_text: str, memory_context: str = "") -> str:
    return f"""
You are Jarvis, a concise Windows voice assistant.
Answer the user naturally in 1-2 short sentences.
Do not use markdown, bullets, or code blocks.
If memory context is relevant, use it. Otherwise ignore it.

Memory context:
{memory_context or "none"}

User: {user_text}
Jarvis:
""".strip()


class OllamaCommandModel:
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        api_url: str = OLLAMA_API_URL,
        timeout_seconds: int = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.keep_alive_seconds = OLLAMA_KEEP_ALIVE_SECONDS

    def generate_action(
        self,
        user_text: str,
        contacts: Dict[str, str],
        default_target: str = "android",
        memory_context: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": _build_prompt(
                user_text=user_text,
                contacts=contacts,
                default_target=default_target,
                memory_context=memory_context,
            ),
            "stream": False,
            "keep_alive": self.keep_alive_seconds,
            "options": {"temperature": 0},
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ModelError(f"Failed to reach Ollama API at {self.api_url}: {exc}") from exc

        if response.status_code != 200:
            raise ModelError(
                f"Ollama API returned status {response.status_code}: {response.text[:300]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ModelError("Ollama response was not valid JSON") from exc

        raw_text = str(body.get("response", "")).strip()
        logger.info("Raw model output: %s", raw_text)

        try:
            return _extract_json(raw_text)
        except JSONDecodeError as exc:
            raise ModelError(f"Model did not return strict JSON: {exc}") from exc

    def generate_text(self, user_text: str, memory_context: str = "") -> str:
        payload = {
            "model": self.model,
            "prompt": _build_chat_prompt(user_text=user_text, memory_context=memory_context),
            "stream": False,
            "keep_alive": self.keep_alive_seconds,
            "options": {"temperature": 0.7, "num_predict": 96},
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ModelError(f"Failed to reach Ollama API at {self.api_url}: {exc}") from exc

        if response.status_code != 200:
            raise ModelError(
                f"Ollama API returned status {response.status_code}: {response.text[:300]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ModelError("Ollama response was not valid JSON") from exc

        text = str(body.get("response", "")).strip()
        text = text.replace("Jarvis:", "").strip()
        return text or "I do not have a good answer for that yet."



