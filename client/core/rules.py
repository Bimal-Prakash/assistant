import os
import re
import json
import time
import queue
import shutil
import struct
import tempfile
import threading
import subprocess
from urllib.parse import quote_plus
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
import difflib

from client.config import *
from client.ui import StatusHud

try:
    import msvcrt
except Exception:
    msvcrt = None
try:
    import pyaudio
except Exception:
    pyaudio = None
try:
    import pyautogui
except Exception:
    pyautogui = None
try:
    import pyttsx3
except Exception:
    pyttsx3 = None
try:
    import numpy as np
except Exception:
    np = None

if not SKIP_INTERNAL_STT_IMPORTS:
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        snapshot_download = None
    try:
        from faster_whisper import WhisperModel
    except Exception:
        WhisperModel = None
    try:
        from vosk import Model, KaldiRecognizer, SetLogLevel
        import pvrecorder
    except Exception:
        Model = KaldiRecognizer = SetLogLevel = pvrecorder = None
else:
    snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class RulesMixin:
            def _is_yes_response(self, text: str) -> bool:
                return self._normalize_text_command(text) in YES_COMMANDS

            def _is_no_response(self, text: str) -> bool:
                return self._normalize_text_command(text) in NO_COMMANDS

            def _is_risky_action(self, action: Dict[str, Any]) -> bool:
                action_name = str(action.get("action", "")).strip().lower()
                return action_name in LOW_CONFIDENCE_RISKY_ACTIONS

            def _should_gate_low_confidence(self, action: Dict[str, Any]) -> bool:
                if not self._is_risky_action(action):
                    return False
                confidence = self.last_recognition_confidence
                return confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD

            def _is_quiet_success_message(self, message: str) -> bool:
                text = re.sub(r"\s+", " ", (message or "").strip().lower())
                if not text:
                    return False
                if text.startswith(("i could not", "could not", "failed", "backend", "please ", "do you ", "which ")):
                    return False
                if "error" in text or "not found" in text or "unsupported" in text:
                    return False
                
                quiet_prefixes = (
                    "opening ", "closing ", "playing ", "searching ", "toggling ", 
                    "skipping ", "going to previous", "increasing ", "decreasing ", 
                    "setting pc ", "setting brightness", "setting volume", "adjusting ", 
                    "muting ", "opened ", "liked ", "focused ", "snapping ", "maximized ", 
                    "minimized ", "restored ", "locked ", "emptied ", "took ", "showing ", 
                    "set timer", "searched ", "executing ", "done", "okay", "sure", "got it",
                    "working on it"
                )
                return text.startswith(quiet_prefixes) or text in ["ok", "done.", "okay."]

