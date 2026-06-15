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

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class BackendMixin:
            def send_command(self, text: str) -> Dict[str, Any]:
                session_id = getattr(self, "session_id", "default")
                payload = {"text": text, "client": "pc", "session_id": session_id}
                response = requests.post(f"{self.backend_url}/command", json=payload, timeout=300)
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("Backend did not return a JSON object")
                return body

            def _check_backend_status(self, retries: int = 2, delay_seconds: float = 0.6) -> bool:
                status_url = f"{self.backend_url}/status"
                for attempt in range(max(1, retries)):
                    try:
                        response = requests.get(status_url, timeout=3)
                        response.raise_for_status()
                        body = response.json()
                        ok = bool(isinstance(body, dict) and body.get("status") == "ok")
                        self.backend_reachable = ok
                        self._last_backend_check_ts = time.time()
                        return ok
                    except Exception:
                        if attempt < retries - 1:
                            time.sleep(delay_seconds)
                self.backend_reachable = False
                self._last_backend_check_ts = time.time()
                return False

