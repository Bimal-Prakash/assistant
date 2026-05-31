import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_file()

HOST = os.getenv("JARVIS_HOST", "0.0.0.0")
PORT = int(os.getenv("JARVIS_PORT", "8000"))

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2:2b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
OLLAMA_KEEP_ALIVE_SECONDS = int(os.getenv("OLLAMA_KEEP_ALIVE_SECONDS", "0"))

CONTACTS_FILE = BASE_DIR / "contacts.json"

WAKE_WORDS = (
    "hey jarvis",
)

ALLOWED_ACTIONS = {
    "open_app",
    "close_app",
    "open_website",
    "call_contact",
    "send_whatsapp",
    "type_text",
    "system_control",
    "network_control",
    "media_control",
    "volume_control",
    "brightness_control",
    "power_control",
    "mic_control",
}


JARVIS_MEMORY_DATABASE_URL = os.getenv("JARVIS_MEMORY_DATABASE_URL", "")
JARVIS_MEMORY_HISTORY_LIMIT = int(os.getenv("JARVIS_MEMORY_HISTORY_LIMIT", "12"))
JARVIS_MEMORY_FACT_LIMIT = int(os.getenv("JARVIS_MEMORY_FACT_LIMIT", "20"))




