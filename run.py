import argparse
import logging
import os
import queue
import re
import threading
import time
import uuid
from typing import Optional

import requests
# pyrefly: ignore [missing-import]
import uvicorn

# This launcher listens through the microphone and delegates command
# handling/execution to the Jarvis backend and PC client.

from pathlib import Path
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    try:
        for _raw_line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _raw_line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _value = _line.split("=", 1)
            _key, _value = _key.strip(), _value.strip().strip('"').strip("'")
            if _key and _key not in os.environ:
                os.environ[_key] = _value
    except Exception:
        pass

os.environ.setdefault("JARVIS_SKIP_INTERNAL_STT_IMPORTS", "1")
os.environ.setdefault("JARVIS_HUD", "0")
os.environ.setdefault("JARVIS_SPOKEN_FILLER", "0")

try:
    # pyrefly: ignore [missing-import]
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None

from core.config import HOST, PORT
from client.app import LaptopJarvisClient


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
        "server.app:app",
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


def start_microphone_stt(command_queue: "queue.Queue[str]", energy_threshold: Optional[int], pause_event: "threading.Event", client: LaptopJarvisClient) -> object:
    if sr is None:
        raise RuntimeError("SpeechRecognition is not installed. Run: pip install -r requirements.txt")

    running = [True]

    def audio_callback(recognizer_obj: "sr.Recognizer", audio: "sr.AudioData") -> None:
        for attempt in range(2):
            try:
                text = recognizer_obj.recognize_google(audio)
                if text:
                    log.info("Heard: %s", text)
                    command_queue.put(text)
                return
            except sr.UnknownValueError:
                return  # It was silence or unintelligible, don't retry
            except Exception as exc:
                if attempt == 0:
                    time.sleep(0.2)
                    continue
                log.error("Google STT failed: %s", exc)

    def resilient_listen():
        while running[0]:
            try:
                recognizer = sr.Recognizer()
                recognizer.pause_threshold = 1.2  # Increased from 0.5 to prevent cutting off adithyaponnu26
                recognizer.non_speaking_duration = 0.4
                if energy_threshold is not None:
                    recognizer.energy_threshold = energy_threshold
                    recognizer.dynamic_energy_threshold = False

                microphone = sr.Microphone()
                log.info("Calibrating microphone for ambient noise...")
                with microphone as source:
                    recognizer.adjust_for_ambient_noise(source, duration=1)

                log.info("Microphone listener is ready. Say 'Jarvis' to activate.")

                with microphone as source:
                    while running[0]:
                        if pause_event.is_set():
                            time.sleep(0.5)
                            continue
                        try:
                            audio = recognizer.listen(source, timeout=1, phrase_time_limit=None)
                            if running[0] and not pause_event.is_set():
                                threading.Thread(target=audio_callback, args=(recognizer, audio), daemon=True).start()
                        except sr.WaitTimeoutError:
                            pass
            except Exception as exc:
                log.error("Microphone disconnected or failed: %s. Retrying in 2 seconds...", exc)
                time.sleep(2.0)

    listener_thread = threading.Thread(target=resilient_listen, daemon=True)
    listener_thread.start()

    def stopper(wait_for_stop=False):
        running[0] = False
        if wait_for_stop:
            listener_thread.join()

    return stopper


