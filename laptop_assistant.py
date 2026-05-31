import argparse
import difflib
import ctypes
import io
import json
import math
import os
import queue
import re
import shutil
import tempfile
import subprocess
import struct
import threading
import time
from urllib.parse import quote_plus
from datetime import datetime
import webbrowser
import wave

try:
    import msvcrt  # type: ignore
except Exception:
    msvcrt = None
from typing import Any, Dict, List, Optional

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_local_env() -> None:
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
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


_load_local_env()

TERMINAL_MINIMAL = os.getenv("JARVIS_TERMINAL_MINIMAL", "1").strip().lower() not in {"0", "false", "no"}
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1" if TERMINAL_MINIMAL else "0")

ALWAYS_ON_COMMAND_STRICT = os.getenv("JARVIS_ALWAYS_ON_COMMAND_STRICT", "1").strip().lower() not in {"0", "false", "no"}
SKIP_INTERNAL_STT_IMPORTS = os.getenv("JARVIS_SKIP_INTERNAL_STT_IMPORTS", "0").strip().lower() in {"1", "true", "yes"}

try:
    import numpy as np  # type: ignore
except Exception:
    np = None

if SKIP_INTERNAL_STT_IMPORTS:
    WhisperModel = None
else:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        WhisperModel = None

if SKIP_INTERNAL_STT_IMPORTS:
    snapshot_download = None
else:
    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except Exception:
        snapshot_download = None

try:
    import pyaudio  # type: ignore
except Exception:
    pyaudio = None

try:
    import pyttsx3  # type: ignore
except Exception:
    pyttsx3 = None

if SKIP_INTERNAL_STT_IMPORTS:
    Model = None
    KaldiRecognizer = None
    pvrecorder = None
    SetLogLevel = None
else:
    try:
        from vosk import Model, KaldiRecognizer, SetLogLevel  # type: ignore
        import pvrecorder  # type: ignore
    except Exception:
        Model = None
        KaldiRecognizer = None
        pvrecorder = None
        SetLogLevel = None

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

try:
    import tkinter as tk  # type: ignore
except Exception:
    tk = None

try:
    import winsound  # type: ignore
except Exception:
    winsound = None


BACKEND_URL = os.getenv("JARVIS_BACKEND_URL", "http://127.0.0.1:8000")
WAKE_WORDS = ("hey jarvis",)
WAKE_WORD_VARIANTS = ("hi jarvis", "hey jervis", "hey jarvish", "hey jarvees", "hay jarvis")
WAKE_LEAD_TOKENS = {"hey", "hi", "hay", "hello"}
ACCENT_TOLERANT_MODE = os.getenv("JARVIS_ACCENT_TOLERANT", "1").strip().lower() not in {"0", "false", "no"}
WAKE_FUZZY_THRESHOLD = float(os.getenv("JARVIS_WAKE_FUZZY_THRESHOLD", "0.86"))
WAKE_MIN_CONFIDENCE = float(os.getenv("JARVIS_WAKE_MIN_CONFIDENCE", "0.45"))
COMMAND_MIN_CONFIDENCE = float(os.getenv("JARVIS_COMMAND_MIN_CONFIDENCE", "0.32"))
VOSK_SAMPLE_RATE = 16000
VOSK_MODEL_CANDIDATES = [
    m.strip()
    for m in os.getenv(
        "JARVIS_VOSK_MODEL_CANDIDATES",
        "vosk-model-en-in-0.5,vosk-model-en-us-0.22,vosk-model-small-en-in-0.4,vosk-model-small-en-us-0.15",
    ).split(",")
    if m.strip()
]
VOSK_HINT_PHRASES = [
    "hey jarvis",
    "open",
    "close",
    "start",
    "launch",
    "settings",
    "chrome",
    "notepad",
    "calculator",
    "explorer",
    "vscode",
    "spotify",
    "whatsapp",
    "terminal",
]
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
STT_ENGINE = os.getenv("JARVIS_STT_ENGINE", "whisper").strip().lower()
VOSK_PARTIAL_INTERVAL_FRAMES = int(os.getenv("JARVIS_VOSK_PARTIAL_INTERVAL_FRAMES", "2"))
VOSK_END_SILENCE_FRAMES = int(os.getenv("JARVIS_VOSK_END_SILENCE_FRAMES", "12"))
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
ASSEMBLYAI_UPLOAD_URL = os.getenv("ASSEMBLYAI_UPLOAD_URL", "https://api.assemblyai.com/v2/upload").strip()
ASSEMBLYAI_TRANSCRIPT_URL = os.getenv("ASSEMBLYAI_TRANSCRIPT_URL", "https://api.assemblyai.com/v2/transcript").strip()
ASSEMBLYAI_TIMEOUT_SECONDS = int(os.getenv("ASSEMBLYAI_TIMEOUT_SECONDS", "35"))
ASSEMBLYAI_POLL_SECONDS = float(os.getenv("ASSEMBLYAI_POLL_SECONDS", "0.8"))
WHISPER_MODEL_NAME = os.getenv("JARVIS_WHISPER_MODEL", "distil-medium.en").strip()
WHISPER_MODEL_REPO = os.getenv("JARVIS_WHISPER_MODEL_REPO", "").strip()
WHISPER_DEVICE = os.getenv("JARVIS_WHISPER_DEVICE", "cpu").strip()
WHISPER_VERIFY_ENABLED = os.getenv("JARVIS_WHISPER_VERIFY_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
WHISPER_VERIFY_MODEL_NAME = os.getenv("JARVIS_WHISPER_VERIFY_MODEL", "distil-large-v3").strip()
WHISPER_VERIFY_MODEL_REPO = os.getenv("JARVIS_WHISPER_VERIFY_MODEL_REPO", "Systran/faster-distil-whisper-large-v3").strip()
WHISPER_VERIFY_FOR_SHORT = os.getenv("JARVIS_WHISPER_VERIFY_FOR_SHORT", "1").strip().lower() not in {"0", "false", "no"}
WHISPER_COMPUTE_TYPE = os.getenv("JARVIS_WHISPER_COMPUTE_TYPE", "int8").strip()
WHISPER_SAMPLE_RATE = 16000
WHISPER_CHUNK = int(os.getenv("JARVIS_WHISPER_CHUNK", "512"))
WHISPER_SILENCE_RMS = float(os.getenv("JARVIS_WHISPER_SILENCE_RMS", "75"))
WHISPER_END_SILENCE_FRAMES = int(os.getenv("JARVIS_WHISPER_END_SILENCE_FRAMES", "22"))
WHISPER_MIN_SPEECH_FRAMES = int(os.getenv("JARVIS_WHISPER_MIN_SPEECH_FRAMES", "4"))
WHISPER_VAD_FILTER = os.getenv("JARVIS_WHISPER_VAD_FILTER", "0").strip().lower() in {"1", "true", "yes"}
WHISPER_STREAM_DECODE_INTERVAL_FRAMES = int(os.getenv("JARVIS_WHISPER_STREAM_DECODE_INTERVAL_FRAMES", "3"))
WHISPER_STREAM_MIN_STABLE_PARTIALS = int(os.getenv("JARVIS_WHISPER_STREAM_MIN_STABLE_PARTIALS", "2"))
WHISPER_STREAM_MIN_COMMAND_CHARS = int(os.getenv("JARVIS_WHISPER_STREAM_MIN_COMMAND_CHARS", "6"))
WHISPER_STREAM_MAX_WINDOW_FRAMES = int(os.getenv("JARVIS_WHISPER_STREAM_MAX_WINDOW_FRAMES", "72"))
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
    "song", "music", "track", "playlist", "next", "previous", "pause", "resume", "terminal",
    "juice", "wrld", "world", "robbery", "by"
}

COMMAND_KEYWORDS = {
    "open", "close", "start", "launch", "run", "play", "search", "find", "type", "send", "call",
    "turn", "set", "increase", "decrease", "volume", "brightness", "wifi", "bluetooth", "mute", "unmute",
    "shutdown", "restart", "sleep", "chrome", "spotify", "whatsapp", "youtube", "vscode", "notepad",
    "calculator", "explorer", "terminal", "time", "date", "battery", "next", "previous", "pause", "resume"
}


class StatusHud:
    def __init__(self) -> None:
        self.enabled = False
        self._closed = False
        self._queue: "queue.Queue[Dict[str, str]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        if tk is None:
            return

        self._thread = threading.Thread(target=self._run_ui, daemon=True)
        self._thread.start()
        self.enabled = True

    def _run_ui(self) -> None:
        if tk is None:
            return

        root = tk.Tk()
        root.title("Jarvis HUD")
        root.geometry("420x130+20+20")
        root.attributes("-topmost", True)
        root.configure(bg="#111111")

        transcript_var = tk.StringVar(value="Heard: ...")
        intent_var = tk.StringVar(value="Intent: ...")
        action_var = tk.StringVar(value="Action: ...")

        for var in (transcript_var, intent_var, action_var):
            label = tk.Label(root, textvariable=var, anchor="w", justify="left", fg="#f0f0f0", bg="#111111", font=("Consolas", 10))
            label.pack(fill="x", padx=10, pady=3)

        def poll() -> None:
            while True:
                try:
                    payload = self._queue.get_nowait()
                except queue.Empty:
                    break
                if payload.get("__cmd") == "shutdown":
                    root.quit()
                    return
                transcript_var.set(f"Heard: {payload.get('heard', '...')}")
                intent_var.set(f"Intent: {payload.get('intent', '...')}")
                action_var.set(f"Action: {payload.get('action', '...')}")
            root.after(120, poll)

        poll()
        root.mainloop()
        try:
            root.destroy()
        except Exception:
            pass

    def update(self, heard: str = "", intent: str = "", action: str = "") -> None:
        if not self.enabled or self._closed:
            return
        self._queue.put({"heard": heard, "intent": intent, "action": action})

    def close(self) -> None:
        if not self.enabled or self._closed:
            return
        self._closed = True
        try:
            self._queue.put({"__cmd": "shutdown"})
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.enabled = False

