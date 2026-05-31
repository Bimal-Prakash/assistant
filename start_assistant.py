import argparse
import logging
import os
import queue
import re
import threading
import time
from typing import Optional

import requests
import uvicorn

# This launcher listens through the microphone and delegates command
# handling/execution to the Jarvis backend and PC client.
os.environ.setdefault("OLLAMA_MODEL", "gemma2:2b")
os.environ.setdefault("JARVIS_STT_ENGINE", "windows")
os.environ.setdefault("JARVIS_SKIP_INTERNAL_STT_IMPORTS", "1")
os.environ.setdefault("JARVIS_HUD", "0")
os.environ.setdefault("JARVIS_SPOKEN_FILLER", "0")

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None

from config import HOST, PORT
from laptop_assistant import LaptopJarvisClient


BACKEND_URL = os.getenv("JARVIS_BACKEND_URL", f"http://127.0.0.1:{PORT}")
WAKE_WORDS = ("hey jarvis", "hi jarvis", "jarvis")
IDLE_COMMANDS = {
    "stop",
    "exit",
    "shut up",
    "shutup",
    "go idle",
    "go to sleep",
    "sleep",
    "stop listening",
}
QUIT_COMMANDS = {"quit assistant", "close assistant", "shutdown assistant"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("assistant")


def wait_for_backend(url: str, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(f"{url.rstrip('/')}/status", timeout=2)
            if response.ok:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def run_backend() -> None:
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )


def split_wake_command(text: str) -> tuple[bool, str]:
    cleaned = " ".join((text or "").strip().split())
    lowered = cleaned.lower()
    for wake in WAKE_WORDS:
        if lowered.startswith(wake):
            return True, cleaned[len(wake) :].lstrip(" ,:-").strip()
    return False, cleaned


def is_idle_command(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    normalized = re.sub(r"\b(?:jarvis|jar|jervis|jarvish)\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,:-")
    if normalized in IDLE_COMMANDS:
        return True
    return normalized.startswith(("shut up", "shutup", "stop listening", "go idle", "go to sleep"))


def start_microphone_stt(command_queue: "queue.Queue[str]", energy_threshold: Optional[int]) -> object:
    if sr is None:
        raise RuntimeError("SpeechRecognition is not installed. Run: pip install -r requirements.txt")

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.5
    recognizer.non_speaking_duration = 0.4
    if energy_threshold is not None:
        recognizer.energy_threshold = energy_threshold
        recognizer.dynamic_energy_threshold = False

    microphone = sr.Microphone()
    log.info("Calibrating microphone for ambient noise...")
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

    def audio_callback(recognizer_obj: "sr.Recognizer", audio: "sr.AudioData") -> None:
        try:
            text = recognizer_obj.recognize_google(audio)
        except sr.UnknownValueError:
            return
        except sr.RequestError as exc:
            log.error("STT request failed: %s", exc)
            return

        if text:
            log.info("Heard: %s", text)
            command_queue.put(text)

    log.info("Microphone listener is ready. Say 'Jarvis' to activate.")
    return recognizer.listen_in_background(microphone, audio_callback)


def run_assistant(start_server: bool, text_mode: bool, energy_threshold: Optional[int]) -> None:
    if start_server:
        threading.Thread(target=run_backend, daemon=True).start()

    if not wait_for_backend(BACKEND_URL):
        raise RuntimeError(f"Backend did not become ready at {BACKEND_URL}")

    client = LaptopJarvisClient(BACKEND_URL, hud_enabled=False)
    client.speak("Assistant is ready")

    commands: "queue.Queue[str]" = queue.Queue()
    stop_listening = None
    active = False
    if not text_mode:
        stop_listening = start_microphone_stt(commands, energy_threshold)

    try:
        while True:
            if text_mode:
                command = input("Assistant > ").strip()
            else:
                command = commands.get()

            normalized = client._normalize_text_command(command)
            if normalized in QUIT_COMMANDS:
                client.speak("Stopping assistant")
                break
            if not normalized:
                continue

            woke, payload = split_wake_command(command)
            normalized_payload = client._normalize_text_command(payload)

            if woke:
                active = True
                if not normalized_payload:
                    continue
                command = payload
                normalized = normalized_payload
            elif not active:
                continue

            if is_idle_command(normalized):
                active = False
                continue

            try:
                action = client._resolve_action_for_command(command)
                client.execute_pc_action(action)
            except Exception as exc:
                log.exception("Command failed")
                client.speak(f"Command failed: {exc}")
    finally:
        if stop_listening is not None:
            stop_listening(wait_for_stop=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Windows assistant using microphone STT and Jarvis actions")
    parser.add_argument("--no-server", action="store_true", help="Do not start the FastAPI backend")
    parser.add_argument("--text", action="store_true", help="Use typed commands instead of microphone STT")
    parser.add_argument("--energy-threshold", type=int, default=None, help="Optional fixed microphone energy threshold")
    args = parser.parse_args()

    run_assistant(
        start_server=not args.no_server,
        text_mode=args.text,
        energy_threshold=args.energy_threshold,
    )


if __name__ == "__main__":
    main()
