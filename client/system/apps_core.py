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
    import pyautogui
except Exception:
    pyautogui = None
class AppManagementMixin:
            def _suggest_app_name(self, raw_name: str) -> Optional[str]:
                normalized = self._normalize_text_command(raw_name)
                if not normalized:
                    return None
        
                candidates = set(APP_URI_MAP.keys()) | set(APP_ALIASES.values()) | set(APP_ALIASES.keys())
                candidates.update({"chrome", "notepad", "calculator", "explorer", "vscode", "terminal", "cmd", "powershell", "spotify", "whatsapp"})
        
                try:
                    for app in self._get_start_apps():
                        name = self._normalize_text_command(str(app.get("Name", "")))
                        if name:
                            candidates.add(name)
                except Exception:
                    pass
        
                try:
                    for shortcut in self._get_start_menu_shortcuts():
                        name = self._normalize_text_command(str(shortcut.get("name", "")))
                        if name:
                            candidates.add(name)
                except Exception:
                    pass
        
                if not candidates:
                    return None
        
                matches = difflib.get_close_matches(normalized, sorted(candidates), n=1, cutoff=0.72)
                return matches[0] if matches else None

            def _open_app(self, app_name: str, post_text: Optional[str] = None) -> str:
                raw_app = re.sub(r"\s+", " ", app_name.strip().lower())
                raw_app = re.sub(r"\s+(?:in|on)\s+(?:chrome|browser)$", "", raw_app).strip()
                raw_app = re.sub(r"^(the|a|an)\s+", "", raw_app).strip()
                raw_app = re.sub(r"\s+app$", "", raw_app).strip()
                raw_app = re.sub(r"\s+web$", "", raw_app).strip()
                self.pending_alias_suggestion = None
                app = self.dynamic_aliases.get(raw_app, APP_ALIASES.get(raw_app, raw_app))
                app_map = {
                    "chrome": ["cmd", "/c", "start", "chrome"],
                    "notepad": ["notepad"],
                    "calculator": ["calc"],
                    "explorer": ["explorer"],
                    "vscode": ["cmd", "/c", "start", "code"],
                    "terminal": ["wt"],
                    "cmd": ["cmd"],
                    "powershell": ["powershell"],
                }
                cmd = app_map.get(app)
        
                try:
                    if cmd:
                        subprocess.Popen(cmd, shell=False)
                        self._handle_post_open_action(app, post_text)
                        return f"Opening {app_name}"
        
                    app_uri = APP_URI_MAP.get(app)
                    if app_uri:
                        subprocess.Popen(["cmd", "/c", "start", "", app_uri], shell=False)
                        self._handle_post_open_action(app, post_text)
                        return f"Opening {app_name}"
        
                    # Try executable resolution from PATH.
                    candidates = [app, app.replace(" ", ""), f"{app}.exe", f"{app.replace(' ', '')}.exe"]
                    seen: set = set()
                    for candidate in candidates:
                        if not candidate or candidate in seen:
                            continue
                        seen.add(candidate)
                        where_result = subprocess.run(
                            ["where", candidate],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if where_result.returncode == 0:
                            first_path = where_result.stdout.splitlines()[0].strip()
                            if first_path:
                                subprocess.Popen(["cmd", "/c", "start", "", first_path], shell=False)
                                self._handle_post_open_action(app, post_text)
                                return f"Opening {app_name}"
        
                    app_id = self._find_start_menu_app_id(app)
                    if app_id:
                        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], shell=False)
                        self._handle_post_open_action(app, post_text)
                        return f"Opening {app_name}"
        
                    shortcut = self._find_start_menu_shortcut(app)
                    if shortcut:
                        os.startfile(shortcut)  # type: ignore[attr-defined]
                        self._handle_post_open_action(app, post_text)
                        return f"Opening {app_name}"
        
                    if app in WEB_ALIASES:
                        webbrowser.open(WEB_ALIASES[app])
                        return f"Opening {app_name} in browser"

                    web_fallbacks = {
                        "youtube": "https://www.youtube.com/",
                    }
                    if app in web_fallbacks:
                        webbrowser.open(web_fallbacks[app])
                        return f"Opening {app_name} in browser"
                except Exception as exc:
                    return f"Failed to open {app_name}: {exc}"
        
                # Fallback: Deep Parallel Search for executable
                found_path = self._deep_parallel_search(app)
                if found_path:
                    subprocess.Popen(["cmd", "/c", "start", "", found_path], shell=False)
                    self._handle_post_open_action(app, post_text)
                    return f"Found and opening {app_name}"
        
                suggestion = self._suggest_app_name(raw_app)
                if suggestion and suggestion != raw_app:
                    self.pending_alias_suggestion = {"spoken": raw_app, "suggested": suggestion}
                    return f"I could not find {app_name}. Did you mean {suggestion}? Say yes or no."
                
                # Fallback: Try to open the corresponding .com website directly
                clean_name = raw_app.replace(" ", "")
                # Some common mappings if the name is slightly different
                domain_map = {
                    "whatsapp": "web.whatsapp.com",
                    "discord": "discord.com/app",
                    "claude": "claude.ai",
                    "gemini": "gemini.google.com",
                    "chatgpt": "chatgpt.com",
                }
                domain = domain_map.get(clean_name, f"www.{clean_name}.com")
                search_url = f"https://{domain}"
                webbrowser.open(search_url)
                return f"I couldn't find the app locally, so I opened {search_url} in your browser."

            def _deep_parallel_search(self, target_exe: str) -> Optional[str]:
                import concurrent.futures
                
                target_exe = target_exe.lower()
                if not target_exe.endswith(".exe"):
                    target_exe += ".exe"
                
                user_profile = os.environ.get("USERPROFILE", "")
                local_appdata = os.environ.get("LOCALAPPDATA", "")
                
                search_dirs = [
                    "C:\\Program Files",
                    "C:\\Program Files (x86)",
                    "C:\\Games",
                    "D:\\Games",
                    "D:\\",
                    local_appdata,
                    os.path.join(user_profile, "Desktop")
                ]
                
                valid_dirs = [d for d in search_dirs if os.path.isdir(d)]
                
                def search_directory(directory: str) -> Optional[str]:
                    try:
                        # Limit depth for D:\ root to prevent infinite hangs
                        max_depth = 3 if directory == "D:\\" else None
                        base_depth = directory.count(os.sep)
                        
                        for root, _, files in os.walk(directory):
                            if max_depth is not None:
                                current_depth = root.count(os.sep)
                                if current_depth - base_depth >= max_depth:
                                    continue
                                    
                            for file in files:
                                if file.lower() == target_exe:
                                    return os.path.join(root, file)
                    except Exception:
                        pass
                    return None
                
                if not valid_dirs:
                    return None
                    
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(valid_dirs)) as executor:
                    futures = {executor.submit(search_directory, d): d for d in valid_dirs}
                    try:
                        for future in concurrent.futures.as_completed(futures, timeout=3.0):
                            result = future.result()
                            if result:
                                return result
                    except concurrent.futures.TimeoutError:
                        pass
                return None

            def _close_app(self, app_name: str) -> str:
                app = app_name.strip().lower()
                process_map = {
                    "chrome": ["chrome.exe"],
                    "google chrome": ["chrome.exe"],
                    "spotify": ["spotify.exe", "spotifylauncher.exe"],
                    "whatsapp": ["whatsapp.exe"],
                    "terminal": ["WindowsTerminal.exe", "wt.exe"],
                    "windows terminal": ["WindowsTerminal.exe", "wt.exe"],
                    "vscode": ["code.exe"],
                    "notepad": ["notepad.exe"],
                    "explorer": ["explorer.exe"],
                    "vlc": ["vlc.exe"],
                    "vlc player": ["vlc.exe"],
                    "vlc media player": ["vlc.exe"]
                }
        
                process_images = process_map.get(app)
                if not process_images:
                    base = app.replace(" ", "")
                    process_images = [f"{base}.exe"]
        
                for image in process_images:
                    result = subprocess.run(
                        ["taskkill", "/IM", image, "/F"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode == 0:
                        return f"Closing {app_name}"
                        
                # Fallback: If taskkill fails, try to close it via window title (useful for 'close it' context resolution)
                try:
                    # pyrefly: ignore [missing-import]
                    import pygetwindow as gw
                    windows = gw.getWindowsWithTitle(app_name)
                    if windows:
                        windows[0].close()
                        return f"Closed window: {app_name}"
                except Exception as e:
                    pass
        
                return f"I could not close app {app_name} on laptop"

            def _minimize_app(self, app_name: str) -> str:
                try:
                    # pyrefly: ignore [missing-import]
                    import pygetwindow as gw
                    windows = gw.getWindowsWithTitle(app_name)
                    if not windows and app_name.lower() in APP_ALIASES:
                        windows = gw.getWindowsWithTitle(APP_ALIASES[app_name.lower()])
                    
                    if not windows:
                        # Try case insensitive match if direct match fails
                        all_windows = gw.getAllTitles()
                        matches = [t for t in all_windows if app_name.lower() in t.lower()]
                        if matches:
                            windows = gw.getWindowsWithTitle(matches[0])
                    
                    if windows:
                        for w in windows:
                            w.minimize()
                        return f"Minimizing {app_name}"
                except Exception:
                    pass
                
                # Fallback to powershell
                try:
                    ps_cmd = f"""
                    $wshell = New-Object -ComObject wscript.shell;
                    if ($wshell.AppActivate('{app_name}')) {{
                        Start-Sleep -Milliseconds 100
                        $wshell.SendKeys('% n')
                    }}
                    """
                    subprocess.run(["powershell", "-Command", ps_cmd], check=False)
                    return f"Minimizing {app_name}"
                except Exception as e:
                    return f"Failed to minimize {app_name}"

            def _handle_post_open_action(self, app: str, post_text: Optional[str]) -> None:
                query = (post_text or "").strip()
                if not query:
                    return
                if query.lower() in {"none", "null", "undefined", "n/a", "na"}:
                    return
        
                if pyautogui is None:
                    return
        
                if app == "spotify":
                    self._spotify_search_and_play(query)
                    return

                if app == "youtube":
                    from urllib.parse import quote_plus
                    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                    import webbrowser
                    webbrowser.open(search_url)
                    return
        
                time.sleep(1.5)
                try:
                    pyautogui.hotkey("ctrl", "l")
                    pyautogui.typewrite(query, interval=0.02)
                    pyautogui.press("enter")
                except Exception:
                    pass