class LaptopJarvisClient:
    def __init__(self, backend_url: str, hud_enabled: bool = True) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.tts = None
        self.tts_mode = "none"
        self.edge_tts_cli = shutil.which("edge-tts") or shutil.which("edge-tts.exe")
        if not self.edge_tts_cli:
            edge_tts_candidate = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                ".venv",
                "Scripts",
                "edge-tts.exe",
            )
            if os.path.isfile(edge_tts_candidate):
                self.edge_tts_cli = edge_tts_candidate
        self._init_tts_engine()

        # Initialize Vosk model
        self.vosk_model = None
        if SetLogLevel:
            try:
                SetLogLevel(-1)
            except Exception:
                pass
        self.kaldi_recognizer = None
        self.vosk_model_name = ""
        if Model and KaldiRecognizer and STT_ENGINE == "vosk":
            self._load_vosk_model()
        
        self._start_apps_cache: Optional[List[Dict[str, str]]] = None
        self._start_apps_cache_ts = 0.0
        self._start_menu_shortcuts_cache: Optional[List[Dict[str, str]]] = None
        self.input_mode = "voice"
        self.windows_native_text_mode = False
        self.last_recognition_confidence: Optional[float] = None
        self.pending_alias_suggestion: Optional[Dict[str, str]] = None
        self.pending_action_confirmation: Optional[Dict[str, Any]] = None
        self.hud = StatusHud() if hud_enabled else None
        self._alias_file_path = os.path.join(os.path.dirname(__file__), ALIAS_FILE_NAME)
        self.dynamic_aliases = self._load_dynamic_aliases()
        self.wake_active_until = 0.0
        self.backend_reachable: Optional[bool] = None
        self._last_backend_check_ts = 0.0
        self._noise_floor_rms = STT_NOISE_MIN_RMS
        self._mic_device_index_override: Optional[int] = None
        if MIC_DEVICE_INDEX_OVERRIDE_RAW not in {"", "auto", "default", "-1"}:
            try:
                self._mic_device_index_override = int(MIC_DEVICE_INDEX_OVERRIDE_RAW)
            except Exception:
                self._mic_device_index_override = None
        self._active_mic_device_index: Optional[int] = None
        self._consecutive_empty_captures = 0
        self.stt_engine = STT_ENGINE
        if self.stt_engine == "assemblyai" and not ASSEMBLYAI_API_KEY:
            print("Warning: ASSEMBLYAI_API_KEY is missing; falling back to Whisper/Vosk STT.")
            self.stt_engine = "whisper"
        if self.stt_engine not in {"whisper", "vosk", "assemblyai", "windows"}:
            print(f"Warning: Unknown STT engine '{self.stt_engine}', falling back to whisper.")
            self.stt_engine = "whisper"
        if self.stt_engine == "windows":
            self.input_mode = "text"
            self.windows_native_text_mode = True
        self.whisper_model = None
        self.whisper_verify_model = None
        self._init_whisper_model()
        self._input_gain = 1.0
        self._stt_profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), STT_PROFILE_FILE_NAME)
        self._machine_name = (os.getenv("COMPUTERNAME") or "pc").strip().lower() or "pc"
        self._stt_profile_cache: Dict[str, Dict[str, Any]] = {}
        self._load_stt_calibration_profile()
        self._apply_stt_calibration_profile()

    def _infer_whisper_repo_id(self, model_name: str) -> str:
        model = (model_name or "").strip()
        if not model:
            return ""
        if "/" in model:
            return model
        if model.startswith("distil-"):
            suffix = model[len("distil-"):]
            return f"Systran/faster-distil-whisper-{suffix}"
        return f"Systran/faster-whisper-{model}"

    def _resolve_model_source(self, requested_model: str, requested_repo: str = "") -> str:
        requested = (requested_model or "").strip()
        if requested and os.path.isdir(requested):
            return requested

        repo_id = (requested_repo or "").strip() or self._infer_whisper_repo_id(requested)
        if not repo_id or snapshot_download is None:
            return requested

        safe_repo = re.sub(r"[^A-Za-z0-9._-]+", "_", repo_id.replace("/", "--"))
        local_dir = os.path.join(BASE_DIR, "models", safe_repo)
        os.makedirs(local_dir, exist_ok=True)

        if os.path.isfile(os.path.join(local_dir, "model.bin")) and os.path.isfile(os.path.join(local_dir, "config.json")):
            return local_dir

        try:
            kwargs = {
                "repo_id": repo_id,
                "local_dir": local_dir,
            }
            resolved = snapshot_download(**kwargs)
            return str(resolved)
        except Exception as exc:
            print(f"Warning: local Whisper model sync failed ({exc}); trying default loader path.")
            return requested

    def _resolve_whisper_model_source(self) -> str:
        return self._resolve_model_source(WHISPER_MODEL_NAME, WHISPER_MODEL_REPO)

    def _ensure_vosk_model_loaded(self) -> None:
        if self.vosk_model is None and Model and KaldiRecognizer:
            self._load_vosk_model()

    def _init_whisper_model(self) -> None:
        if self.stt_engine != "whisper":
            return
        if WhisperModel is None:
            print("Warning: faster-whisper is unavailable in this environment; falling back to Vosk STT.")
            self.stt_engine = "vosk"
            self._ensure_vosk_model_loaded()
            return
        try:
            model_source = self._resolve_whisper_model_source()
            try:
                self.whisper_model = WhisperModel(
                    model_source,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                    local_files_only=bool(model_source and os.path.isdir(model_source)),
                )
            except TypeError:
                self.whisper_model = WhisperModel(
                    model_source,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                )
            print(f"Whisper model loaded successfully: {model_source} ({WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE})")
            self._init_whisper_verify_model()
        except Exception as exc:
            print(f"Warning: Whisper model init failed ({exc}); falling back to Vosk STT.")
            self.whisper_model = None
            self.stt_engine = "vosk"
            self._ensure_vosk_model_loaded()

    def _init_whisper_verify_model(self) -> None:
        if self.stt_engine != "whisper" or not WHISPER_VERIFY_ENABLED:
            return
        if WhisperModel is None or self.whisper_model is None:
            return

        verify_name = (WHISPER_VERIFY_MODEL_NAME or "").strip()
        if not verify_name:
            return

        if verify_name == WHISPER_MODEL_NAME and (WHISPER_VERIFY_MODEL_REPO or "").strip() == (WHISPER_MODEL_REPO or "").strip():
            self.whisper_verify_model = self.whisper_model
            return

        try:
            verify_source = self._resolve_model_source(verify_name, WHISPER_VERIFY_MODEL_REPO)
            try:
                self.whisper_verify_model = WhisperModel(
                    verify_source,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                    local_files_only=bool(verify_source and os.path.isdir(verify_source)),
                )
            except TypeError:
                self.whisper_verify_model = WhisperModel(
                    verify_source,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                )
            if not TERMINAL_MINIMAL:
                print(f"Whisper verify model loaded: {verify_source} ({WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE})")
        except Exception as exc:
            self.whisper_verify_model = None
            if not TERMINAL_MINIMAL:
                print(f"Warning: Whisper verify model init failed ({exc}).")

    def _listen_with_windows_speech(self) -> Optional[str]:
        timeout_seconds = max(2, WINDOWS_STT_TIMEOUT_SECONDS)
        ps_script = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$engine = $null
try {
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
} catch {
    try {
        $culture = [System.Globalization.CultureInfo]::CurrentUICulture
        $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
    } catch {
        $engine = $null
    }
}

if ($engine -eq $null) {
    $recognizers = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
    if ($recognizers -and $recognizers.Count -gt 0) {
        $culture = $recognizers[0].Culture
        $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
    }
}

if ($engine -eq $null) {
    Write-Output 'ERROR||Could not initialize Windows speech recognizer'
    exit 2
}

