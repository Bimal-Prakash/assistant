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

class WakeWordMixin:
            def _normalize_wake_probe(self, text: str) -> str:
                normalized = self._normalize_text_command(text)
                if not normalized:
                    return ""
        
                substitutions = {
                    "jarvish": "jarvis",
                    "jarvees": "jarvis",
                    "jarviss": "jarvis",
                    "jervis": "jarvis",
                    "dervis": "jarvis",
                    "jarvice": "jarvis",
                    "jarbis": "jarvis",
                    "he jarvis": "hey jarvis",
                    "hi jarvish": "hi jarvis",
                    "hey jarviss": "hey jarvis",
                }
                for src, dst in substitutions.items():
                    normalized = re.sub(rf"\b{re.escape(src)}\b", dst, normalized)
        
                normalized = re.sub(r"\s+", " ", normalized).strip()
                return normalized

            def _has_wake_prefix_text(self, text: str) -> bool:
                normalized = self._normalize_wake_probe(text)
                if not normalized:
                    return False
        
                if normalized == "jarvis" or normalized.startswith("jarvis "):
                    return True
        
                wake_candidates = [self._normalize_wake_probe(w) for w in (list(WAKE_WORDS) + list(WAKE_WORD_VARIANTS))]
                for wake in wake_candidates:
                    if wake and normalized.startswith(wake):
                        return True
        
                if not ACCENT_TOLERANT_MODE:
                    return False
        
                words = normalized.split()
                if len(words) < 2:
                    return False
        
                if words[0] not in WAKE_LEAD_TOKENS:
                    return False
        
                probe_values = [" ".join(words[:2])]
                if len(words) >= 3:
                    probe_values.append(" ".join(words[:3]))
        
                for probe in probe_values:
                    # Reject fuzzy wake when transcript does not even resemble "jarvis" token.
                    if not any(token in probe for token in ("jar", "jarv", "jerv")):
                        continue
                    for wake in wake_candidates:
                        if wake and difflib.SequenceMatcher(None, probe, wake).ratio() >= WAKE_FUZZY_THRESHOLD:
                            return True
                return False

            def _is_wake_only_text(self, text: str) -> bool:
                return self._has_wake_prefix_text(text) and not self.strip_wake_word(text)

            def strip_wake_word(self, text: str) -> str:
                t = text.strip()
                normalized = self._normalize_wake_probe(t)
                if not normalized:
                    return ""
        
                if normalized == "jarvis":
                    return ""
                if normalized.startswith("jarvis "):
                    return " ".join(t.split()[1:]).lstrip(" ,:-").strip()
        
                wake_candidates = [self._normalize_wake_probe(w) for w in (list(WAKE_WORDS) + list(WAKE_WORD_VARIANTS))]
        
                # Exact prefix detection first.
                for wake in wake_candidates:
                    if wake and normalized.startswith(wake):
                        word_count = len(wake.split())
                        remainder = " ".join(t.split()[word_count:])
                        return remainder.lstrip(" ,:-").strip()
        
                # Fuzzy prefix detection for accent/mishearing tolerance.
                if ACCENT_TOLERANT_MODE:
                    words = t.split()
                    if len(words) >= 2:
                        first_token = self._normalize_text_command(words[0])
                        if first_token not in WAKE_LEAD_TOKENS:
                            return ""
                        first_two = self._normalize_wake_probe(" ".join(words[:2]))
                        if any(token in first_two for token in ("jar", "jarv", "jerv")):
                            for wake in wake_candidates:
                                if wake and difflib.SequenceMatcher(None, first_two, wake).ratio() >= WAKE_FUZZY_THRESHOLD:
                                    remainder = " ".join(words[2:])
                                    return remainder.lstrip(" ,:-").strip()
        
                return ""

