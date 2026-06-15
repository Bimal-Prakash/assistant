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

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class WindowsSTTMixin:
            def _listen_with_windows_speech(self) -> Optional[str]:
                timeout_seconds = max(2, WINDOWS_STT_TIMEOUT_SECONDS)
                ps_script = """
        $ErrorActionPreference = 'Stop'
        Add-Type -AssemblyName System.Speech
        
        $engine = $null
        try {
            $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
        } catch {
            try {
                $culture = [System.Globalization.CultureInfo]::CurrentUICulture
                $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
            } catch {
                $engine = $null
            }
        }
        
        if ($engine -eq $null) {
            $recognizers = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
            if ($recognizers -and $recognizers.Count -gt 0) {
                $culture = $recognizers[0].Culture
                $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
            }
        }
        
        if ($engine -eq $null) {
            Write-Output 'ERROR||Could not initialize Windows speech recognizer'
            exit 2
        }
        
        try {
            $engine.SetInputToDefaultAudioDevice()
            $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
            $result = $engine.Recognize([TimeSpan]::FromSeconds(__TIMEOUT_SECONDS__))
            if ($result -ne $null) {
                $text = ($result.Text -replace '\\s+', ' ').Trim()
                if ($text) {
                    $confidence = [math]::Round($result.Confidence, 3)
                    Write-Output ($text + '||' + $confidence)
                }
            }
        } catch {
            Write-Output ('ERROR||' + $_.Exception.Message)
            exit 3
        } finally {
            try { $engine.Dispose() } catch {}
        }
        """
                ps_script = ps_script.replace("__TIMEOUT_SECONDS__", str(timeout_seconds))
        
                try:
                    proc = subprocess.run(
                        ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds + 5,
                    )
                except Exception as exc:
                    if not TERMINAL_MINIMAL:
                        print(f"[windows stt error] {exc}")
                    return None
        
                output = (proc.stdout or "").strip()
                if not output:
                    if proc.returncode != 0 and not TERMINAL_MINIMAL:
                        stderr_text = (proc.stderr or "").strip()
                        if stderr_text:
                            print(f"[windows stt error] {stderr_text}")
                    return ""
        
                line = output.splitlines()[-1].strip()
                if not line:
                    return ""
        
                if line.startswith("ERROR||"):
                    if not TERMINAL_MINIMAL:
                        print(f"[windows stt error] {line.split('||', 1)[1].strip()}")
                    return ""
        
                heard_text = line
                confidence = None
                if "||" in line:
                    heard_text, confidence_raw = line.rsplit("||", 1)
                    heard_text = heard_text.strip()
                    try:
                        confidence = float(confidence_raw.strip())
                    except Exception:
                        confidence = None
        
                if confidence is not None:
                    self.last_recognition_confidence = confidence
                    if confidence < WINDOWS_STT_MIN_CONFIDENCE:
                        return ""
        
                return heard_text

