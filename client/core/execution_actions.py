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

class ActionExecutionMixin:
                def _sanitize_text(self, text: str) -> str:
                    if not text:
                        return text
                    # Strip markdown formatting like quotes, asterisks, bold, etc.
                    text = text.replace('"', '').replace('*', '')
                    return text.strip()

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

                    if action_name == "minimize_app":
                        app_name = str(action.get("app", "")).strip()
                        if app_name:
                            min_result = getattr(self, "_minimize_app", lambda x: "Minimize not supported")(app_name)
                            if min_result.startswith("Minimizing "):
                                return
                            else:
                                self.speak(min_result)
                            return
                        self.speak("App name missing")
                        return
            
                    if action_name == "send_whatsapp":
                        phone = str(action.get("phone", "")).strip()
                        message = self._sanitize_text(str(action.get("message", "")).strip())
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
                        msg = action.get("response") or result
                        if msg and not self._is_quiet_success_message(msg):
                            self.speak(msg)
                        if result and result != action.get("response"):
                            print(result)
                        return
            
                    agentic_methods = {
                        "maximize_app": "_maximize_app",
                        "restore_app": "_restore_app",
                        "focus_app": "_focus_app",
                        "snap_window": "_snap_window",
                        "hide_all_windows": "_hide_all_windows",
                        "read_clipboard": "_read_clipboard",
                        "write_clipboard": "_write_clipboard",
                        "press_shortcut": "_press_shortcut",
                        "check_performance": "_check_performance",
                        "lock_pc": "_lock_pc",
                        "empty_recycle_bin": "_empty_recycle_bin",
                        "take_screenshot": "_take_screenshot",
                        "show_notification": "_show_notification",
                        "set_timer": "_set_timer",
                        "open_folder": "_open_folder",
                        "search_files": "_search_files",
                        "whatsapp_call": "_whatsapp_call"
                    }
                    if action_name in agentic_methods:
                        method_name = agentic_methods[action_name]
                        method = getattr(self, method_name, lambda *args, **kwargs: "Feature not available")
                        
                        kwargs = {}
                        if action_name in ["maximize_app", "restore_app", "focus_app"]:
                            kwargs["app_name"] = str(action.get("app", "")).strip()
                        elif action_name == "snap_window":
                            kwargs["app_name"] = str(action.get("app", "")).strip()
                            kwargs["direction"] = str(action.get("direction", "")).strip()
                        elif action_name == "write_clipboard":
                            kwargs["text"] = self._sanitize_text(str(action.get("text", "")))
                        elif action_name == "press_shortcut":
                            kwargs["shortcut"] = str(action.get("shortcut", "")).strip()
                        elif action_name == "show_notification":
                            kwargs["title"] = self._sanitize_text(str(action.get("title", "")))
                            kwargs["message"] = self._sanitize_text(str(action.get("message", "")))
                        elif action_name == "set_timer":
                            kwargs["seconds"] = int(action.get("seconds", 0))
                            kwargs["label"] = self._sanitize_text(str(action.get("label", "")))
                        elif action_name == "open_folder":
                            kwargs["folder_path"] = str(action.get("folder_path", "")).strip()
                        elif action_name == "search_files":
                            kwargs["query"] = self._sanitize_text(str(action.get("query", "")))
                        elif action_name == "whatsapp_call":
                            kwargs["contact_name"] = self._sanitize_text(str(action.get("contact_name", "")))
                            kwargs["call_type"] = str(action.get("call_type", "audio")).strip()
                        
                        result = method(**kwargs)
                        if result and not self._is_quiet_success_message(result):
                            self.speak(result)
                        return

                    if action_name == "type_text":
                        message = str(action.get("response") or action.get("text") or "Okay")
                        message = self._sanitize_text(message)
                        if not self._is_quiet_success_message(message):
                            self.speak(message)
                        return
            
                    # PC control actions are executed on backend and returned as type_text.
                    message = str(action.get("response") or "Done")
                    if not self._is_quiet_success_message(message):
                        self.speak(message)

