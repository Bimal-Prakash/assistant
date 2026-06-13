import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.memory")

class MemoryExtractionMixin:
        def _extract_facts(self, text: str) -> Dict[str, str]:
            msg = (text or "").strip()
            if not msg:
                return {}
    
            lowered = msg.lower()
            facts: Dict[str, str] = {}
    
            name_match = re.search(r"\bmy name is\s+([a-zA-Z][a-zA-Z\s\-']{1,60})", msg, flags=re.IGNORECASE)
            if name_match:
                facts["name"] = name_match.group(1).strip()
    
            city_match = re.search(r"\bi (?:live in|am from)\s+([a-zA-Z][a-zA-Z\s\-']{1,60})", msg, flags=re.IGNORECASE)
            if city_match:
                facts["location"] = city_match.group(1).strip()
    
            likes_match = re.search(r"\bi like\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
            if likes_match and " not " not in lowered:
                facts["likes"] = likes_match.group(1).strip()
    
            dislikes_match = re.search(r"\bi (?:do not|don't) like\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
            if dislikes_match:
                facts["dislikes"] = dislikes_match.group(1).strip()
    
            work_match = re.search(r"\bi work as\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
            if work_match:
                facts["profession"] = work_match.group(1).strip()
    
            preference_match = re.search(r"\bi prefer\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
            if preference_match:
                facts["preference"] = preference_match.group(1).strip()
    
            return facts

