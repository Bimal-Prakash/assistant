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


class STTGatingMixin:
            def _is_unknown_transcript(self, text: str) -> bool:
                normalized = self._normalize_text_command(text)
                if not normalized:
                    return True
                normalized = normalized.replace("[", "").replace("]", "")
                return normalized in {"unk", "unknown"} or normalized.startswith("unk ") or " unk" in normalized

            def _extract_confidence(self, result_obj: Dict[str, Any]) -> Optional[float]:
                words = result_obj.get("result")
                confidences: List[float] = []
                if isinstance(words, list):
                    for item in words:
                        if not isinstance(item, dict):
                            continue
                        value = item.get("conf")
                        if isinstance(value, (float, int)):
                            confidences.append(float(value))
        
                if confidences:
                    return sum(confidences) / len(confidences)
        
                direct_conf = result_obj.get("conf")
                if isinstance(direct_conf, (float, int)):
                    return float(direct_conf)
        
                fallback_text = str(result_obj.get("text", "") or result_obj.get("partial", "")).strip()
                if fallback_text:
                    # Fallback confidence for models without word-level conf output.
                    return 0.62
                return None

            def _accent_gate_text(self, text: str) -> str:
                normalized = self._normalize_text_command(text)
                fixes = {
                    "played": "play",
                    "plaid": "play",
                    "plaid": "play",
                    "spotty fi": "spotify",
                    "spoti fy": "spotify",
                    "what's app": "whatsapp",
                    "whats app": "whatsapp",
                    "you tube": "youtube",
                    "vs code": "vscode",
                    "crome": "chrome",
                    "chorme": "chrome",
                    "jarvish": "jarvis",
                    "jervis": "jarvis",
                    "dervis": "jarvis",
                }
                for src, dst in fixes.items():
                    normalized = re.sub(rf"\b{re.escape(src)}\b", dst, normalized)
        
                normalized = re.sub(r"^(?:please\s+)?played\s+", "play ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
                return normalized

            def _fuzzy_gate_text(self, text: str) -> str:
                tokens = text.split()
                if not tokens:
                    return text
        
                corrected: List[str] = []
                for token in tokens:
                    base = re.sub(r"[^a-z]", "", token.lower())
                    if len(base) < 3 or base in STT_FUZZY_VOCAB:
                        corrected.append(token)
                        continue
        
                    match = difflib.get_close_matches(base, sorted(STT_FUZZY_VOCAB), n=1, cutoff=STT_FUZZY_TOKEN_THRESHOLD)
                    if match:
                        replacement = match[0]
                        corrected.append(replacement)
                    else:
                        corrected.append(token)
        
                return " ".join(corrected)

            def _command_likelihood_score(self, text: str) -> float:
                normalized = self._normalize_text_command(text)
                if not normalized:
                    return -1.0
        
                tokens = [t for t in normalized.split() if t]
                if not tokens:
                    return -1.0
        
                keyword_hits = sum(1 for t in tokens if t in COMMAND_KEYWORDS)
                keyword_ratio = keyword_hits / float(max(1, len(tokens)))
        
                pattern_bonus = 0.0
                if re.match(r"^(open|close|start|launch|run|play|search|find|send|call|turn|set)\b", normalized):
                    pattern_bonus += 0.35
                if re.search(r"\b(on|off|up|down|next|previous|mute|unmute)\b", normalized):
                    pattern_bonus += 0.2
                if self._has_wake_prefix_text(normalized):
                    pattern_bonus += 0.35
        
                short_noise_penalty = 0.0
                short_tokens = sum(1 for t in tokens if len(t) <= 2)
                if len(tokens) >= 3 and short_tokens / float(len(tokens)) > 0.5:
                    short_noise_penalty = 0.2
        
                return (keyword_ratio * 1.2) + pattern_bonus - short_noise_penalty

            def _select_best_stt_candidate(
                self,
                result_obj: Optional[Dict[str, Any]],
                best_partial: str,
            ) ->tuple[str, Optional[float]]:
                candidates: List[Dict[str, Any]] = []
        
                if isinstance(result_obj, dict):
                    alt = result_obj.get("alternatives")
                    if isinstance(alt, list):
                        for item in alt:
                            if not isinstance(item, dict):
                                continue
                            text_val = self._normalize_text_command(str(item.get("text", "")))
                            if not text_val:
                                continue
                            conf_val = item.get("confidence")
                            confidence = float(conf_val) if isinstance(conf_val, (int, float)) else None
                            candidates.append({"text": text_val, "confidence": confidence})
        
                    main_text = self._normalize_text_command(str(result_obj.get("text", "")))
                    if main_text:
                        candidates.append({"text": main_text, "confidence": self._extract_confidence(result_obj)})
        
                partial_text = self._normalize_text_command(best_partial)
                if partial_text:
                    candidates.append({"text": partial_text, "confidence": None})
        
                if not candidates:
                    return "", None
        
                best_text = ""
                best_conf: Optional[float] = None
                best_score = -999.0
        
                for candidate in candidates:
                    ctext = candidate["text"]
                    cconf = candidate.get("confidence")
                    conf_score = cconf if isinstance(cconf, (int, float)) else 0.45
                    likelihood = self._command_likelihood_score(ctext)
                    total = (conf_score * 1.25) + likelihood
                    if total > best_score:
                        best_score = total
                        best_text = ctext
                        best_conf = float(cconf) if isinstance(cconf, (int, float)) else None
        
                return best_text, best_conf

            def _apply_stt_gates(
                self,
                raw_text: str,
                confidence: Optional[float],
                avg_rms: float,
                speech_energy_frames: int,
                total_frames: int,
            ) -> str:
                text = self._normalize_text_command(raw_text)
                if not text:
                    return ""
        
                if STT_NOISE_GATE_ENABLED:
                    speech_ratio = float(speech_energy_frames) / float(max(1, total_frames))
                    wake_like = self._has_wake_prefix_text(text) or "jarvis" in text
                    if not wake_like:
                        if avg_rms < STT_NOISE_MIN_RMS and (confidence is None or confidence < 0.55):
                            print(f"Noise gate rejected transcript (avg_rms={avg_rms:.1f}).")
                            return ""
                        if speech_ratio < STT_NOISE_MIN_SPEECH_FRAC and (confidence is None or confidence < 0.60):
                            print(f"Noise gate rejected transcript (speech_ratio={speech_ratio:.2f}).")
                            return ""
        
                text = self._collapse_repeated_words(text)
        
                if STT_ACCENT_GATE_ENABLED:
                    text = self._accent_gate_text(text)
        
                if STT_FUZZY_GATE_ENABLED:
                    text = self._fuzzy_gate_text(text)
        
                text = self._semantic_normalize_command(text)
                text = re.sub(r"\s+", " ", text).strip(" ,.-")
                return text

