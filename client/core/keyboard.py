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
import ctypes
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

class KeyboardMixin:
            def _is_space_pressed(self) -> bool:
                try:
                    return bool(ctypes.windll.user32.GetAsyncKeyState(0x20) & 0x8000)
                except Exception:
                    return False

            def _wait_until_space_pressed(self) -> None:
                while True:
                    if self._is_space_pressed():
                        return
                    time.sleep(max(0.005, PUSH_TO_TALK_POLL_SECONDS))
