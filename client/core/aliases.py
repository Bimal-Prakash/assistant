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

class AliasesMixin:
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

