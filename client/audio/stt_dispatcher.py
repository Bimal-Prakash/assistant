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
    # pyrefly: ignore [missing-import]
    import pyttsx3
except Exception:
    pyttsx3 = None


class STTDispatcherMixin:
            def listen(self) -> str:
                self.last_recognition_confidence = None
        
                if self.stt_engine == "windows":
                    windows_result = self._listen_with_windows_speech()
                    if windows_result is not None:
                        return windows_result

                # Only fallback to text input if the chosen engine is completely unavailable
                typed = input("Type command: ").strip()
                self._update_hud(heard=typed, intent="typed")
                return typed

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

