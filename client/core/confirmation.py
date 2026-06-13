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

class ConfirmationMixin:
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

