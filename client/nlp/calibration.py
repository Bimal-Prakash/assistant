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
    import pyttsx3
except Exception:
    pyttsx3 = None
try:
    import numpy as np
except Exception:
    np = None

class CalibrationMixin:
            def _stt_profile_key(self) -> str:
                model_label = os.path.basename(self.vosk_model_name.strip()) if self.vosk_model_name else "default-model"
                return f"{self._machine_name}:{model_label}"

            def _load_stt_calibration_profile(self) -> None:
                if not STT_CALIBRATION_ENABLED:
                    return
                if not os.path.exists(self._stt_profile_path):
                    self._stt_profile_cache = {}
                    return
                try:
                    with open(self._stt_profile_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._stt_profile_cache = data if isinstance(data, dict) else {}
                except Exception:
                    self._stt_profile_cache = {}

            def _save_stt_calibration_profile(self) -> None:
                if not STT_CALIBRATION_ENABLED:
                    return
                try:
                    with open(self._stt_profile_path, "w", encoding="utf-8") as f:
                        json.dump(self._stt_profile_cache, f, indent=2)
                except Exception:
                    pass

            def _apply_stt_calibration_profile(self) -> None:
                if not STT_CALIBRATION_ENABLED:
                    return
                profile = self._stt_profile_cache.get(self._stt_profile_key(), {})
                if not isinstance(profile, dict):
                    return
        
                noise_floor = profile.get("noise_floor_rms")
                if isinstance(noise_floor, (int, float)):
                    self._noise_floor_rms = max(STT_NOISE_MIN_RMS, float(noise_floor))
        
                input_gain = profile.get("input_gain")
                if isinstance(input_gain, (int, float)):
                    self._input_gain = min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, float(input_gain)))

            def _persist_stt_calibration(self, noise_floor_rms: float, speech_rms: float, input_gain: float, frames: int) -> None:
                if not STT_CALIBRATION_ENABLED:
                    return
                if frames < STT_CALIBRATION_MIN_UTTERANCE_FRAMES:
                    return
        
                key = self._stt_profile_key()
                prev = self._stt_profile_cache.get(key, {})
                if not isinstance(prev, dict):
                    prev = {}
        
                prev_count = int(prev.get("samples", 0)) if isinstance(prev.get("samples", 0), int) else 0
                new_count = prev_count + 1
        
                prev_noise = float(prev.get("noise_floor_rms", STT_NOISE_MIN_RMS))
                prev_speech = float(prev.get("speech_rms", max(STT_AGC_TARGET_RMS, STT_NOISE_MIN_RMS)))
                prev_gain = float(prev.get("input_gain", 1.0))
        
                merged_noise = (prev_noise * prev_count + float(noise_floor_rms)) / float(new_count)
                merged_speech = (prev_speech * prev_count + float(speech_rms)) / float(new_count)
                merged_gain = (prev_gain * prev_count + float(input_gain)) / float(new_count)
        
                self._stt_profile_cache[key] = {
                    "samples": new_count,
                    "noise_floor_rms": max(STT_NOISE_MIN_RMS, merged_noise),
                    "speech_rms": max(STT_NOISE_MIN_RMS, merged_speech),
                    "input_gain": min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, merged_gain)),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
                self._save_stt_calibration_profile()

