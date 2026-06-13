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
import webbrowser
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

class HeuristicsMixin:
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

