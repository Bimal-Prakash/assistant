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

try:
    import winsound
except Exception:
    winsound = None
try:
    # pyrefly: ignore [missing-import]
    import pyttsx3
except Exception:
    pyttsx3 = None

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class TTSMixin:
        _tts_lock = threading.Lock()

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

        def _speak_blocking(self, text: str) -> None:
            """Actual TTS playback — runs in background thread."""
            with self._tts_lock:
                if self.tts_mode == "edge":
                    if self._speak_with_edge_tts(text):
                        return

                if self.tts_mode == "pyttsx3" and self.tts:
                    try:
                        self.tts.say(text)
                        self.tts.runAndWait()
                    except Exception:
                        pass

        def speak(self, text: str) -> None:
            if not text:
                return
            print(f"Jarvis: {text}")
            self._update_hud(action=text)
            # Fire-and-forget: TTS runs in background so actions start immediately
            threading.Thread(target=self._speak_blocking, args=(text,), daemon=True).start()

