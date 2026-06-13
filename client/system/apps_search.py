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
import webbrowser
import winreg
from urllib.parse import quote_plus
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
import difflib

from client.config import *
from client.ui import StatusHud

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

class StartMenuSearchMixin:
            def _find_start_menu_app_id(self, app_name: str) -> Optional[str]:
                try:
                    start_apps = self._get_start_apps()
                except Exception:
                    return None
        
                normalized = re.sub(r"\s+", " ", app_name.strip().lower())
                if not normalized:
                    return None
        
                exact = next(
                    (item["AppID"] for item in start_apps if item["Name"].strip().lower() == normalized),
                    None,
                )
                if exact:
                    return exact
        
                fuzzy = next(
                    (
                        item["AppID"]
                        for item in start_apps
                        if normalized in item["Name"].strip().lower()
                    ),
                    None,
                )
                return fuzzy

            def _get_start_apps(self) -> List[Dict[str, str]]:
                if (
                    self._start_apps_cache is not None
                    and (time.time() - self._start_apps_cache_ts) < START_APPS_CACHE_TTL_SECONDS
                ):
                    return self._start_apps_cache
        
                ps_command = (
                    "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    self._start_apps_cache = []
                    self._start_apps_cache_ts = time.time()
                    return self._start_apps_cache
        
                parsed = json.loads(result.stdout)
                if isinstance(parsed, dict):
                    parsed = [parsed]
        
                apps: List[Dict[str, str]] = []
                if isinstance(parsed, list):
                    for item in parsed:
                        if not isinstance(item, dict):
                            continue
                        name = str(item.get("Name", "")).strip()
                        app_id = str(item.get("AppID", "")).strip()
                        if name and app_id:
                            apps.append({"Name": name, "AppID": app_id})
        
                self._start_apps_cache = apps
                self._start_apps_cache_ts = time.time()
                return self._start_apps_cache

            def _find_start_menu_shortcut(self, app_name: str) -> Optional[str]:
                shortcuts = self._get_start_menu_shortcuts()
                normalized = re.sub(r"\s+", " ", app_name.strip().lower())
                if not normalized:
                    return None
        
                exact = next((item["path"] for item in shortcuts if item["name"] == normalized), None)
                if exact:
                    return exact
        
                fuzzy = next((item["path"] for item in shortcuts if normalized in item["name"]), None)
                return fuzzy

            def _get_start_menu_shortcuts(self) -> List[Dict[str, str]]:
                if self._start_menu_shortcuts_cache is not None:
                    return self._start_menu_shortcuts_cache
        
                candidates = []
                roots = [
                    os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
                    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                ]
                for root in roots:
                    if not root or not os.path.isdir(root):
                        continue
                    for dirpath, _, filenames in os.walk(root):
                        for filename in filenames:
                            if not filename.lower().endswith(".lnk"):
                                continue
                            full_path = os.path.join(dirpath, filename)
                            base_name = os.path.splitext(filename)[0]
                            normalized_name = re.sub(r"\s+", " ", base_name.strip().lower())
                            if normalized_name:
                                candidates.append({"name": normalized_name, "path": full_path})
        
                self._start_menu_shortcuts_cache = candidates
                return self._start_menu_shortcuts_cache

