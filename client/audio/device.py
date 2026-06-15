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
import math
import io
import wave
from urllib.parse import quote_plus
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
import difflib

from client.config import *

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

try:
    import winsound
except Exception:
    winsound = None
class AudioDeviceMixin:
        def _play_chime(self, kind: str = "wake") -> None:
            if winsound is None:
                return
            try:
                if kind == "thinking":
                    winsound.MessageBeep(winsound.MB_ICONQUESTION)
                else:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        def _apply_input_gain(self, frame: List[int]) -> List[int]:
            if not frame:
                return frame
            if not STT_AGC_ENABLED:
                return frame
    
            rms = self._frame_rms(frame)
            if rms < 20:
                return frame
    
            desired_gain = STT_AGC_TARGET_RMS / max(rms, 1.0)
            desired_gain = min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, desired_gain))
            self._input_gain = (self._input_gain * 0.85) + (desired_gain * 0.15)
            gain = min(STT_AGC_MAX_GAIN, max(STT_AGC_MIN_GAIN, self._input_gain))
    
            adjusted: List[int] = []
            for sample in frame:
                value = int(sample * gain)
                if value > 32767:
                    value = 32767
                elif value < -32768:
                    value = -32768
                adjusted.append(value)
            return adjusted

        def _available_input_devices(self) -> List[str]:
            if pvrecorder is None:
                return []
            try:
                devices = pvrecorder.PvRecorder.get_available_devices()
                return list(devices) if isinstance(devices, list) else []
            except Exception:
                return []

        def _open_recorder_with_fallback(self) -> Any:
            if pvrecorder is None:
                raise RuntimeError("PvRecorder is unavailable")
    
            devices = self._available_input_devices()
            candidates: List[int] = []
    
            if self._mic_device_index_override is not None:
                candidates.append(self._mic_device_index_override)
            elif self._active_mic_device_index is not None:
                candidates.append(self._active_mic_device_index)
                if self._active_mic_device_index != -1:
                    candidates.append(-1)
            else:
                # On some Windows setups after unplugging headsets, explicit input index is more reliable than -1 default routing.
                if devices:
                    candidates.append(0)
                candidates.append(-1)
    
            scan_limit = min(len(devices), 8)
            for idx in range(scan_limit):
                if idx not in candidates:
                    candidates.append(idx)
    
            last_exc: Optional[Exception] = None
            for idx in candidates:
                try:
                    recorder = pvrecorder.PvRecorder(device_index=idx, frame_length=512)
                    recorder.start()
                    if idx != self._active_mic_device_index:
                        label = "default" if idx == -1 else (devices[idx] if 0 <= idx < len(devices) else f"device {idx}")
                        if not TERMINAL_MINIMAL:
                            print(f"   Using mic input: {label}")
                    self._active_mic_device_index = idx
                    return recorder
                except Exception as exc:
                    last_exc = exc
                    continue
    
            raise RuntimeError(f"Could not open any microphone input: {last_exc}")

        def _maybe_rotate_mic_device(self) -> None:
            if self._mic_device_index_override is not None:
                return
            devices = self._available_input_devices()
            if not devices or len(devices) <= 1:
                return
    
            if self._active_mic_device_index is None or self._active_mic_device_index < 0:
                self._active_mic_device_index = 0
                return
    
            self._active_mic_device_index = (self._active_mic_device_index + 1) % len(devices)
            try:
                if not TERMINAL_MINIMAL:
                    print(f"   Rotating mic input to: {devices[self._active_mic_device_index]}")
            except Exception:
                pass

        def _pyaudio_input_device_index(self, pa: Any) -> Optional[int]:
            if self._mic_device_index_override is not None:
                return self._mic_device_index_override
            try:
                default_idx = pa.get_default_input_device_info().get("index")
                return int(default_idx)
            except Exception:
                pass
            try:
                count = int(pa.get_device_count())
                for i in range(count):
                    info = pa.get_device_info_by_index(i)
                    if int(info.get("maxInputChannels", 0)) > 0:
                        return i
            except Exception:
                pass
            return None

        def _rms_from_pcm16(self, pcm_bytes: bytes) -> float:
            if not pcm_bytes:
                return 0.0
            samples = struct.unpack("<%dh" % (len(pcm_bytes) // 2), pcm_bytes)
            if not samples:
                return 0.0
            power = sum(float(s) * float(s) for s in samples) / float(len(samples))
            return math.sqrt(power)

        def _pcm16_to_wav_bytes(self, pcm: bytes, sample_rate: int) -> bytes:
            if not pcm:
                return b""
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm)
            return buf.getvalue()

        def _frame_rms(self, frame: List[int]) -> float:
            if not frame:
                return 0.0
            power = sum(float(sample) * float(sample) for sample in frame) / float(len(frame))
            return math.sqrt(power)

