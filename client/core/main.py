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
    # pyrefly: ignore [missing-import]
    import pyttsx3
except Exception:
    pyttsx3 = None
try:
    # pyrefly: ignore [missing-import]
    import numpy as np
except Exception:
    np = None



class MainLoopMixin:
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

                if self.stt_engine not in {"windows"}:
                    print(f"Warning: Unknown STT engine '{self.stt_engine}', forcing 'windows' text mode.")
                    self.stt_engine = "windows"
                if self.stt_engine == "windows":
                    self.input_mode = "text"
                    self.windows_native_text_mode = True

                self._input_gain = 1.0
                self._stt_profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), STT_PROFILE_FILE_NAME)
                self._machine_name = (os.getenv("COMPUTERNAME") or "pc").strip().lower() or "pc"
                self._stt_profile_cache: Dict[str, Dict[str, Any]] = {}
                self._load_stt_calibration_profile()
                self._apply_stt_calibration_profile()

                self.command_queue = queue.Queue()
                self._worker_thread = threading.Thread(target=self._command_worker_loop, daemon=True)
                self._worker_thread.start()

            def _command_worker_loop(self) -> None:
                while True:
                    cmd_raw, conf = self.command_queue.get()
                    if cmd_raw is None:
                        break
                    try:
                        action = self._resolve_action_for_command(cmd_raw)
                        if not TERMINAL_MINIMAL:
                            print(f"\n[Worker] Action JSON: {json.dumps(action, indent=2)}\nWindows speech > ", end="", flush=True)
                        self._update_hud(intent=action.get("action", ""), action=str(action))

                        if self._should_gate_low_confidence(action):
                            self.pending_action_confirmation = {"action": action, "heard": cmd_raw, "confidence": conf}
                            self.speak(
                                f"Low confidence {conf:.2f} for '{cmd_raw}'. Say yes to confirm or no to cancel."
                            )
                            continue

                        self.execute_pc_action(action)
                    except Exception as exc:
                        self.speak(f"Backend error: {exc}")
                    finally:
                        self.command_queue.task_done()

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
        
                            if normalized in {"cancel", "abort", "nevermind", "ignore"}:
                                with self.command_queue.mutex:
                                    self.command_queue.queue.clear()
                                self.speak("Cancelled pending actions.")
                                continue
        
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
        
                            # Queue the command for the background worker instead of blocking or naive threading
                            self.command_queue.put((raw, self.last_recognition_confidence))
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

