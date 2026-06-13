import os
from pathlib import Path

def _load_dotenv_file() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass

_load_dotenv_file()

BACKEND_URL = os.getenv("JARVIS_BACKEND_URL", "http://127.0.0.1:8000")
TERMINAL_MINIMAL = os.getenv("JARVIS_TERMINAL_MINIMAL", "1").strip().lower() not in {"0", "false", "no"}
ALWAYS_ON_COMMAND_STRICT = os.getenv("JARVIS_ALWAYS_ON_COMMAND_STRICT", "1").strip().lower() not in {"0", "false", "no"}
SKIP_INTERNAL_STT_IMPORTS = os.getenv("JARVIS_SKIP_INTERNAL_STT_IMPORTS", "0").strip().lower() in {"1", "true", "yes"}

WAKE_WORDS = ("hey jarvis",)
WAKE_WORD_VARIANTS = ("hi jarvis", "hey jervis", "hey jarvish", "hey jarvees", "hay jarvis")
WAKE_LEAD_TOKENS = {"hey", "hi", "hay", "hello"}
ACCENT_TOLERANT_MODE = os.getenv("JARVIS_ACCENT_TOLERANT", "1").strip().lower() not in {"0", "false", "no"}
WAKE_FUZZY_THRESHOLD = float(os.getenv("JARVIS_WAKE_FUZZY_THRESHOLD", "0.86"))
WAKE_MIN_CONFIDENCE = float(os.getenv("JARVIS_WAKE_MIN_CONFIDENCE", "0.45"))
COMMAND_MIN_CONFIDENCE = float(os.getenv("JARVIS_COMMAND_MIN_CONFIDENCE", "0.32"))

APP_ALIASES = {
    "google chrome": "chrome",
    "chrome browser": "chrome",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "file explorer": "explorer",
    "windows explorer": "explorer",
    "calculator app": "calculator",
}
APP_URI_MAP = {
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "clock": "ms-clock:",
}
WEB_ALIASES = {
    "facebook": "https://www.facebook.com",
    "fb": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "insta": "https://www.instagram.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "gemini": "https://gemini.google.com",
    "copilot": "https://copilot.microsoft.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "spankbang": "https://spankbang.com"
}

LOW_CONFIDENCE_THRESHOLD = 0.68
LOW_CONFIDENCE_RISKY_ACTIONS = {"power_control", "network_control", "close_app", "mic_control"}
TEXT_MODE_COMMANDS = {"text", "text mode", "switch to text", "text input"}
VOICE_MODE_COMMANDS = {"voice", "voice mode", "switch to voice", "voice input"}
YES_COMMANDS = {"yes", "yeah", "yep", "confirm", "ok", "okay", "do it"}
NO_COMMANDS = {"no", "nope", "cancel", "stop", "abort"}
ALIAS_FILE_NAME = "app_aliases.json"
WAKE_ACTIVE_SECONDS = int(os.getenv("JARVIS_WAKE_ACTIVE_SECONDS", "7"))
LISTEN_MAX_SECONDS = int(os.getenv("JARVIS_LISTEN_MAX_SECONDS", "8"))
START_APPS_CACHE_TTL_SECONDS = int(os.getenv("JARVIS_START_APPS_CACHE_TTL_SECONDS", "120"))
SPOKEN_FILLER_ENABLED = os.getenv("JARVIS_SPOKEN_FILLER", "0").strip().lower() not in {"0", "false", "no"}
EDGE_TTS_VOICE = os.getenv("JARVIS_EDGE_TTS_VOICE", "en-IN-NeerjaNeural")

HUD_ENABLED_DEFAULT = os.getenv("JARVIS_HUD", "0").strip().lower() not in {"0", "false", "no"}

