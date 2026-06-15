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

class NormalizationMixin:
            def _normalize_text_command(self, text: str) -> str:
                return re.sub(r"\s+", " ", (text or "").strip().lower())

            def _collapse_repeated_words(self, text: str) -> str:
                return re.sub(r"\b(\w+)(?:\s+\1){1,}\b", r"\1", text)

            def _semantic_normalize_command(self, text: str) -> str:
                normalized = self._normalize_text_command(text)
                if not normalized:
                    return ""
        
                normalized = re.sub(r"^(?:please\s+)?(?:can you|could you|would you|kindly)\s+", "", normalized)
                normalized = re.sub(r"\bplease\b", "", normalized)
                normalized = re.sub(r"\bswitch\s+on\b", "turn on", normalized)
                normalized = re.sub(r"\bswitch\s+off\b", "turn off", normalized)
                normalized = re.sub(r"\bset\s+the\s+", "set ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
                return normalized

            def _canonicalize_windows_command(self, normalized: str) -> str:
                candidates = []
        
                for m in re.finditer(r"\b(previous(?:\s+(?:song|track))?|back\s+song|previous)\b", normalized):
                    candidates.append((m.start(), "previous song"))
                for m in re.finditer(r"\b(next(?:\s+(?:song|track))?|skip|next)\b", normalized):
                    candidates.append((m.start(), "next song"))
                for m in re.finditer(r"\b(pause|resume|play)\b", normalized):
                    token = m.group(1)
                    mapped = "resume" if token == "resume" else token
                    candidates.append((m.start(), mapped))
        
                for m in re.finditer(r"\b(?:increase|raise|up|higher)\b.*\bbrightness\b|\bbrightness\b.*\b(?:increase|raise|up|higher)\b", normalized):
                    candidates.append((m.start(), "increase brightness"))
                for m in re.finditer(r"\b(?:decrease|lower|down|reduce)\b.*\bbrightness\b|\bbrightness\b.*\b(?:decrease|lower|down|reduce)\b", normalized):
                    candidates.append((m.start(), "decrease brightness"))
        
                for m in re.finditer(r"\b(?:increase|raise|up|higher)\b.*\bvolume\b|\bvolume\b.*\b(?:increase|raise|up|higher)\b", normalized):
                    candidates.append((m.start(), "increase volume"))
                for m in re.finditer(r"\b(?:decrease|lower|down|reduce)\b.*\bvolume\b|\bvolume\b.*\b(?:decrease|lower|down|reduce)\b", normalized):
                    candidates.append((m.start(), "decrease volume"))
        
                for m in re.finditer(r"\bopen\s+(youtube|chrome|spotify|whatsapp|notepad|calculator|explorer|vscode|settings)\b", normalized):
                    app_name = m.group(1)
                    if app_name == "youtube":
                        candidates.append((m.start(), "open https://www.youtube.com"))
                    else:
                        candidates.append((m.start(), f"open {app_name}"))
        
                for m in re.finditer(r"\bclose\s+([a-z0-9 ]{2,30})\b", normalized):
                    app = re.sub(r"\s+", " ", m.group(1)).strip()
                    app = re.split(r"\b(?:please|now|thanks|thank you)\b", app, maxsplit=1)[0].strip()
                    if app:
                        candidates.append((m.start(), f"close {app}"))
        
                if candidates:
                    candidates.sort(key=lambda x: x[0])
                    return candidates[-1][1]
        
                return normalized

            def _sanitize_windows_live_transcript(self, heard: str) -> str:
                normalized = heard or ""
                normalized = self._collapse_repeated_words(normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip().lower()
                if not normalized:
                    return ""
        
                jarvis_index = normalized.rfind("jarvis")
                if jarvis_index != -1:
                    tail = normalized[jarvis_index + len("jarvis"):].strip(" ,:-")
                    if tail:
                        normalized = tail
        
                normalized = re.sub(r"\b(?:please|can you|could you|would you|jarvis)\b", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not normalized:
                    return ""
        
                segments = [re.sub(r"\s+", " ", s).strip() for s in re.split(r"[,.!?;]|\b(?:and then|then)\b", normalized)]
                segments = [s for s in segments if s]
                command_segments = [s for s in segments if self._looks_like_direct_command(s)]
                if command_segments:
                    normalized = command_segments[-1]
        
                normalized = self._canonicalize_windows_command(normalized)
        
                if not self._looks_like_direct_command(normalized):
                    return ""
        
                return normalized