def run_assistant(start_server: bool, text_mode: bool, energy_threshold: Optional[int]) -> None:
    if start_server:
        threading.Thread(target=run_backend, daemon=True).start()

    if not wait_for_backend(BACKEND_URL):
        raise RuntimeError(f"Backend did not become ready at {BACKEND_URL}")

    def prewarm_ollama():
        try:
            import requests
            from core.config import OLLAMA_API_URL, OLLAMA_MODEL
            logging.info(f"Pre-warming Ollama model {OLLAMA_MODEL} into VRAM...")
            requests.post(
                OLLAMA_API_URL, 
                json={
                    "model": OLLAMA_MODEL, 
                    "prompt": "hello", 
                    "stream": False, 
                    "keep_alive": "10m"
                }, 
                timeout=120
            )
            logging.info("Ollama model pre-warmed successfully. First command will be instant!")
        except Exception as e:
            logging.warning(f"Ollama pre-warm failed: {e}")
            
    threading.Thread(target=prewarm_ollama, daemon=True).start()

    client = LaptopJarvisClient(BACKEND_URL, hud_enabled=False)
    client.speak("Assistant is ready")

    commands: "queue.Queue[str]" = queue.Queue()
    stop_listening = None
    active = False
    pending_clarification = None
    # Session ID tracks a conversation — resets on each wake word activation
    client.session_id = str(uuid.uuid4())

    def check_abort() -> bool:
        for item in list(commands.queue):
            low = item.lower()
            if "stop" in low or "cancel" in low or "abort" in low:
                return True
        return False
    client._check_abort = check_abort

    pause_event = threading.Event()

    if not text_mode:
        stop_listening = start_microphone_stt(commands, energy_threshold, pause_event, client)

    try:
        while True:
            if text_mode:
                command = input("Assistant > ").strip()
            else:
                command = commands.get()
                
            # Benchmark telemetry
            import os, time
            os.environ["COMMAND_START_TIME"] = str(time.time())
            print(f"\n[Benchmark] Voice recognized: 0.00s")

            # Apply dynamic STT corrections from environment variables
            # Format in .env: JARVIS_STT_CORRECTIONS="vimal:bimal,pawan:pavan"
            stt_corrections_env = os.getenv("JARVIS_STT_CORRECTIONS", "")
            if stt_corrections_env:
                command_lower = command.lower()
                for pair in stt_corrections_env.split(','):
                    parts = pair.split(':')
                    if len(parts) == 2:
                        wrong, right = parts[0].strip(), parts[1].strip()
                        if wrong.lower() in command_lower:
                            command = command.replace(wrong.capitalize(), right.capitalize())
                            command = command.replace(wrong.lower(), right.lower())

            normalized = client._normalize_text_command(command)
            if normalized in QUIT_COMMANDS:
                client.speak("Stopping assistant")
                break
            if not normalized:
                continue

            woke, payload = split_wake_command(command)
            normalized_payload = client._normalize_text_command(payload)

            if text_mode or woke:
                active = True
                if woke:
                    # New wake word = new conversation session
                    client.session_id = str(uuid.uuid4())
                    if not normalized_payload:
                        continue
                    command = payload
                    normalized = normalized_payload
            elif not active:
                continue

            if is_idle_command(normalized):
                active = False
                pending_clarification = None
                continue

            # --- Conversational State Machine for Incomplete Commands ---
            cmd_lower = command.lower().strip()
            
            # If we asked a clarifying question last turn, prepend the verb!
            if pending_clarification:
                command = f"{pending_clarification} {command}"
                cmd_lower = command.lower().strip()
                pending_clarification = None
                
            # Intercept incomplete one-word commands instantly
            if cmd_lower in ["open", "close", "minimize", "minimise", "play", "call"]:
                pending_clarification = cmd_lower
                prompts = {
                    "open": "What would you like to open?",
                    "close": "What would you like to close?",
                    "minimize": "What would you like to minimize?",
                    "minimise": "What would you like to minimize?",
                    "play": "What would you like to play?",
                    "call": "Whom would you like to call?"
                }
                client.speak(prompts[cmd_lower])
                continue

            # --- Compound Command Splitter ---
            # Allows lightning fast system commands to execute immediately
            # while pushing the complex/agentic half to the LLM.
            cmds_to_run = [command]
            if cmd_lower.startswith(("open ", "close ", "minimize ", "minimise ", "play ", "call ")):
                import re
                match = re.split(r'\s+(?:and|then)\s+(ask|tell|introduce|search|read|write|close|open|play|pause|call|what|who|where|why|how)\b', command, maxsplit=1, flags=re.IGNORECASE)
                if len(match) == 3:
                    part1 = match[0].strip()
                    part2 = (match[1] + match[2]).strip()
                    # Prepend context to the second command so the LLM knows who "her/it" is!
                    part2_with_context = f"[Context: The user just ran the command '{part1}'] {part2}"
                    cmds_to_run = [part1, part2_with_context]

            for single_cmd in cmds_to_run:
                try:
                    try:
                        action = client._resolve_action_for_command(single_cmd)
                    except KeyboardInterrupt:
                        log.warning("Action resolution interrupted by user (Ctrl+C).")
                        client.speak("Action canceled.")
                        active = False
                        break
                        
                    result = client.execute_pc_action(action)
                    
                    if action.get("action") == "whatsapp_call":
                        if result and "canceled" in result.lower():
                            log.info("WhatsApp call was canceled.")
                        else:
                            log.info("WhatsApp call initiated. Pausing STT to prevent background transcribing.")
                            client.speak("Muting assistant microphone. Press Enter in the terminal to wake me up.")
                            pause_event.set()
                            input("\n>>> ON A CALL. Press Enter here to wake up Jarvis... <<<\n")
                            pause_event.clear()
                            client.speak("Microphone resumed.")
                            log.info("Resumed microphone STT.")
                            # Drain any residual commands from before the pause
                            while not commands.empty():
                                commands.get_nowait()
                            
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