STT_ACCENT_GATE_ENABLED = os.getenv("JARVIS_STT_ACCENT_GATE", "1").strip().lower() not in {"0", "false", "no"}
STT_NOISE_GATE_ENABLED = os.getenv("JARVIS_STT_NOISE_GATE", "0").strip().lower() not in {"0", "false", "no"}
STT_FUZZY_GATE_ENABLED = os.getenv("JARVIS_STT_FUZZY_GATE", "1").strip().lower() not in {"0", "false", "no"}
STT_NOISE_MIN_RMS = float(os.getenv("JARVIS_STT_NOISE_MIN_RMS", "70"))
STT_NOISE_SPEECH_RATIO = float(os.getenv("JARVIS_STT_NOISE_SPEECH_RATIO", "1.6"))
STT_NOISE_MIN_SPEECH_FRAC = float(os.getenv("JARVIS_STT_NOISE_MIN_SPEECH_FRAC", "0.015"))
STT_FUZZY_TOKEN_THRESHOLD = float(os.getenv("JARVIS_STT_FUZZY_TOKEN_THRESHOLD", "0.86"))
STT_MAX_ALTERNATIVES = int(os.getenv("JARVIS_STT_MAX_ALTERNATIVES", "5"))
STT_PROFILE_FILE_NAME = os.getenv("JARVIS_STT_PROFILE_FILE", "stt_calibration_profiles.json")
STT_CALIBRATION_ENABLED = os.getenv("JARVIS_STT_CALIBRATION", "0").strip().lower() not in {"0", "false", "no"}
STT_AGC_ENABLED = os.getenv("JARVIS_STT_AGC", "1").strip().lower() not in {"0", "false", "no"}
STT_AGC_TARGET_RMS = float(os.getenv("JARVIS_STT_AGC_TARGET_RMS", "1100"))
STT_AGC_MIN_GAIN = float(os.getenv("JARVIS_STT_AGC_MIN_GAIN", "0.85"))
STT_AGC_MAX_GAIN = float(os.getenv("JARVIS_STT_AGC_MAX_GAIN", "2.20"))
STT_CALIBRATION_MIN_UTTERANCE_FRAMES = int(os.getenv("JARVIS_STT_CALIBRATION_MIN_FRAMES", "35"))
MIC_DEVICE_INDEX_OVERRIDE_RAW = os.getenv("JARVIS_MIC_DEVICE_INDEX", "auto").strip().lower()
STT_ENGINE = os.getenv("JARVIS_STT_ENGINE", "windows").strip().lower()
PUSH_TO_TALK_SPACE_ENABLED = os.getenv("JARVIS_PUSH_TO_TALK_SPACE", "1").strip().lower() not in {"0", "false", "no"}
PUSH_TO_TALK_MAX_SECONDS = int(os.getenv("JARVIS_PUSH_TO_TALK_MAX_SECONDS", "8"))
PUSH_TO_TALK_POLL_SECONDS = float(os.getenv("JARVIS_PUSH_TO_TALK_POLL_SECONDS", "0.015"))
WINDOWS_STT_TIMEOUT_SECONDS = int(os.getenv("JARVIS_WINDOWS_STT_TIMEOUT_SECONDS", str(LISTEN_MAX_SECONDS)))
WINDOWS_STT_MIN_CONFIDENCE = float(os.getenv("JARVIS_WINDOWS_STT_MIN_CONFIDENCE", "0.30"))
WINDOWS_TEXT_IDLE_SECONDS = float(os.getenv("JARVIS_WINDOWS_TEXT_IDLE_SECONDS", "1.2"))
WINDOWS_TEXT_MAX_WAIT_SECONDS = int(os.getenv("JARVIS_WINDOWS_TEXT_MAX_WAIT_SECONDS", "20"))
STT_FUZZY_VOCAB = {
    "hey", "hi", "jarvis", "open", "close", "start", "launch", "run", "play", "search", "find",
    "spotify", "whatsapp", "chrome", "youtube", "vscode", "notepad", "calculator", "explorer",
    "volume", "brightness", "wifi", "bluetooth", "mute", "unmute", "shutdown", "restart", "sleep",
    "song", "music", "track", "playlist", "next", "previous", "pause", "resume", "terminal", "by"
}

COMMAND_KEYWORDS = {
    "open", "close", "start", "launch", "run", "play", "search", "find", "type", "send", "call",
    "turn", "set", "increase", "decrease", "volume", "brightness", "wifi", "bluetooth", "mute", "unmute",
    "shutdown", "restart", "sleep", "chrome", "spotify", "whatsapp", "youtube", "vscode", "notepad",
    "calculator", "explorer", "terminal", "time", "date", "battery", "next", "previous", "pause", "resume"
}