try {
    $engine.SetInputToDefaultAudioDevice()
    $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
    $result = $engine.Recognize([TimeSpan]::FromSeconds(__TIMEOUT_SECONDS__))
    if ($result -ne $null) {
        $text = ($result.Text -replace '\\s+', ' ').Trim()
        if ($text) {
            $confidence = [math]::Round($result.Confidence, 3)
            Write-Output ($text + '||' + $confidence)
        }
    }
} catch {
    Write-Output ('ERROR||' + $_.Exception.Message)
    exit 3
} finally {
    try { $engine.Dispose() } catch {}
}
"""
        ps_script = ps_script.replace("__TIMEOUT_SECONDS__", str(timeout_seconds))

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 5,
            )
        except Exception as exc:
            if not TERMINAL_MINIMAL:
                print(f"[windows stt error] {exc}")
            return None

        output = (proc.stdout or "").strip()
        if not output:
            if proc.returncode != 0 and not TERMINAL_MINIMAL:
                stderr_text = (proc.stderr or "").strip()
                if stderr_text:
                    print(f"[windows stt error] {stderr_text}")
            return ""

        line = output.splitlines()[-1].strip()
        if not line:
            return ""

        if line.startswith("ERROR||"):
            if not TERMINAL_MINIMAL:
                print(f"[windows stt error] {line.split('||', 1)[1].strip()}")
            return ""

        heard_text = line
        confidence = None
        if "||" in line:
            heard_text, confidence_raw = line.rsplit("||", 1)
            heard_text = heard_text.strip()
            try:
                confidence = float(confidence_raw.strip())
            except Exception:
                confidence = None

        if confidence is not None:
            self.last_recognition_confidence = confidence
            if confidence < WINDOWS_STT_MIN_CONFIDENCE:
                return ""

        return heard_text

    def _init_tts_engine(self) -> None:
        # Default offline-first mode. Use edge only if explicitly requested.
        preferred = os.getenv("JARVIS_TTS_ENGINE", "pyttsx3").strip().lower()

        if preferred in {"pyttsx3", "auto"} and pyttsx3:
            try:
                self.tts = pyttsx3.init()
                self.tts_mode = "pyttsx3"
                return
            except Exception:
                self.tts = None

        if preferred in {"edge", "edge-tts"} and self.edge_tts_cli:
            self.tts_mode = "edge"
            return

        self.tts_mode = "none"

    def _play_chime(self, kind: str = "wake") -> None:
        if winsound is None:
            return
        try:
            if kind == "thinking":
                winsound.MessageBeep(winsound.MB_ICONQUESTION)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def _speak_with_edge_tts(self, text: str) -> bool:
        if not self.edge_tts_cli:
            return False

        fd, wav_path = tempfile.mkstemp(prefix="jarvis_tts_", suffix=".wav")
        os.close(fd)
        try:
            cmd = [
                self.edge_tts_cli,
                "--text",
                text,
                "--voice",
                EDGE_TTS_VOICE,
                "--write-media",
                wav_path,
                "--format",
                "riff-24khz-16bit-mono-pcm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=20)
            if result.returncode != 0:
                return False
            if winsound is not None:
                winsound.PlaySound(wav_path, winsound.SND_FILENAME)
                return True
            return False
        except Exception:
            return False
        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass

    def _load_vosk_model(self) -> None:
        requested = os.getenv("JARVIS_VOSK_MODEL", "auto").strip()
        allow_download = os.getenv("JARVIS_VOSK_ALLOW_DOWNLOAD", "0").strip().lower() in {"1", "true", "yes"}

        candidates: List[str] = []
        if requested and requested.lower() != "auto":
            candidates.append(requested)
        candidates.extend([m for m in VOSK_MODEL_CANDIDATES if m not in candidates])

        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_home = os.path.expanduser("~")
        cache_root = os.path.join(user_home, ".cache", "vosk")

        local_paths: List[str] = []
        for item in candidates:
            if os.path.isdir(item):
                local_paths.append(item)
                continue

            for candidate_path in (
                os.path.join(base_dir, item),
                os.path.join(cache_root, item),
            ):
                if os.path.isdir(candidate_path) and candidate_path not in local_paths:
                    local_paths.append(candidate_path)

        # 1) Offline/local-first loading.
        for model_path in local_paths:
            try:
                self.vosk_model = Model(model_path)
                self.vosk_model_name = model_path
                self._reset_recognizer()
                print(f"Vosk model loaded successfully: {self.vosk_model_name}")
                return
            except Exception:
                continue

        # 2) Optional online/model-name loading only when explicitly enabled.
        if allow_download:
            for candidate in candidates:
                try:
                    self.vosk_model = Model(model_name=candidate)
                    self.vosk_model_name = candidate
                    self._reset_recognizer()
                    print(f"Vosk model loaded successfully: {self.vosk_model_name}")
                    return
                except Exception:
                    continue

        print("Warning: Could not initialize any configured Vosk model.")
        print("Place a model folder locally or set JARVIS_VOSK_ALLOW_DOWNLOAD=1.")
        self.vosk_model = None
        self.kaldi_recognizer = None

    def _create_kaldi_recognizer(self) -> Optional[Any]:
        if not self.vosk_model or not KaldiRecognizer:
            return None

        # Maximum-accuracy mode: do not constrain with grammar.
        recognizer = KaldiRecognizer(self.vosk_model, VOSK_SAMPLE_RATE)

        try:
            recognizer.SetWords(True)
        except Exception:
            pass
        try:
            recognizer.SetPartialWords(True)
        except Exception:
            pass
        try:
            recognizer.SetMaxAlternatives(max(1, STT_MAX_ALTERNATIVES))
        except Exception:
            pass
        return recognizer

    def _stt_profile_key(self) -> str:
        model_label = os.path.basename(self.vosk_model_name.strip()) if self.vosk_model_name else "default-model"
        return f"{self._machine_name}:{model_label}"

    def _load_stt_calibration_profile(self) -> None:
        if not STT_CALIBRATION_ENABLED:
            return
        if not os.path.exists(self._stt_profile_path):
            self._stt_profile_cache = {}
            return
        try:
            with open(self._stt_profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._stt_profile_cache = data if isinstance(data, dict) else {}
        except Exception:
            self._stt_profile_cache = {}

    def _save_stt_calibration_profile(self) -> None:
        if not STT_CALIBRATION_ENABLED:
            return
        try:
            with open(self._stt_profile_path, "w", encoding="utf-8") as f:
                json.dump(self._stt_profile_cache, f, indent=2)
        except Exception:
            pass

    def _apply_stt_calibration_profile(self) -> None:
        if not STT_CALIBRATION_ENABLED:
            return
        profile = self._stt_profile_cache.get(self._stt_profile_key(), {})
        if not isinstance(profile, dict):
            return

        noise_floor = profile.get("noise_floor_rms")
        if isinstance(noise_floor, (int, float)):
            self._noise_floor_rms = max(STT_NOISE_MIN_RMS, float(noise_floor))

        input_gain = profile.get("input_gain")
        if isinstance(input_gain, (int, float)):
            self._input_gain = min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, float(input_gain)))

    def _persist_stt_calibration(self, noise_floor_rms: float, speech_rms: float, input_gain: float, frames: int) -> None:
        if not STT_CALIBRATION_ENABLED:
            return
        if frames < STT_CALIBRATION_MIN_UTTERANCE_FRAMES:
            return

        key = self._stt_profile_key()
        prev = self._stt_profile_cache.get(key, {})
        if not isinstance(prev, dict):
            prev = {}

        prev_count = int(prev.get("samples", 0)) if isinstance(prev.get("samples", 0), int) else 0
        new_count = prev_count + 1

        prev_noise = float(prev.get("noise_floor_rms", STT_NOISE_MIN_RMS))
        prev_speech = float(prev.get("speech_rms", max(STT_AGC_TARGET_RMS, STT_NOISE_MIN_RMS)))
        prev_gain = float(prev.get("input_gain", 1.0))

        merged_noise = (prev_noise * prev_count + float(noise_floor_rms)) / float(new_count)
        merged_speech = (prev_speech * prev_count + float(speech_rms)) / float(new_count)
        merged_gain = (prev_gain * prev_count + float(input_gain)) / float(new_count)

        self._stt_profile_cache[key] = {
            "samples": new_count,
            "noise_floor_rms": max(STT_NOISE_MIN_RMS, merged_noise),
            "speech_rms": max(STT_NOISE_MIN_RMS, merged_speech),
            "input_gain": min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, merged_gain)),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_stt_calibration_profile()

    def _apply_input_gain(self, frame: List[int]) -> List[int]:
        if not frame:
            return frame
        if not STT_AGC_ENABLED:
            return frame

        rms = self._frame_rms(frame)
        if rms < 20:
            return frame

        desired_gain = STT_AGC_TARGET_RMS / max(rms, 1.0)
        desired_gain = min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, desired_gain))
        self._input_gain = (self._input_gain * 0.85) + (desired_gain * 0.15)
        gain = min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, self._input_gain))

        adjusted: List[int] = []
        for sample in frame:
            value = int(sample * gain)
            if value > 32767:
                value = 32767
            elif value < -32768:
                value = -32768
            adjusted.append(value)
        return adjusted

    def _available_input_devices(self) -> List[str]:
        if pvrecorder is None:
            return []
        try:
            devices = pvrecorder.PvRecorder.get_available_devices()
            return list(devices) if isinstance(devices, list) else []
        except Exception:
            return []

    def _open_recorder_with_fallback(self) -> Any:
        if pvrecorder is None:
            raise RuntimeError("PvRecorder is unavailable")

        devices = self._available_input_devices()
        candidates: List[int] = []

        if self._mic_device_index_override is not None:
            candidates.append(self._mic_device_index_override)
        elif self._active_mic_device_index is not None:
            candidates.append(self._active_mic_device_index)
            if self._active_mic_device_index != -1:
                candidates.append(-1)
        else:
            # On some Windows setups after unplugging headsets, explicit input index is more reliable than -1 default routing.
            if devices:
                candidates.append(0)
            candidates.append(-1)

        scan_limit = min(len(devices), 8)
        for idx in range(scan_limit):
            if idx not in candidates:
                candidates.append(idx)

        last_exc: Optional[Exception] = None
        for idx in candidates:
            try:
                recorder = pvrecorder.PvRecorder(device_index=idx, frame_length=512)
                recorder.start()
                if idx != self._active_mic_device_index:
                    label = "default" if idx == -1 else (devices[idx] if 0 <= idx < len(devices) else f"device {idx}")
                    if not TERMINAL_MINIMAL:
                        print(f"   Using mic input: {label}")
                self._active_mic_device_index = idx
                return recorder
            except Exception as exc:
                last_exc = exc
                continue

        raise RuntimeError(f"Could not open any microphone input: {last_exc}")

    def _maybe_rotate_mic_device(self) -> None:
        if self._mic_device_index_override is not None:
            return
        devices = self._available_input_devices()
        if not devices or len(devices) <= 1:
            return

        if self._active_mic_device_index is None or self._active_mic_device_index < 0:
            self._active_mic_device_index = 0
            return

        self._active_mic_device_index = (self._active_mic_device_index + 1) % len(devices)
        try:
            if not TERMINAL_MINIMAL:
                print(f"   Rotating mic input to: {devices[self._active_mic_device_index]}")
        except Exception:
            pass

    def _update_hud(self, heard: str = "", intent: str = "", action: str = "") -> None:
        try:
            if self.hud:
                self.hud.update(heard=heard, intent=intent, action=action)
        except Exception:
            pass

    @staticmethod
    def _normalize_text_command(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @staticmethod
    def _is_unknown_transcript(text: str) -> bool:
        normalized = LaptopJarvisClient._normalize_text_command(text)
        if not normalized:
            return True
        normalized = normalized.replace("[", "").replace("]", "")
        return normalized in {"unk", "unknown"} or normalized.startswith("unk ") or " unk" in normalized

    @staticmethod
    def _normalize_wake_probe(text: str) -> str:
        normalized = LaptopJarvisClient._normalize_text_command(text)
        if not normalized:
            return ""

        substitutions = {
            "jarvish": "jarvis",
            "jarvees": "jarvis",
            "jarviss": "jarvis",
            "jervis": "jarvis",
            "dervis": "jarvis",
            "jarvice": "jarvis",
            "jarbis": "jarvis",
            "he jarvis": "hey jarvis",
            "hi jarvish": "hi jarvis",
            "hey jarviss": "hey jarvis",
        }
        for src, dst in substitutions.items():
            normalized = re.sub(rf"\b{re.escape(src)}\b", dst, normalized)

        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    @staticmethod
    def _has_wake_prefix_text(text: str) -> bool:
        normalized = LaptopJarvisClient._normalize_wake_probe(text)
        if not normalized:
            return False

        if normalized == "jarvis" or normalized.startswith("jarvis "):
            return True

        wake_candidates = [LaptopJarvisClient._normalize_wake_probe(w) for w in (list(WAKE_WORDS) + list(WAKE_WORD_VARIANTS))]
        for wake in wake_candidates:
            if wake and normalized.startswith(wake):
                return True

        if not ACCENT_TOLERANT_MODE:
            return False

        words = normalized.split()
        if len(words) < 2:
            return False

        if words[0] not in WAKE_LEAD_TOKENS:
            return False

        probe_values = [" ".join(words[:2])]
        if len(words) >= 3:
            probe_values.append(" ".join(words[:3]))

        for probe in probe_values:
            # Reject fuzzy wake when transcript does not even resemble "jarvis" token.
            if not any(token in probe for token in ("jar", "jarv", "jerv")):
                continue
            for wake in wake_candidates:
                if wake and difflib.SequenceMatcher(None, probe, wake).ratio() >= WAKE_FUZZY_THRESHOLD:
                    return True
        return False

    def _is_wake_only_text(self, text: str) -> bool:
        return self._has_wake_prefix_text(text) and not self.strip_wake_word(text)

    def _reset_recognizer(self) -> None:
        if not self.kaldi_recognizer:
            self.kaldi_recognizer = self._create_kaldi_recognizer()
            return
        try:
            self.kaldi_recognizer.Reset()
        except Exception:
            self.kaldi_recognizer = self._create_kaldi_recognizer()

    def _extract_confidence(self, result_obj: Dict[str, Any]) -> Optional[float]:
        words = result_obj.get("result")
        confidences: List[float] = []
        if isinstance(words, list):
            for item in words:
                if not isinstance(item, dict):
                    continue
                value = item.get("conf")
                if isinstance(value, (float, int)):
                    confidences.append(float(value))

        if confidences:
            return sum(confidences) / len(confidences)

        direct_conf = result_obj.get("conf")
        if isinstance(direct_conf, (float, int)):
            return float(direct_conf)

        fallback_text = str(result_obj.get("text", "") or result_obj.get("partial", "")).strip()
        if fallback_text:
            # Fallback confidence for models without word-level conf output.
            return 0.62
        return None

    @staticmethod
    def _is_yes_response(text: str) -> bool:
        return LaptopJarvisClient._normalize_text_command(text) in YES_COMMANDS

    @staticmethod
    def _is_no_response(text: str) -> bool:
        return LaptopJarvisClient._normalize_text_command(text) in NO_COMMANDS

    def _is_risky_action(self, action: Dict[str, Any]) -> bool:
        action_name = str(action.get("action", "")).strip().lower()
        return action_name in LOW_CONFIDENCE_RISKY_ACTIONS

    def _should_gate_low_confidence(self, action: Dict[str, Any]) -> bool:
        if not self._is_risky_action(action):
            return False
        confidence = self.last_recognition_confidence
        return confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD

    def _load_dynamic_aliases(self) -> Dict[str, str]:
        if not os.path.exists(self._alias_file_path):
            return {}
        try:
            with open(self._alias_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            aliases: Dict[str, str] = {}
            for k, v in data.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    continue
                key = self._normalize_text_command(k)
                value = self._normalize_text_command(v)
                if key and value:
                    aliases[key] = value
            return aliases
        except Exception:
            return {}

    def _save_dynamic_aliases(self) -> None:
        try:
            with open(self._alias_file_path, "w", encoding="utf-8") as f:
                json.dump(self.dynamic_aliases, f, indent=2)
        except Exception:
            pass

    def _suggest_app_name(self, raw_name: str) -> Optional[str]:
        normalized = self._normalize_text_command(raw_name)
        if not normalized:
            return None

        candidates = set(APP_URI_MAP.keys()) | set(APP_ALIASES.values()) | set(APP_ALIASES.keys())
        candidates.update({"chrome", "notepad", "calculator", "explorer", "vscode", "terminal", "cmd", "powershell", "spotify", "whatsapp"})

        try:
            for app in self._get_start_apps():
                name = self._normalize_text_command(str(app.get("Name", "")))
                if name:
                    candidates.add(name)
        except Exception:
            pass

        try:
            for shortcut in self._get_start_menu_shortcuts():
                name = self._normalize_text_command(str(shortcut.get("name", "")))
                if name:
                    candidates.add(name)
        except Exception:
            pass

        if not candidates:
            return None

        matches = difflib.get_close_matches(normalized, sorted(candidates), n=1, cutoff=0.72)
        return matches[0] if matches else None

    def _accent_normalize_command(self, command: str) -> str:
        normalized = self._normalize_text_command(command)
        if not normalized:
            return command

        fixes = {
            "what's app": "whatsapp",
            "whats app": "whatsapp",
            "what's up": "whatsapp",
            "whats up": "whatsapp",
            "wats up": "whatsapp",
            "whatsup": "whatsapp",
            "whatsapp app": "whatsapp",
            "spotty fi": "spotify",
            "spoti fy": "spotify",
            "you tube": "youtube",
            "u tube": "youtube",
            "youtbe": "youtube",
            "yutube": "youtube",
            "yotube": "youtube",
            "yooutube": "youtube",
            "vs code": "vscode",
            "crome": "chrome",
            "chorme": "chrome",
            "chomre": "chrome",
            "chrom": "chrome",
            "crewm": "chrome",
            "crew": "chrome",
            "comb": "chrome",
            "groom": "chrome",
            "grome": "chrome",
        }
        for src, dst in fixes.items():
            normalized = re.sub(rf"\b{re.escape(src)}\b", dst, normalized)

        normalized = re.sub(r"\bit\s+open\s+", "open ", normalized)
        normalized = re.sub(r"\bopen\s+youtube\s+in\s+chrome\b", "open https://www.youtube.com", normalized)
        normalized = re.sub(r"\b(?:open|start|launch|run)\s+youtube\b", "open https://www.youtube.com", normalized)
        normalized = re.sub(r"\b(?:open|start|launch|run)\s+crew\b", "open chrome", normalized)

        if re.fullmatch(r"(?:open\s+)?whatsapp(?:\s+app)?\s+(?:in|on)\s+chrome", normalized):
            return "open https://web.whatsapp.com"
        if re.fullmatch(r"open\s+whatsapp(?:\s+app)?", normalized):
            return "open whatsapp"

        open_match = re.match(r"^(open|start|launch|run)\s+(.+)$", normalized)
        if open_match:
            verb = open_match.group(1)
            app_raw = open_match.group(2).strip()
            suggestion = self._suggest_app_name(app_raw)
            if suggestion and suggestion != app_raw:
                normalized = f"{verb} {suggestion}"

        return normalized

    def _frame_rms(self, frame: List[int]) -> float:
        if not frame:
            return 0.0
        power = sum(float(sample) * float(sample) for sample in frame) / float(len(frame))
        return math.sqrt(power)

    @staticmethod
    def _collapse_repeated_words(text: str) -> str:
        return re.sub(r"\b(\w+)(?:\s+\1){1,}\b", r"\1", text)

    def _accent_gate_text(self, text: str) -> str:
        normalized = self._normalize_text_command(text)
        fixes = {
            "played": "play",
            "plaid": "play",
            "plaid": "play",
            "use world": "juice wrld",
            "jews world": "juice wrld",
            "juice world": "juice wrld",
            "roberry": "robbery",
            "robary": "robbery",
            "spotty fi": "spotify",
            "spoti fy": "spotify",
            "what's app": "whatsapp",
            "whats app": "whatsapp",
            "you tube": "youtube",
            "vs code": "vscode",
            "crome": "chrome",
            "chorme": "chrome",
            "jarvish": "jarvis",
            "jervis": "jarvis",
            "dervis": "jarvis",
        }
        for src, dst in fixes.items():
            normalized = re.sub(rf"\b{re.escape(src)}\b", dst, normalized)

        normalized = re.sub(r"^(?:please\s+)?played\s+", "play ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
        return normalized

    def _fuzzy_gate_text(self, text: str) -> str:
        tokens = text.split()
        if not tokens:
            return text

        corrected: List[str] = []
        for token in tokens:
            base = re.sub(r"[^a-z]", "", token.lower())
            if len(base) < 3 or base in STT_FUZZY_VOCAB:
                corrected.append(token)
                continue

            match = difflib.get_close_matches(base, sorted(STT_FUZZY_VOCAB), n=1, cutoff=STT_FUZZY_TOKEN_THRESHOLD)
            if match:
                replacement = match[0]
                corrected.append(replacement)
            else:
                corrected.append(token)

        return " ".join(corrected)

    def _semantic_normalize_command(self, text: str) -> str:
        normalized = self._normalize_text_command(text)
        if not normalized:
            return ""

        normalized = re.sub(r"^(?:please\s+)?(?:can you|could you|would you|kindly)\s+", "", normalized)
        normalized = re.sub(r"\bplease\b", "", normalized)
        normalized = re.sub(r"\bswitch\s+on\b", "turn on", normalized)
        normalized = re.sub(r"\bswitch\s+off\b", "turn off", normalized)
        normalized = re.sub(r"\bset\s+the\s+", "set ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
        return normalized

    def _command_likelihood_score(self, text: str) -> float:
        normalized = self._normalize_text_command(text)
        if not normalized:
            return -1.0

        tokens = [t for t in normalized.split() if t]
        if not tokens:
            return -1.0

        keyword_hits = sum(1 for t in tokens if t in COMMAND_KEYWORDS)
        keyword_ratio = keyword_hits / float(max(1, len(tokens)))

        pattern_bonus = 0.0
        if re.match(r"^(open|close|start|launch|run|play|search|find|send|call|turn|set)\b", normalized):
            pattern_bonus += 0.35
        if re.search(r"\b(on|off|up|down|next|previous|mute|unmute)\b", normalized):
            pattern_bonus += 0.2
        if self._has_wake_prefix_text(normalized):
            pattern_bonus += 0.35

        short_noise_penalty = 0.0
        short_tokens = sum(1 for t in tokens if len(t) <= 2)
        if len(tokens) >= 3 and short_tokens / float(len(tokens)) > 0.5:
            short_noise_penalty = 0.2

        return (keyword_ratio * 1.2) + pattern_bonus - short_noise_penalty

    def _select_best_stt_candidate(
        self,
        result_obj: Optional[Dict[str, Any]],
        best_partial: str,
    ) ->tuple[str, Optional[float]]:
        candidates: List[Dict[str, Any]] = []

        if isinstance(result_obj, dict):
            alt = result_obj.get("alternatives")
            if isinstance(alt, list):
                for item in alt:
                    if not isinstance(item, dict):
                        continue
                    text_val = self._normalize_text_command(str(item.get("text", "")))
                    if not text_val:
                        continue
                    conf_val = item.get("confidence")
                    confidence = float(conf_val) if isinstance(conf_val, (int, float)) else None
                    candidates.append({"text": text_val, "confidence": confidence})

            main_text = self._normalize_text_command(str(result_obj.get("text", "")))
            if main_text:
                candidates.append({"text": main_text, "confidence": self._extract_confidence(result_obj)})

        partial_text = self._normalize_text_command(best_partial)
        if partial_text:
            candidates.append({"text": partial_text, "confidence": None})

        if not candidates:
            return "", None

        best_text = ""
        best_conf: Optional[float] = None
        best_score = -999.0

        for candidate in candidates:
            ctext = candidate["text"]
            cconf = candidate.get("confidence")
            conf_score = cconf if isinstance(cconf, (int, float)) else 0.45
            likelihood = self._command_likelihood_score(ctext)
            total = (conf_score * 1.25) + likelihood
            if total > best_score:
                best_score = total
                best_text = ctext
                best_conf = float(cconf) if isinstance(cconf, (int, float)) else None

        return best_text, best_conf

    def _apply_stt_gates(
        self,
        raw_text: str,
        confidence: Optional[float],
        avg_rms: float,
        speech_energy_frames: int,
        total_frames: int,
    ) -> str:
        text = self._normalize_text_command(raw_text)
        if not text:
            return ""

        if STT_NOISE_GATE_ENABLED:
            speech_ratio = float(speech_energy_frames) / float(max(1, total_frames))
            wake_like = self._has_wake_prefix_text(text) or "jarvis" in text
            if not wake_like:
                if avg_rms < STT_NOISE_MIN_RMS and (confidence is None or confidence < 0.55):
                    print(f"Noise gate rejected transcript (avg_rms={avg_rms:.1f}).")
                    return ""
                if speech_ratio < STT_NOISE_MIN_SPEECH_FRAC and (confidence is None or confidence < 0.60):
                    print(f"Noise gate rejected transcript (speech_ratio={speech_ratio:.2f}).")
                    return ""

        text = self._collapse_repeated_words(text)

        if STT_ACCENT_GATE_ENABLED:
            text = self._accent_gate_text(text)

        if STT_FUZZY_GATE_ENABLED:
            text = self._fuzzy_gate_text(text)

        text = self._semantic_normalize_command(text)
        text = re.sub(r"\s+", " ", text).strip(" ,.-")
        return text

    def speak(self, text: str) -> None:
        if not text:
            return
        print(f"Jarvis: {text}")
        self._update_hud(action=text)

        if self.tts_mode == "edge":
            if self._speak_with_edge_tts(text):
                return

        if self.tts_mode == "pyttsx3" and self.tts:
            try:
                self.tts.say(text)
                self.tts.runAndWait()
            except Exception:
                pass

    def _pyaudio_input_device_index(self, pa: Any) -> Optional[int]:
        if self._mic_device_index_override is not None:
            return self._mic_device_index_override
        try:
            default_idx = pa.get_default_input_device_info().get("index")
            return int(default_idx)
        except Exception:
            pass
        try:
            count = int(pa.get_device_count())
            for i in range(count):
                info = pa.get_device_info_by_index(i)
                if int(info.get("maxInputChannels", 0)) > 0:
                    return i
        except Exception:
            pass
        return None

    @staticmethod
    def _is_space_pressed() -> bool:
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x20) & 0x8000)
        except Exception:
            return False

    @staticmethod
    def _wait_until_space_pressed() -> None:
        while True:
            if LaptopJarvisClient._is_space_pressed():
                return
            time.sleep(max(0.005, PUSH_TO_TALK_POLL_SECONDS))

    @staticmethod
    def _rms_from_pcm16(chunk: bytes) -> float:
        if not chunk:
            return 0.0
        samples = struct.unpack("<%dh" % (len(chunk) // 2), chunk)
        if not samples:
            return 0.0
        power = sum(float(s) * float(s) for s in samples) / float(len(samples))
        return math.sqrt(power)

    @staticmethod
    def _pcm16_to_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
        if not pcm:
            return b""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        return buf.getvalue()

    def _transcribe_with_assemblyai(self, pcm: bytes) -> str:
        if not ASSEMBLYAI_API_KEY or not pcm:
            return ""

        wav_payload = self._pcm16_to_wav_bytes(pcm, WHISPER_SAMPLE_RATE)
        if not wav_payload:
            return ""

        auth_headers = {"authorization": ASSEMBLYAI_API_KEY}
        try:
            upload_resp = requests.post(
                ASSEMBLYAI_UPLOAD_URL,
                headers={**auth_headers, "content-type": "application/octet-stream"},
                data=wav_payload,
                timeout=ASSEMBLYAI_TIMEOUT_SECONDS,
            )
            upload_resp.raise_for_status()
            upload_url = str(upload_resp.json().get("upload_url", "")).strip()
            if not upload_url:
                return ""

            create_resp = requests.post(
                ASSEMBLYAI_TRANSCRIPT_URL,
                headers={**auth_headers, "content-type": "application/json"},
                json={"audio_url": upload_url},
                timeout=ASSEMBLYAI_TIMEOUT_SECONDS,
            )
            create_resp.raise_for_status()
            transcript_id = str(create_resp.json().get("id", "")).strip()
            if not transcript_id:
                return ""

            deadline = time.time() + max(10, ASSEMBLYAI_TIMEOUT_SECONDS)
            while time.time() < deadline:
                status_resp = requests.get(
                    f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}",
                    headers=auth_headers,
                    timeout=ASSEMBLYAI_TIMEOUT_SECONDS,
                )
                status_resp.raise_for_status()
                body = status_resp.json()
                status = str(body.get("status", "")).strip().lower()
                if status == "completed":
                    return str(body.get("text", "")).strip()
                if status == "error":
                    error_text = str(body.get("error", "unknown AssemblyAI error")).strip()
                    print(f"[assemblyai stt error] {error_text}")
                    return ""
                time.sleep(max(0.2, ASSEMBLYAI_POLL_SECONDS))
        except Exception as exc:
            print(f"[assemblyai stt error] {exc}")
            return ""

        print("[assemblyai stt error] transcription timed out")
        return ""

    def _listen_with_assemblyai(self) -> Optional[str]:
        if not ASSEMBLYAI_API_KEY:
            return None

        self.last_recognition_confidence = None
        stop_event = threading.Event()

        def _transcribe_from_pcm_chunks(chunks: List[bytes], frame_count: int, speech_frames: int, rms_sum: float) -> str:
            if frame_count == 0 or speech_frames < WHISPER_MIN_SPEECH_FRAMES:
                if not TERMINAL_MINIMAL:
                    print("Could not understand the audio. Please speak again.")
                return ""

            pcm = b"".join(chunks)
            recognized_text = self._transcribe_with_assemblyai(pcm)
            if not recognized_text:
                if not TERMINAL_MINIMAL:
                    print("Could not understand the audio. Please speak again.")
                return ""

            avg_rms = rms_sum / float(max(1, frame_count))
            self.last_recognition_confidence = 0.82
            gated_text = self._apply_stt_gates(
                recognized_text,
                confidence=self.last_recognition_confidence,
                avg_rms=avg_rms,
                speech_energy_frames=speech_frames,
                total_frames=frame_count,
            )
            if not gated_text:
                return ""

            print(f"You: {gated_text}")
            self._update_hud(heard=gated_text, intent="speech")
            return gated_text

        if pyaudio is not None:
            audio_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=256)
            pa = None
            stream = None
            try:
                if not TERMINAL_MINIMAL:
                    print("Listening... (say command)")
                pa = pyaudio.PyAudio()
                input_idx = self._pyaudio_input_device_index(pa)
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=WHISPER_SAMPLE_RATE,
                    input=True,
                    input_device_index=input_idx,
                    frames_per_buffer=WHISPER_CHUNK,
                )

                def _record_worker() -> None:
                    while not stop_event.is_set():
                        try:
                            data = stream.read(WHISPER_CHUNK, exception_on_overflow=False)
                        except Exception:
                            continue
                        try:
                            audio_queue.put(data, timeout=0.1)
                        except queue.Full:
                            pass

                t = threading.Thread(target=_record_worker, daemon=True)
                t.start()
                if not TERMINAL_MINIMAL:
                    print("   Recording started...")

                max_frames = int((WHISPER_SAMPLE_RATE / WHISPER_CHUNK) * LISTEN_MAX_SECONDS)
                frame_count = 0
                speech_frames = 0
                post_silence_frames = 0
                speech_started = False
                chunks: List[bytes] = []
                rms_sum = 0.0

                while frame_count < max_frames:
                    try:
                        chunk = audio_queue.get(timeout=0.4)
                    except queue.Empty:
                        if speech_started:
                            post_silence_frames += 1
                            if post_silence_frames >= WHISPER_END_SILENCE_FRAMES:
                                break
                        continue

                    frame_count += 1
                    chunks.append(chunk)
                    rms = self._rms_from_pcm16(chunk)
                    rms_sum += rms

                    if rms >= WHISPER_SILENCE_RMS:
                        speech_started = True
                        speech_frames += 1
                        post_silence_frames = 0
                    elif speech_started:
                        post_silence_frames += 1
                        if post_silence_frames >= WHISPER_END_SILENCE_FRAMES:
                            break

                if not TERMINAL_MINIMAL:
                    print("   Recording stopped.")
                stop_event.set()
                return _transcribe_from_pcm_chunks(chunks, frame_count, speech_frames, rms_sum)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"[assemblyai voice error] {exc}")
                return ""
            finally:
                stop_event.set()
                try:
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                except Exception:
                    pass
                try:
                    if pa is not None:
                        pa.terminate()
                except Exception:
                    pass

        if pvrecorder is None:
            return None

        recorder = None
        try:
            if not TERMINAL_MINIMAL:
                print("Listening... (say command)")
            recorder = self._open_recorder_with_fallback()
            if not TERMINAL_MINIMAL:
                print("   Recording started...")

            max_frames = int((WHISPER_SAMPLE_RATE / WHISPER_CHUNK) * LISTEN_MAX_SECONDS)
            frame_count = 0
            speech_frames = 0
            post_silence_frames = 0
            speech_started = False
            chunks: List[bytes] = []
            rms_sum = 0.0

            while frame_count < max_frames:
                try:
                    frame = recorder.read()
                except KeyboardInterrupt:
                    raise
                except Exception:
                    continue

                frame_count += 1
                frame = self._apply_input_gain(frame)
                chunk = struct.pack("<%dh" % len(frame), *frame)
                chunks.append(chunk)
                rms = self._rms_from_pcm16(chunk)
                rms_sum += rms

                if rms >= WHISPER_SILENCE_RMS:
                    speech_started = True
                    speech_frames += 1
                    post_silence_frames = 0
                elif speech_started:
                    post_silence_frames += 1
                    if post_silence_frames >= WHISPER_END_SILENCE_FRAMES:
                        break

            if not TERMINAL_MINIMAL:
                    print("   Recording stopped.")
            return _transcribe_from_pcm_chunks(chunks, frame_count, speech_frames, rms_sum)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[assemblyai pvrecorder error] {exc}")
            return ""
        finally:
            try:
                if recorder is not None:
                    recorder.stop()
                    recorder.delete()
            except Exception:
                pass

    def _listen_with_whisper_streaming(self) -> Optional[str]:
        if self.whisper_model is None or np is None:
            return None

        self.last_recognition_confidence = None
        stop_event = threading.Event()

        def _transcribe_from_pcm_chunks(chunks: List[bytes], frame_count: int, speech_frames: int, rms_sum: float) -> str:
            if frame_count == 0 or speech_frames < WHISPER_MIN_SPEECH_FRAMES:
                if not TERMINAL_MINIMAL:
                    print("Could not understand the audio. Please speak again.")
                return ""

            pcm = b"".join(chunks)
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

            def _decode_with(model_obj: Any) -> str:
                segments, _info = model_obj.transcribe(
                    audio,
                    language="en",
                    vad_filter=WHISPER_VAD_FILTER,
                    beam_size=1,
                    best_of=1,
                    condition_on_previous_text=False,
                )
                parts: List[str] = []
                for seg in segments:
                    seg_text = str(seg.text or "").strip()
                    if seg_text:
                        parts.append(seg_text)
                return " ".join(parts).strip()

            recognized_text = _decode_with(self.whisper_model)
            if not recognized_text:
                if not TERMINAL_MINIMAL:
                    print("Could not understand the audio. Please speak again.")
                return ""

            fast_norm = self._normalize_text_command(recognized_text)
            fast_tokens = [t for t in fast_norm.split() if t]
            fast_has_keyword = any(t in COMMAND_KEYWORDS for t in fast_tokens)
            fast_needs_verify = WHISPER_VERIFY_FOR_SHORT and (len(fast_tokens) <= 2 or not fast_has_keyword)

            if self.whisper_verify_model is not None and fast_needs_verify:
                try:
                    verify_text = _decode_with(self.whisper_verify_model)
                    verify_norm = self._normalize_text_command(verify_text)
                    verify_tokens = [t for t in verify_norm.split() if t]
                    verify_has_keyword = any(t in COMMAND_KEYWORDS for t in verify_tokens)

                    if verify_text and (
                        (verify_has_keyword and not fast_has_keyword)
                        or (verify_has_keyword == fast_has_keyword and len(verify_norm) > len(fast_norm) + 2)
                    ):
                        recognized_text = verify_text
                except Exception:
                    pass

            avg_rms = rms_sum / float(max(1, frame_count))
            self.last_recognition_confidence = 0.78
            gated_text = self._apply_stt_gates(
                recognized_text,
                confidence=self.last_recognition_confidence,
                avg_rms=avg_rms,
                speech_energy_frames=speech_frames,
                total_frames=frame_count,
            )
            if not gated_text:
                return ""

            print(f"You: {gated_text}")
            self._update_hud(heard=gated_text, intent="speech")
            return gated_text

        if pyaudio is not None:
            audio_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=256)
            pa = None
            stream = None
            try:
                if not TERMINAL_MINIMAL:
                    print("Listening... (say command)")
                pa = pyaudio.PyAudio()
                input_idx = self._pyaudio_input_device_index(pa)
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=WHISPER_SAMPLE_RATE,
                    input=True,
                    input_device_index=input_idx,
                    frames_per_buffer=WHISPER_CHUNK,
                )

                def _record_worker() -> None:
                    while not stop_event.is_set():
                        try:
                            data = stream.read(WHISPER_CHUNK, exception_on_overflow=False)
                        except Exception:
                            continue
                        try:
                            audio_queue.put(data, timeout=0.1)
                        except queue.Full:
                            pass

                t = threading.Thread(target=_record_worker, daemon=True)
                t.start()

                if PUSH_TO_TALK_SPACE_ENABLED:
                    if not TERMINAL_MINIMAL:
                        print("Hold SPACE to talk, release to send.")
                    self._wait_until_space_pressed()

                    max_frames = int((WHISPER_SAMPLE_RATE / WHISPER_CHUNK) * max(2, PUSH_TO_TALK_MAX_SECONDS))
                    frame_count = 0
                    speech_frames = 0
                    chunks: List[bytes] = []
                    rms_sum = 0.0

                    while frame_count < max_frames:
                        pressed = self._is_space_pressed()
                        if not pressed and frame_count > 0:
                            break
                        try:
                            chunk = audio_queue.get(timeout=0.12)
                        except queue.Empty:
                            if not self._is_space_pressed() and frame_count > 0:
                                break
                            continue

                        frame_count += 1
                        chunks.append(chunk)
                        rms = self._rms_from_pcm16(chunk)
                        rms_sum += rms
                        if rms >= max(30.0, WHISPER_SILENCE_RMS * 0.55):
                            speech_frames += 1

                    stop_event.set()
                    return _transcribe_from_pcm_chunks(chunks, frame_count, speech_frames, rms_sum)

                if not TERMINAL_MINIMAL:
                    print("   Recording started...")

                max_frames = int((WHISPER_SAMPLE_RATE / WHISPER_CHUNK) * LISTEN_MAX_SECONDS)
                frame_count = 0
                speech_frames = 0
                post_silence_frames = 0
                speech_started = False
                chunks: List[bytes] = []
                rms_sum = 0.0

                while frame_count < max_frames:
                    try:
                        chunk = audio_queue.get(timeout=0.4)
                    except queue.Empty:
                        if speech_started:
                            post_silence_frames += 1
                            if post_silence_frames >= WHISPER_END_SILENCE_FRAMES:
                                break
                        continue

                    frame_count += 1
                    chunks.append(chunk)
                    rms = self._rms_from_pcm16(chunk)
                    rms_sum += rms

                    if rms >= WHISPER_SILENCE_RMS:
                        speech_started = True
                        speech_frames += 1
                        post_silence_frames = 0
                    elif speech_started:
                        post_silence_frames += 1
                        if post_silence_frames >= WHISPER_END_SILENCE_FRAMES:
                            break

                if not TERMINAL_MINIMAL:
                    print("   Recording stopped.")
                stop_event.set()
                return _transcribe_from_pcm_chunks(chunks, frame_count, speech_frames, rms_sum)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"[whisper voice error] {exc}")
                return ""
            finally:
                stop_event.set()
                try:
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                except Exception:
                    pass
                try:
                    if pa is not None:
                        pa.terminate()
                except Exception:
                    pass

        if pvrecorder is None:
            return None

        recorder = None
        try:
            if not TERMINAL_MINIMAL:
                print("Listening... (say command)")
            recorder = self._open_recorder_with_fallback()

            if PUSH_TO_TALK_SPACE_ENABLED:
                if not TERMINAL_MINIMAL:
                    print("Hold SPACE to talk, release to send.")
                self._wait_until_space_pressed()

                max_frames = int((WHISPER_SAMPLE_RATE / WHISPER_CHUNK) * max(2, PUSH_TO_TALK_MAX_SECONDS))
                frame_count = 0
                speech_frames = 0
                chunks: List[bytes] = []
                rms_sum = 0.0

                while frame_count < max_frames:
                    pressed = self._is_space_pressed()
                    if not pressed and frame_count > 0:
                        break
                    try:
                        frame = recorder.read()
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        continue

                    frame_count += 1
                    frame = self._apply_input_gain(frame)
                    chunk = struct.pack("<%dh" % len(frame), *frame)
                    chunks.append(chunk)
                    rms = self._rms_from_pcm16(chunk)
                    rms_sum += rms
                    if rms >= max(30.0, WHISPER_SILENCE_RMS * 0.55):
                        speech_frames += 1

                return _transcribe_from_pcm_chunks(chunks, frame_count, speech_frames, rms_sum)

            if not TERMINAL_MINIMAL:
                print("   Recording started...")

            max_frames = int((WHISPER_SAMPLE_RATE / WHISPER_CHUNK) * LISTEN_MAX_SECONDS)
            frame_count = 0
            speech_frames = 0
            post_silence_frames = 0
            speech_started = False
            chunks: List[bytes] = []
            rms_sum = 0.0

            while frame_count < max_frames:
                try:
                    frame = recorder.read()
                except KeyboardInterrupt:
                    raise
                except Exception:
                    continue

                frame_count += 1
                frame = self._apply_input_gain(frame)
                chunk = struct.pack("<%dh" % len(frame), *frame)
                chunks.append(chunk)
                rms = self._rms_from_pcm16(chunk)
                rms_sum += rms

                if rms >= WHISPER_SILENCE_RMS:
                    speech_started = True
                    speech_frames += 1
                    post_silence_frames = 0
                elif speech_started:
                    post_silence_frames += 1
                    if post_silence_frames >= WHISPER_END_SILENCE_FRAMES:
                        break

            if not TERMINAL_MINIMAL:
                print("   Recording stopped.")
            return _transcribe_from_pcm_chunks(chunks, frame_count, speech_frames, rms_sum)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[whisper pvrecorder error] {exc}")
            return ""
        finally:
            try:
                if recorder is not None:
                    recorder.stop()
                    recorder.delete()
            except Exception:
                pass

    def listen(self) -> str:
        self.last_recognition_confidence = None

        if self.stt_engine == "windows":
            windows_result = self._listen_with_windows_speech()
            if windows_result is not None:
                return windows_result

        if self.stt_engine == "vosk":
            self._ensure_vosk_model_loaded()

        if self.stt_engine == "assemblyai":
            assembly_result = self._listen_with_assemblyai()
            if assembly_result is not None:
                return assembly_result

        if self.stt_engine == "whisper":
            whisper_result = self._listen_with_whisper_streaming()
            if whisper_result is not None:
                return whisper_result

        if self.kaldi_recognizer and pvrecorder and self.vosk_model:
            recorder = None
            try:
                if not TERMINAL_MINIMAL:
                    print("Listening... (say command)")

                recorder = self._open_recorder_with_fallback()
                if not TERMINAL_MINIMAL:
                    print("   Recording started...")

                max_frames = int((VOSK_SAMPLE_RATE / 512) * LISTEN_MAX_SECONDS)
                frame_count = 0
                final_result = ""
                best_partial = ""
                last_result_obj: Optional[Dict[str, Any]] = None
                silence_frames = 0
                last_partial = ""
                speech_started = False
                speech_energy_frames = 0
                speech_rms_sum = 0.0
                speech_rms_count = 0
                rms_sum = 0.0
                noise_probe_sum = 0.0
                noise_probe_frames = 0
                read_errors = 0

                while frame_count < max_frames:
                    try:
                        frame = recorder.read()
                        frame_count += 1
                        read_errors = 0
                    except KeyboardInterrupt:
                        break
                    except Exception as exc:
                        read_errors += 1
                        if read_errors in {1, 5, 10}:
                            print(f"   [debug] mic read error ({read_errors}): {exc}")
                        if read_errors >= 16:
                            break
                        time.sleep(0.02)
                        continue

                    frame = self._apply_input_gain(frame)
                    frame_rms = self._frame_rms(frame)
                    rms_sum += frame_rms

                    if frame_count <= 18 and not speech_started:
                        noise_probe_sum += frame_rms
                        noise_probe_frames += 1

                    dynamic_threshold = max(self._noise_floor_rms * STT_NOISE_SPEECH_RATIO, STT_NOISE_MIN_RMS)
                    if frame_rms >= dynamic_threshold:
                        speech_energy_frames += 1
                        speech_rms_sum += frame_rms
                        speech_rms_count += 1

                    frame_bytes = struct.pack("<%dh" % len(frame), *frame)

                    if self.kaldi_recognizer.AcceptWaveform(frame_bytes):
                        result_json = self.kaldi_recognizer.Result()
                        result = json.loads(result_json)
                        last_result_obj = result
                        conf = self._extract_confidence(result)
                        if conf is not None:
                            self.last_recognition_confidence = conf
                        final_result = str(result.get("text", "")).strip()
                        if not final_result and "result" in result and result["result"]:
                            final_result = " ".join([item.get("word", "") for item in result["result"]]).strip()
                        break
                    else:
                        if frame_count % max(1, VOSK_PARTIAL_INTERVAL_FRAMES) == 0:
                            partial_json = self.kaldi_recognizer.PartialResult()
                            if partial_json:
                                partial = json.loads(partial_json)
                                if "partial" in partial and partial["partial"]:
                                    current_partial = partial["partial"].strip()
                                    if current_partial:
                                        speech_started = True
                                        if current_partial != last_partial:
                                            if not TERMINAL_MINIMAL:
                                                print(f"   Partial: {current_partial}")
                                            last_partial = current_partial
                                            best_partial = current_partial
                                            silence_frames = 0
                                        else:
                                            silence_frames += 1
                                    else:
                                        silence_frames += 1
                                else:
                                    silence_frames += 1

                                if speech_started and silence_frames > VOSK_END_SILENCE_FRAMES:
                                    break

                if recorder:
                    recorder.stop()
                    recorder.delete()
                if not TERMINAL_MINIMAL:
                    print("   Recording stopped.")

                if noise_probe_frames > 0:
                    observed_floor = noise_probe_sum / float(noise_probe_frames)
                    self._noise_floor_rms = max(STT_NOISE_MIN_RMS, (self._noise_floor_rms * 0.7) + (observed_floor * 0.3))
                    observed_speech = (speech_rms_sum / float(max(1, speech_rms_count))) if speech_rms_count > 0 else max(observed_floor * 2.0, STT_NOISE_MIN_RMS)
                    self._persist_stt_calibration(
                        noise_floor_rms=self._noise_floor_rms,
                        speech_rms=observed_speech,
                        input_gain=self._input_gain,
                        frames=frame_count,
                    )

                if not final_result:
                    result_json = self.kaldi_recognizer.FinalResult()
                    if result_json:
                        result = json.loads(result_json)
                        last_result_obj = result
                        conf = self._extract_confidence(result)
                        if conf is not None:
                            self.last_recognition_confidence = conf
                        final_result = str(result.get("text", "")).strip()
                        if not final_result and "result" in result and result["result"]:
                            final_result = " ".join([item.get("word", "") for item in result["result"]]).strip()

                recognized_text, selected_confidence = self._select_best_stt_candidate(last_result_obj, best_partial)
                if not recognized_text:
                    recognized_text = final_result.strip()
                avg_rms = (rms_sum / float(max(1, frame_count))) if frame_count else 0.0

                self._reset_recognizer()

                if recognized_text:
                    self._consecutive_empty_captures = 0
                    confidence = selected_confidence if selected_confidence is not None else self.last_recognition_confidence
                    gated_text = self._apply_stt_gates(
                        recognized_text,
                        confidence=confidence,
                        avg_rms=avg_rms,
                        speech_energy_frames=speech_energy_frames,
                        total_frames=frame_count,
                    )
                    if not gated_text:
                        self._consecutive_empty_captures += 1
                        if self._consecutive_empty_captures >= 3:
                            self._maybe_rotate_mic_device()
                        return ""

                    token_count = len(self._normalize_text_command(gated_text).split())
                    min_conf = WAKE_MIN_CONFIDENCE if token_count <= 2 else COMMAND_MIN_CONFIDENCE
                    if confidence is not None and confidence < min_conf:
                        print(f"Low confidence ({confidence:.2f}) transcript ignored.")
                        return ""

                    print(f"You: {gated_text}")
                    self._update_hud(heard=gated_text, intent="speech")
                    return gated_text

                self._consecutive_empty_captures += 1
                if self._consecutive_empty_captures >= 3:
                    self._maybe_rotate_mic_device()
                if frame_count:
                    if not TERMINAL_MINIMAL:
                        print(f"   [debug] average mic rms: {avg_rms:.1f}")
                if not TERMINAL_MINIMAL:
                    print("Could not understand the audio. Please speak again.")
                return ""

            except KeyboardInterrupt:
                print("\nStopping...")
                if recorder:
                    try:
                        recorder.stop()
                        recorder.delete()
                    except Exception:
                        pass
                raise
            except Exception as exc:
                print(f"[voice error] {exc}")
                if recorder:
                    try:
                        recorder.stop()
                        recorder.delete()
                    except Exception:
                        pass
                print("Falling back to text input...")

        typed = input("Type command: ").strip()
        self._update_hud(heard=typed, intent="typed")
        return typed

    @staticmethod
    def strip_wake_word(text: str) -> str:
        t = text.strip()
        normalized = LaptopJarvisClient._normalize_wake_probe(t)
        if not normalized:
            return ""

        if normalized == "jarvis":
            return ""
        if normalized.startswith("jarvis "):
            return " ".join(t.split()[1:]).lstrip(" ,:-").strip()

        wake_candidates = [LaptopJarvisClient._normalize_wake_probe(w) for w in (list(WAKE_WORDS) + list(WAKE_WORD_VARIANTS))]

        # Exact prefix detection first.
        for wake in wake_candidates:
            if wake and normalized.startswith(wake):
                word_count = len(wake.split())
                remainder = " ".join(t.split()[word_count:])
                return remainder.lstrip(" ,:-").strip()

        # Fuzzy prefix detection for accent/mishearing tolerance.
        if ACCENT_TOLERANT_MODE:
            words = t.split()
            if len(words) >= 2:
                first_token = LaptopJarvisClient._normalize_text_command(words[0])
                if first_token not in WAKE_LEAD_TOKENS:
                    return ""
                first_two = LaptopJarvisClient._normalize_wake_probe(" ".join(words[:2]))
                if any(token in first_two for token in ("jar", "jarv", "jerv")):
                    for wake in wake_candidates:
                        if wake and difflib.SequenceMatcher(None, first_two, wake).ratio() >= WAKE_FUZZY_THRESHOLD:
                            remainder = " ".join(words[2:])
                            return remainder.lstrip(" ,:-").strip()

        return ""

    def send_command(self, text: str) -> Dict[str, Any]:
        payload = {"text": text, "client": "pc"}
        response = requests.post(f"{self.backend_url}/command", json=payload, timeout=60)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Backend did not return a JSON object")
        return body

    def _handle_system_query(self, text: str) -> Optional[Dict[str, Any]]:
        """Handle local system queries - always check these locally first."""
        text_lower = text.strip().lower()

        if re.search(r"\blast\s+time\b|\blast\s+command\b|\bprevious\s+command\b", text_lower):
            return None
        
        # Name queries
        if re.search(r"\bwhat.*\bmy\s+name\b|\bwhat\s+is\s+my\s+name\b|\bmy\s+name\b|\bwho\s+am\s+i\b", text_lower):
            # Try to get name from memory
            try:
                from memory_store import PostgresMemoryStore
                memory_store = PostgresMemoryStore(database_url="", history_limit=12, fact_limit=20)
                name = memory_store.get_fact(client="pc", fact_key="name")
                if name:
                    return {
                        "action": "type_text",
                        "response": f"Your name is {name}.",
                        "text": f"Your name is {name}.",
                    }
                else:
                    return {
                        "action": "type_text",
                        "response": "I don't know your name yet. Please tell me your name.",
                        "text": "I don't know your name yet. Please tell me your name.",
                    }
            except Exception:
                return {
                    "action": "type_text",
                    "response": "I don't know your name yet. Please tell me your name.",
                    "text": "I don't know your name yet. Please tell me your name.",
                }
        
        # Handle name setting ("my name is ...")
        name_match = re.match(r"^(?:my\s+name\s+is|i\s+(?:am|am\s+called))\s+(.+)$", text_lower)
        if name_match:
            name = name_match.group(1).strip().strip(".,:;!?")
            if name and len(name) > 1:
                try:
                    from memory_store import PostgresMemoryStore
                    memory_store = PostgresMemoryStore(database_url="", history_limit=12, fact_limit=20)
                    memory_store.set_fact(client="pc", fact_key="name", fact_value=name)
                    return {
                        "action": "type_text",
                        "response": f"Got it! I'll remember that your name is {name}.",
                        "text": f"Got it! I'll remember that your name is {name}.",
                    }
                except Exception:
                    return {
                        "action": "type_text",
                        "response": f"I'll remember that your name is {name}.",
                        "text": f"I'll remember that your name is {name}.",
                    }
        
        # Time queries - highest priority
        if re.search(r"\btime\b", text_lower):
            current_time = datetime.now().strftime("%I:%M %p")
            return {
                "action": "type_text",
                "response": f"The current time is {current_time}",
                "text": f"The current time is {current_time}",
            }
        
        # Date and day queries
        if "date" in text_lower or "today" in text_lower or ("day" in text_lower and "what" in text_lower):
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            return {
                "action": "type_text",
                "response": f"Today is {current_date}",
                "text": f"Today is {current_date}",
            }
        
        # Battery queries
        if re.search(r"\b(battery|charge)\b", text_lower) or re.search(r"\bpower\s+(?:level|status|remaining)\b", text_lower):
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-CimInstance -ClassName Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    battery_percentage = result.stdout.strip()
                    return {
                        "action": "type_text",
                        "response": f"Battery level is at {battery_percentage} percent",
                        "text": f"Battery level is at {battery_percentage} percent",
                    }
            except Exception:
                pass
            return {
                "action": "type_text",
                "response": "Battery information not available",
                "text": "Battery information not available",
            }
        
        # File explorer
        if "file explorer" in text_lower or "open files" in text_lower or "open folder" in text_lower:
            subprocess.Popen("explorer.exe")
            return {
                "action": "type_text",
                "response": "Opening file explorer",
                "text": "Opening file explorer",
            }
        
        website_match = re.match(r"^(?:open|launch|start|run)\s+(https?://\S+|www\.\S+)$", text_lower)
        if website_match:
            url = website_match.group(1)
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            return {
                "action": "open_website",
                "url": url,
                "response": "Opening website",
            }

        if re.fullmatch(r"(?:open\s+)?whatsapp(?:\s+app)?\s+(?:in|on)\s+chrome", text_lower):
            return {
                "action": "open_website",
                "url": "https://web.whatsapp.com",
                "response": "Opening WhatsApp in Chrome",
            }

        if re.fullmatch(r"(?:open|launch|start|run)\s+whatsapp(?:\s+app)?", text_lower) or text_lower == "whatsapp":
            return {
                "action": "open_app",
                "app": "whatsapp",
                "response": "Opening WhatsApp",
            }

        open_match = re.match(r"^(?:open|launch|start|run)\s+(.+)$", text_lower)
        if open_match:
            app_name = open_match.group(1).strip(" .,:;!?")
            app_name = re.sub(r"^(the|a|an)\s+", "", app_name).strip()
            app_name = re.sub(r"\s+app$", "", app_name).strip()
            if app_name:
                return {
                    "action": "open_app",
                    "app": app_name,
                    "response": f"Opening {app_name}",
                }

        if (
            ("like" in text_lower and "spotify" in text_lower)
            or "add this song" in text_lower
            or "save this song" in text_lower
        ):
            return {
                "action": "spotify_like",
                "response": "Liking current song on Spotify",
                "text": "Liking current song on Spotify",
            }
        
        # Not a local query, return None and let backend handle it
        return None

    def _open_app(self, app_name: str, post_text: Optional[str] = None) -> str:
        raw_app = re.sub(r"\s+", " ", app_name.strip().lower())
        raw_app = re.sub(r"\s+(?:in|on)\s+(?:chrome|browser)$", "", raw_app).strip()
        raw_app = re.sub(r"^(the|a|an)\s+", "", raw_app).strip()
        raw_app = re.sub(r"\s+app$", "", raw_app).strip()
        self.pending_alias_suggestion = None
        app = self.dynamic_aliases.get(raw_app, APP_ALIASES.get(raw_app, raw_app))
        if app in WEB_ALIASES:
            webbrowser.open(WEB_ALIASES[app])
            return f"Opening {app} in browser"
        app_map = {
            "chrome": ["cmd", "/c", "start", "chrome"],
            "notepad": ["notepad"],
            "calculator": ["calc"],
            "explorer": ["explorer"],
            "vscode": ["cmd", "/c", "start", "code"],
            "terminal": ["wt"],
            "cmd": ["cmd"],
            "powershell": ["powershell"],
        }
        cmd = app_map.get(app)

        try:
            if cmd:
                subprocess.Popen(cmd, shell=False)
                self._handle_post_open_action(app, post_text)
                return f"Opening {app_name}"

            app_uri = APP_URI_MAP.get(app)
            if app_uri:
                subprocess.Popen(["cmd", "/c", "start", "", app_uri], shell=False)
                self._handle_post_open_action(app, post_text)
                return f"Opening {app_name}"

            # Try executable resolution from PATH.
            candidates = [app, app.replace(" ", ""), f"{app}.exe", f"{app.replace(' ', '')}.exe"]
            seen: set = set()
            for candidate in candidates:
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                where_result = subprocess.run(
                    ["where", candidate],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if where_result.returncode == 0:
                    first_path = where_result.stdout.splitlines()[0].strip()
                    if first_path:
                        subprocess.Popen(["cmd", "/c", "start", "", first_path], shell=False)
                        self._handle_post_open_action(app, post_text)
                        return f"Opening {app_name}"

            app_id = self._find_start_menu_app_id(app)
            if app_id:
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], shell=False)
                self._handle_post_open_action(app, post_text)
                return f"Opening {app_name}"

            shortcut = self._find_start_menu_shortcut(app)
            if shortcut:
                os.startfile(shortcut)  # type: ignore[attr-defined]
                self._handle_post_open_action(app, post_text)
                return f"Opening {app_name}"

            web_fallbacks = {
                "youtube": "https://www.youtube.com/",
            }
            if app in web_fallbacks:
                webbrowser.open(web_fallbacks[app])
                return f"Opening {app_name} in browser"
        except Exception as exc:
            return f"Failed to open {app_name}: {exc}"

        suggestion = self._suggest_app_name(raw_app)
        if suggestion and suggestion != raw_app:
            self.pending_alias_suggestion = {"spoken": raw_app, "suggested": suggestion}
            return f"I could not find {app_name}. Did you mean {suggestion}? Say yes or no."
        return f"I could not open app {app_name} on laptop"

    @staticmethod
    def _is_quiet_success_message(message: str) -> bool:
        text = re.sub(r"\s+", " ", (message or "").strip().lower())
        if not text:
            return False
        if text.startswith(("i could not", "could not", "failed", "backend", "please ", "do you ", "which ")):
            return False
        quiet_prefixes = (
            "opening ",
            "closing ",
            "playing ",
            "searching ",
            "toggling ",
            "skipping ",
            "going to previous",
            "increasing ",
            "decreasing ",
            "setting pc ",
            "setting brightness",
            "setting volume",
            "adjusting ",
            "muting ",
            "opened ",
        )
        return text.startswith(quiet_prefixes)

    def _close_app(self, app_name: str) -> str:
        app = app_name.strip().lower()
        process_map = {
            "chrome": ["chrome.exe"],
            "google chrome": ["chrome.exe"],
            "spotify": ["spotify.exe", "spotifylauncher.exe"],
            "whatsapp": ["whatsapp.exe"],
            "terminal": ["WindowsTerminal.exe", "wt.exe"],
            "windows terminal": ["WindowsTerminal.exe", "wt.exe"],
            "vscode": ["code.exe"],
            "notepad": ["notepad.exe"],
            "explorer": ["explorer.exe"],
        }

        process_images = process_map.get(app)
        if not process_images:
            base = app.replace(" ", "")
            process_images = [f"{base}.exe"]

        for image in process_images:
            result = subprocess.run(
                ["taskkill", "/IM", image, "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return f"Closing {app_name}"

        return f"I could not close app {app_name} on laptop"

    def _handle_post_open_action(self, app: str, post_text: Optional[str]) -> None:
        query = (post_text or "").strip()
        if not query:
            return
        if query.lower() in {"none", "null", "undefined", "n/a", "na"}:
            return

        if pyautogui is None:
            return

        if app == "spotify":
            self._spotify_search_and_play(query)
            return

        time.sleep(1.5)
        try:
            pyautogui.hotkey("ctrl", "l")
            pyautogui.typewrite(query, interval=0.02)
            pyautogui.press("enter")
        except Exception:
            pass

    def _focus_spotify_window(self) -> None:
        if pyautogui is None:
            return
        try:
            ps_script = (
                "Add-Type -Name WinApi -Namespace Native -MemberDefinition '"
                "[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);"
                "[DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);"
                "'; "
                "$p = Get-Process Spotify -ErrorAction SilentlyContinue | "
                "Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
                "if ($p) { [Native.WinApi]::ShowWindowAsync($p.MainWindowHandle, 9) | Out-Null; "
                "[Native.WinApi]::SetForegroundWindow($p.MainWindowHandle) | Out-Null }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                check=False,
                timeout=4,
            )
            time.sleep(0.5)
            width, height = pyautogui.size()
            pyautogui.click(int(width * 0.5), int(height * 0.35))
        except Exception:
            pass

    def _spotify_search_and_play(self, query: str) -> None:
        if pyautogui is None:
            print("[Spotify] pyautogui not available")
            return

        try:
            search_uri = f"spotify:search:{quote_plus(query)}"
            subprocess.Popen(["cmd", "/c", "start", "", search_uri], shell=False)
            time.sleep(4.0)
            
            self._focus_spotify_window()
            time.sleep(0.8)
            
            # Force the search UI to contain the requested query so Spotify
            # does not simply resume the old paused track.
            pyautogui.hotkey("ctrl", "k")
            time.sleep(0.6)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.typewrite(query, interval=0.04)
            time.sleep(1.0)
            
            pyautogui.press("enter")
            time.sleep(1.1)
            pyautogui.press("enter")
            time.sleep(1.0)
            print(f"[Spotify] Playing: {query}")
        except Exception as e:
            print(f"[Spotify] Error: {e}")

    def _spotify_like_current_song(self) -> str:
        if pyautogui is None:
            return "Spotify like is unavailable because UI automation is disabled."

        try:
            subprocess.Popen("spotify", shell=True)
            time.sleep(1.5)
            self._focus_spotify_window()
            time.sleep(0.3)
            # Spotify desktop shortcut to like/save current song.
            pyautogui.hotkey("ctrl", "s")
            return "Liked current song on Spotify."
        except Exception as exc:
            return f"Could not like current song on Spotify: {exc}"

    def _find_start_menu_app_id(self, app_name: str) -> Optional[str]:
        try:
            start_apps = self._get_start_apps()
        except Exception:
            return None

        normalized = re.sub(r"\s+", " ", app_name.strip().lower())
        if not normalized:
            return None

        exact = next(
            (item["AppID"] for item in start_apps if item["Name"].strip().lower() == normalized),
            None,
        )
        if exact:
            return exact

        fuzzy = next(
            (
                item["AppID"]
                for item in start_apps
                if normalized in item["Name"].strip().lower()
            ),
            None,
        )
        return fuzzy

    def _get_start_apps(self) -> List[Dict[str, str]]:
        if (
            self._start_apps_cache is not None
            and (time.time() - self._start_apps_cache_ts) < START_APPS_CACHE_TTL_SECONDS
        ):
            return self._start_apps_cache

        ps_command = (
            "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            self._start_apps_cache = []
            self._start_apps_cache_ts = time.time()
            return self._start_apps_cache

        parsed = json.loads(result.stdout)
        if isinstance(parsed, dict):
            parsed = [parsed]

        apps: List[Dict[str, str]] = []
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("Name", "")).strip()
                app_id = str(item.get("AppID", "")).strip()
                if name and app_id:
                    apps.append({"Name": name, "AppID": app_id})

        self._start_apps_cache = apps
        self._start_apps_cache_ts = time.time()
        return self._start_apps_cache

    def _find_start_menu_shortcut(self, app_name: str) -> Optional[str]:
        shortcuts = self._get_start_menu_shortcuts()
        normalized = re.sub(r"\s+", " ", app_name.strip().lower())
        if not normalized:
            return None

        exact = next((item["path"] for item in shortcuts if item["name"] == normalized), None)
        if exact:
            return exact

        fuzzy = next((item["path"] for item in shortcuts if normalized in item["name"]), None)
        return fuzzy

    def _get_start_menu_shortcuts(self) -> List[Dict[str, str]]:
        if self._start_menu_shortcuts_cache is not None:
            return self._start_menu_shortcuts_cache

        candidates = []
        roots = [
            os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        ]
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    if not filename.lower().endswith(".lnk"):
                        continue
                    full_path = os.path.join(dirpath, filename)
                    base_name = os.path.splitext(filename)[0]
                    normalized_name = re.sub(r"\s+", " ", base_name.strip().lower())
                    if normalized_name:
                        candidates.append({"name": normalized_name, "path": full_path})

        self._start_menu_shortcuts_cache = candidates
        return self._start_menu_shortcuts_cache

    def execute_pc_action(self, action: Dict[str, Any]) -> None:
        action_name = str(action.get("action", "")).lower()

        if action_name == "open_website":
            url = str(action.get("url", "")).strip()
            if url:
                webbrowser.open(url)
                return
            self.speak("Website URL missing")
            return

        if action_name == "open_app":
            app_name = str(action.get("app", "")).strip()
            raw_text = action.get("text")
            post_text = raw_text.strip() if isinstance(raw_text, str) else None
            if post_text and post_text.lower() in {"none", "null", "undefined", "n/a", "na"}:
                post_text = None
            if app_name:
                open_result = self._open_app(app_name, post_text=post_text)
                if open_result.startswith("Opening "):
                    return
                else:
                    self.speak(open_result)
                return
            self.speak("App name missing")
            return

        if action_name == "close_app":
            app_name = str(action.get("app", "")).strip()
            if app_name:
                close_result = self._close_app(app_name)
                if close_result.startswith("Closing "):
                    return
                else:
                    self.speak(close_result)
                return
            self.speak("App name missing")
            return

        if action_name == "send_whatsapp":
            phone = str(action.get("phone", "")).strip()
            message = str(action.get("message", "")).strip()
            if phone:
                query = f"https://wa.me/{phone}"
                if message:
                    query = f"{query}?text={quote_plus(message)}"
                webbrowser.open(query)
                return
            self.speak("WhatsApp phone number is missing.")
            return

        if action_name == "spotify_like":
            result = self._spotify_like_current_song()
            self.speak(action.get("response") or result)
            if result and result != action.get("response"):
                print(result)
            return

        if action_name == "type_text":
            message = str(action.get("response") or action.get("text") or "Okay")
            if not self._is_quiet_success_message(message):
                self.speak(message)
            return

        # PC control actions are executed on backend and returned as type_text.
        message = str(action.get("response") or "Done")
        if not self._is_quiet_success_message(message):
            self.speak(message)

    def _looks_like_direct_command(self, normalized_text: str) -> bool:
        text = self._normalize_text_command(normalized_text)
        if not text:
            return False

        tokens = [t for t in text.split() if t]
        if not tokens:
            return False

        if text in {"exit", "quit", "stop", "text", "voice", "switch to text", "switch to voice"}:
            return True

        fillers = {
            "oh", "okay", "ok", "hmm", "um", "uh", "so", "thanks", "thank you", "welcome", "hello", "hi"
        }
        if text in fillers:
            return False

        if len(tokens) <= 2 and all(t in fillers for t in tokens):
            return False

        command_verbs = {
            "open", "close", "play", "pause", "resume", "next", "previous", "search", "find", "type", "send", "call",
            "turn", "set", "increase", "decrease", "raise", "lower", "mute", "unmute", "shutdown", "restart", "sleep"
        }
        if tokens[0] in command_verbs:
            return True

        if any(t in COMMAND_KEYWORDS for t in tokens):
            return True

        app_words = {
            "chrome", "spotify", "whatsapp", "youtube", "vscode", "notepad", "calculator", "explorer", "settings"
        }
        if any(t in app_words for t in tokens):
            return True

        # Generic Q/A chatter in always-on mode should be ignored unless explicit command intent appears.
        if tokens[0] in {"who", "what", "when", "where", "why", "how", "tell", "define", "explain"}:
            return False

        return False

    def _canonicalize_windows_command(self, normalized: str) -> str:
        candidates = []

        for m in re.finditer(r"\b(previous(?:\s+(?:song|track))?|back\s+song|previous)\b", normalized):
            candidates.append((m.start(), "previous song"))
        for m in re.finditer(r"\b(next(?:\s+(?:song|track))?|skip|next)\b", normalized):
            candidates.append((m.start(), "next song"))
        for m in re.finditer(r"\b(pause|resume|play)\b", normalized):
            token = m.group(1)
            mapped = "resume" if token == "resume" else token
            candidates.append((m.start(), mapped))

        for m in re.finditer(r"\b(?:increase|raise|up|higher)\b.*\bbrightness\b|\bbrightness\b.*\b(?:increase|raise|up|higher)\b", normalized):
            candidates.append((m.start(), "increase brightness"))
        for m in re.finditer(r"\b(?:decrease|lower|down|reduce)\b.*\bbrightness\b|\bbrightness\b.*\b(?:decrease|lower|down|reduce)\b", normalized):
            candidates.append((m.start(), "decrease brightness"))

        for m in re.finditer(r"\b(?:increase|raise|up|higher)\b.*\bvolume\b|\bvolume\b.*\b(?:increase|raise|up|higher)\b", normalized):
            candidates.append((m.start(), "increase volume"))
        for m in re.finditer(r"\b(?:decrease|lower|down|reduce)\b.*\bvolume\b|\bvolume\b.*\b(?:decrease|lower|down|reduce)\b", normalized):
            candidates.append((m.start(), "decrease volume"))

        for m in re.finditer(r"\bopen\s+(youtube|chrome|spotify|whatsapp|notepad|calculator|explorer|vscode|settings)\b", normalized):
            app_name = m.group(1)
            if app_name == "youtube":
                candidates.append((m.start(), "open https://www.youtube.com"))
            else:
                candidates.append((m.start(), f"open {app_name}"))

        for m in re.finditer(r"\bclose\s+([a-z0-9 ]{2,30})\b", normalized):
            app = re.sub(r"\s+", " ", m.group(1)).strip()
            app = re.split(r"\b(?:please|now|thanks|thank you)\b", app, maxsplit=1)[0].strip()
            if app:
                candidates.append((m.start(), f"close {app}"))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[-1][1]

        return normalized

    def _sanitize_windows_live_transcript(self, heard: str) -> str:
        normalized = self._accent_normalize_command(heard or "")
        normalized = self._collapse_repeated_words(normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip().lower()
        if not normalized:
            return ""

        jarvis_index = normalized.rfind("jarvis")
        if jarvis_index != -1:
            tail = normalized[jarvis_index + len("jarvis"):].strip(" ,:-")
            if tail:
                normalized = tail

        normalized = re.sub(r"\b(?:please|can you|could you|would you|jarvis)\b", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return ""

        segments = [re.sub(r"\s+", " ", s).strip() for s in re.split(r"[,.!?;]|\b(?:and then|then)\b", normalized)]
        segments = [s for s in segments if s]
        command_segments = [s for s in segments if self._looks_like_direct_command(s)]
        if command_segments:
            normalized = command_segments[-1]

        normalized = self._canonicalize_windows_command(normalized)

        if not self._looks_like_direct_command(normalized):
            return ""

        return normalized


    def _capture_voice_command(self) -> str:
        # Always-on mode with strict command-intent gating to avoid random chatter triggers.
        heard = self.listen()
        if not heard:
            return ""

        normalized = self._normalize_text_command(heard)
        if normalized in {"exit", "quit", "stop"}:
            return "exit"

        if self._is_unknown_transcript(heard):
            return ""

        if ALWAYS_ON_COMMAND_STRICT and not self._looks_like_direct_command(normalized):
            return ""

        return heard.strip()

    def _handle_alias_confirmation(self, command_text: str) -> bool:
        if not self.pending_alias_suggestion:
            return False

        if self._is_yes_response(command_text):
            spoken = self.pending_alias_suggestion.get("spoken", "")
            suggested = self.pending_alias_suggestion.get("suggested", "")
            if spoken and suggested:
                self.dynamic_aliases[spoken] = suggested
                self._save_dynamic_aliases()
                self.speak(f"Saved alias. {spoken} will open {suggested}.")
                retry = self._open_app(suggested)
                self.speak(retry)
            self.pending_alias_suggestion = None
            return True

        if self._is_no_response(command_text):
            self.speak("Okay, not saving alias.")
            self.pending_alias_suggestion = None
            return True

        self.speak("Please say yes or no.")
        return True

    def _handle_action_confirmation(self, command_text: str) -> bool:
        if not self.pending_action_confirmation:
            return False

        if self._is_yes_response(command_text):
            action = self.pending_action_confirmation.get("action")
            if isinstance(action, dict):
                self.speak("Confirmed.")
                self.execute_pc_action(action)
            self.pending_action_confirmation = None
            return True

        if self._is_no_response(command_text):
            self.speak("Cancelled.")
            self.pending_action_confirmation = None
            return True

        self.speak("Please say yes or no.")
        return True

    def _check_backend_status(self, retries: int = 2, delay_seconds: float = 0.6) -> bool:
        status_url = f"{self.backend_url}/status"
        for attempt in range(max(1, retries)):
            try:
                response = requests.get(status_url, timeout=3)
                response.raise_for_status()
                body = response.json()
                ok = bool(isinstance(body, dict) and body.get("status") == "ok")
                self.backend_reachable = ok
                self._last_backend_check_ts = time.time()
                return ok
            except Exception:
                if attempt < retries - 1:
                    time.sleep(delay_seconds)
        self.backend_reachable = False
        self._last_backend_check_ts = time.time()
        return False

    def _resolve_action_for_command(self, command: str) -> Dict[str, Any]:
        command = self._accent_normalize_command(command)
        system_response = self._handle_system_query(command)
        if system_response:
            return system_response

        now = time.time()
        if self.backend_reachable is None or (now - self._last_backend_check_ts) > 15:
            self._check_backend_status(retries=1, delay_seconds=0.2)

        if self.backend_reachable is False:
            return {
                "action": "type_text",
                "response": "Backend is offline. I can still handle local system commands.",
                "text": "Backend is offline. I can still handle local system commands.",
            }

        try:
            self._update_hud(intent="thinking", action="processing command")
            self._play_chime("thinking")
            if SPOKEN_FILLER_ENABLED:
                self.speak("Sure, let me check that.")
            action = self.send_command(command)
            self.backend_reachable = True
            return action
        except Exception:
            self.backend_reachable = False
            return {
                "action": "type_text",
                "response": "Backend connection failed. Local-only mode is active.",
                "text": "Backend connection failed. Local-only mode is active.",
            }

    def _activate_wake_window(self) -> None:
        self.wake_active_until = time.time() + WAKE_ACTIVE_SECONDS

    def _wake_window_active(self) -> bool:
        return time.time() < self.wake_active_until
    def install_startup(self) -> str:
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup",
        )
        if not startup_dir or not os.path.isdir(startup_dir):
            return "Could not find Windows Startup folder."

        project_dir = os.path.dirname(os.path.abspath(__file__))
        python_exe = os.path.join(project_dir, ".venv", "Scripts", "pythonw.exe")
        if not os.path.isfile(python_exe):
            python_exe = "pythonw"

        backend_script = os.path.join(project_dir, "main.py")
        assistant_script = os.path.join(project_dir, "laptop_assistant.py")
        vbs_path = os.path.join(startup_dir, "jarvis_startup.vbs")
        legacy_bat_path = os.path.join(startup_dir, "jarvis_startup.bat")

        script = (
            'Set WshShell = CreateObject("WScript.Shell")\n'
            f'WshShell.CurrentDirectory = "{project_dir}"\n'
            f'WshShell.Run chr(34) & "{python_exe}" & chr(34) & " " & chr(34) & "{backend_script}" & chr(34), 0, False\n'
            "WScript.Sleep 4000\n"
            f'WshShell.Run chr(34) & "{python_exe}" & chr(34) & " " & chr(34) & "{assistant_script}" & chr(34) & " --background", 0, False\n'
        )

        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(script)

        if os.path.isfile(legacy_bat_path):
            os.remove(legacy_bat_path)

        return f"Startup installed: {vbs_path}"

    def uninstall_startup(self) -> str:
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup",
        )
        bat_path = os.path.join(startup_dir, "jarvis_startup.bat")
        vbs_path = os.path.join(startup_dir, "jarvis_startup.vbs")

        removed_any = False
        for launcher_path in (bat_path, vbs_path):
            if os.path.isfile(launcher_path):
                os.remove(launcher_path)
                removed_any = True

        return "Startup removed." if removed_any else "Startup entry not found."

    def _read_windows_native_text_command(self) -> str:
        if msvcrt is None:
            return input("Windows speech > ").strip()

        print("Windows speech > ", end="", flush=True)
        chars: List[str] = []
        started_at = time.time()
        last_input_at = started_at

        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()

                if ch in {"\r", "\n"}:
                    print("")
                    break

                if ch == "\x03":
                    raise KeyboardInterrupt

                if ch == "\b":
                    if chars:
                        chars.pop()
                        print("\b \b", end="", flush=True)
                    last_input_at = time.time()
                    continue

                if ch in {"\x00", "\xe0"}:
                    try:
                        _ = msvcrt.getwch()
                    except Exception:
                        pass
                    continue

                chars.append(ch)
                print(ch, end="", flush=True)
                last_input_at = time.time()
                continue

            now = time.time()
            if chars and (now - last_input_at) >= WINDOWS_TEXT_IDLE_SECONDS:
                print("")
                break

            if (now - started_at) >= WINDOWS_TEXT_MAX_WAIT_SECONDS:
                if chars:
                    print("")
                return ""

            time.sleep(0.03)

        return re.sub(r"\s+", " ", "".join(chars)).strip()

    def run(self) -> None:
        print(f"Laptop Jarvis started. Backend: {self.backend_url}")
        if self.windows_native_text_mode:
            print("Windows native text mode: dictate/type and it auto-sends after short pause.")
        elif PUSH_TO_TALK_SPACE_ENABLED:
            print("Push-to-talk enabled: hold SPACE to speak, release SPACE to send.")
        else:
            print("Always listening. Speak command directly. Say 'text' to switch to text mode.")
        print("Say/type 'exit' to stop. (Press Ctrl+C to force stop)")
        self._update_hud(intent="startup", action="always listening")
        if not self._check_backend_status(retries=1, delay_seconds=0.2):
            self.speak("Backend or Ollama is not reachable. I will run in local-only mode until it is back.")

        try:
            while True:
                try:
                    if self.windows_native_text_mode:
                        captured = self._read_windows_native_text_command()
                        if captured:
                            print(f"Native transcript > {captured}")
                        cleaned = self._sanitize_windows_live_transcript(captured)
                        if cleaned and cleaned != captured:
                            print(f"Parsed command   > {cleaned}")
                        raw = cleaned or captured
                    elif self.input_mode == "text":
                        raw = input("Text mode > ").strip()
                    else:
                        raw = self._capture_voice_command()

                    if not raw:
                        continue

                    normalized = self._normalize_text_command(raw)
                    if self._is_unknown_transcript(normalized):
                        self.speak("I couldn't catch that. Please repeat.")
                        continue
                    if normalized in {"exit", "quit", "stop"}:
                        self.speak("Stopping Jarvis")
                        break

                    if self.input_mode == "text" and normalized in VOICE_MODE_COMMANDS:
                        if self.windows_native_text_mode:
                            self.speak("Windows speech mode is active. Staying in text mode.")
                        else:
                            self.input_mode = "voice"
                            self.speak("Switched to voice mode")
                            self._update_hud(intent="mode", action="voice")
                        continue

                    if normalized in TEXT_MODE_COMMANDS:
                        self.input_mode = "text"
                        self.speak("Switched to text mode")
                        self._update_hud(intent="mode", action="text")
                        continue

                    if self._handle_alias_confirmation(normalized):
                        continue

                    if self._handle_action_confirmation(normalized):
                        continue

                    self._update_hud(heard=raw, intent="command")

                    try:
                        action = self._resolve_action_for_command(raw)
                        if not TERMINAL_MINIMAL:
                            print("Action JSON:", json.dumps(action, indent=2))
                        self._update_hud(intent=action.get("action", ""), action=str(action))

                        if self._should_gate_low_confidence(action):
                            conf = self.last_recognition_confidence
                            self.pending_action_confirmation = {"action": action, "heard": raw, "confidence": conf}
                            self.speak(
                                f"Low confidence {conf:.2f}. Say yes to confirm or no to cancel."
                            )
                            continue

                        self.execute_pc_action(action)
                    except Exception as exc:
                        self.speak(f"Backend error: {exc}")
                except KeyboardInterrupt:
                    raise
        except KeyboardInterrupt:
            print("\n\nJarvis stopped by user.")
        finally:
            try:
                if self.hud:
                    self.hud.close()
            except Exception:
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis laptop assistant")
    parser.add_argument("--install-startup", action="store_true", help="Install Windows startup launcher")
    parser.add_argument("--uninstall-startup", action="store_true", help="Remove Windows startup launcher")
    parser.add_argument("--background", action="store_true", help="Run without HUD/taskbar UI components")
    args = parser.parse_args()

    client = LaptopJarvisClient(BACKEND_URL, hud_enabled=(not args.background and HUD_ENABLED_DEFAULT))
    if args.install_startup:
        print(client.install_startup())
    elif args.uninstall_startup:
        print(client.uninstall_startup())
    else:
        client.run()




