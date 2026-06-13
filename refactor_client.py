import os
import ast

base_dir = r"C:\Bimal\Project\assistant"
client_dir = os.path.join(base_dir, "client")

# Define directories
audio_dir = os.path.join(client_dir, "audio")
nlp_dir = os.path.join(client_dir, "nlp")
system_dir = os.path.join(client_dir, "system")
core_dir = os.path.join(client_dir, "core")

for d in [audio_dir, nlp_dir, system_dir, core_dir]:
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("")

with open(os.path.join(client_dir, "app.py"), "r", encoding="utf-8") as f:
    app_code = f.read()

lines = app_code.splitlines()

def get_source_segment(node):
    if not hasattr(node, 'end_lineno'):
        return ""
    start = node.lineno - 1
    end = node.end_lineno
    return "\n".join(lines[start:end])

tree = ast.parse(app_code)

class_node = None
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "LaptopJarvisClient":
        class_node = node
        break

if not class_node:
    raise ValueError("LaptopJarvisClient not found")

methods = {}
for node in class_node.body:
    if isinstance(node, ast.FunctionDef):
        methods[node.name] = get_source_segment(node)

# Categorize methods
device_methods = ["_play_chime", "_apply_input_gain", "_available_input_devices", "_open_recorder_with_fallback", "_maybe_rotate_mic_device", "_pyaudio_input_device_index", "_rms_from_pcm16", "_pcm16_to_wav_bytes", "_frame_rms"]
stt_methods = ["_infer_whisper_repo_id", "_resolve_model_source", "_resolve_whisper_model_source", "_init_whisper_model", "_init_whisper_verify_model", "_listen_with_whisper_streaming", "_ensure_vosk_model_loaded", "_load_vosk_model", "_create_kaldi_recognizer", "_reset_recognizer", "_listen_with_windows_speech", "_transcribe_with_assemblyai", "_listen_with_assemblyai", "listen", "_capture_voice_command", "_read_windows_native_text_command"]
tts_methods = ["_init_tts_engine", "_speak_with_edge_tts", "speak"]
nlp_methods = ["_stt_profile_key", "_load_stt_calibration_profile", "_save_stt_calibration_profile", "_apply_stt_calibration_profile", "_persist_stt_calibration", "_normalize_text_command", "_is_unknown_transcript", "_normalize_wake_probe", "_has_wake_prefix_text", "_is_wake_only_text", "_extract_confidence", "_collapse_repeated_words", "_accent_gate_text", "_fuzzy_gate_text", "_semantic_normalize_command", "_command_likelihood_score", "_select_best_stt_candidate", "_apply_stt_gates", "strip_wake_word", "_canonicalize_windows_command", "_sanitize_windows_live_transcript"]
system_methods = ["_suggest_app_name", "_open_app", "_close_app", "_handle_post_open_action", "_focus_spotify_window", "_spotify_search_and_play", "_spotify_like_current_song", "_find_start_menu_app_id", "_get_start_apps", "_find_start_menu_shortcut", "_get_start_menu_shortcuts", "install_startup", "uninstall_startup"]
core_methods = ["__init__", "_update_hud", "_is_yes_response", "_is_no_response", "_is_risky_action", "_should_gate_low_confidence", "_load_dynamic_aliases", "_save_dynamic_aliases", "_is_space_pressed", "_wait_until_space_pressed", "send_command", "_handle_system_query", "_is_quiet_success_message", "execute_pc_action", "_looks_like_direct_command", "_handle_alias_confirmation", "_handle_action_confirmation", "_check_backend_status", "_resolve_action_for_command", "_activate_wake_window", "_wake_window_active", "run"]

# Build Mixins
def build_mixin(name, methods_list):
    code = f"class {name}:\n"
    has_method = False
    for m in methods_list:
        if m in methods:
            has_method = True
            # Indent the method
            method_code = methods[m]
            code += "    " + method_code.replace("\n", "\n    ") + "\n\n"
    if not has_method:
        code += "    pass\n"
    return code

# Generate the files
import_header = """import os
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
"""

device_code = import_header + "\n" + build_mixin("AudioDeviceMixin", device_methods)
stt_code = import_header + "\n" + build_mixin("STTMixin", stt_methods)
tts_code = import_header + "\n" + build_mixin("TTSMixin", tts_methods)
nlp_code = import_header + "\n" + build_mixin("NLPMixin", nlp_methods)
system_code = import_header + "\n" + build_mixin("SystemAppMixin", system_methods)
core_code = import_header + "\n" + build_mixin("CoreClientMixin", core_methods)

with open(os.path.join(audio_dir, "device.py"), "w", encoding="utf-8") as f: f.write(device_code)
with open(os.path.join(audio_dir, "stt.py"), "w", encoding="utf-8") as f: f.write(stt_code)
with open(os.path.join(audio_dir, "tts.py"), "w", encoding="utf-8") as f: f.write(tts_code)
with open(os.path.join(nlp_dir, "processing.py"), "w", encoding="utf-8") as f: f.write(nlp_code)
with open(os.path.join(system_dir, "apps.py"), "w", encoding="utf-8") as f: f.write(system_code)
with open(os.path.join(core_dir, "loop.py"), "w", encoding="utf-8") as f: f.write(core_code)

# New app.py
new_app_code = """from client.config import *
from client.ui import StatusHud
from client.audio.device import AudioDeviceMixin
from client.audio.stt import STTMixin
from client.audio.tts import TTSMixin
from client.nlp.processing import NLPMixin
from client.system.apps import SystemAppMixin
from client.core.loop import CoreClientMixin

class LaptopJarvisClient(AudioDeviceMixin, STTMixin, TTSMixin, NLPMixin, SystemAppMixin, CoreClientMixin):
    pass
"""

with open(os.path.join(client_dir, "app.py"), "w", encoding="utf-8") as f:
    f.write(new_app_code)

print("Client refactoring using Mixins completed successfully!")
