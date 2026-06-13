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

class WindowMixin:
            def _activate_wake_window(self) -> None:
                self.wake_active_until = time.time() + WAKE_ACTIVE_SECONDS

            def _wake_window_active(self) -> bool:
                return time.time() < self.wake_active_until

