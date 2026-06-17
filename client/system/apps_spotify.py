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
class SpotifyMixin:
            def _focus_spotify_window(self) -> None:
                if pyautogui is None:
                    return
                try:
                    ps_script = (
                        "Add-Type -Name WinApi -Namespace Native -MemberDefinition '"
                        "[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);"
                        "[DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);"
                        "'; "
                        "$p = Get-Process Spotify -ErrorAction SilentlyContinue | "
                        "Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
                        "if ($p) { [Native.WinApi]::ShowWindowAsync($p.MainWindowHandle, 3) | Out-Null; "
                        "[Native.WinApi]::SetForegroundWindow($p.MainWindowHandle) | Out-Null }"
                    )
                    subprocess.run(
                        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=4,
                    )
                    time.sleep(0.5)
                    width, height = pyautogui.size()
                    pyautogui.click(int(width * 0.5), int(height * 0.35))
                except Exception:
                    pass

            _last_played_random_item = None

            def _spotify_search_and_play(self, query: str) -> None:
                if pyautogui is None:
                    print("[Spotify] sorry not available")
                    return

                # If query contains multiple items separated by 'and' or ',', pick one randomly
                if " and " in query.lower() or "," in query:
                    import random
                    import re
                    parts = re.split(r'\s+and\s+|,\s*', query, flags=re.IGNORECASE)
                    parts = [p.strip() for p in parts if p.strip()]
                    if parts:
                        # If we have played one of these recently, try to pick a different one
                        available_parts = [p for p in parts if p != self.__class__._last_played_random_item]
                        if not available_parts:
                            available_parts = parts  # fallback if all were played or something went wrong
                        
                        query = random.choice(available_parts)
                        self.__class__._last_played_random_item = query
                        print(f"[Spotify] Randomly selected: {query}")
        
                try:
                    search_uri = f"spotify:search:{quote_plus(query)}"
                    subprocess.Popen(["cmd", "/c", "start", "", search_uri], shell=False)
                    time.sleep(4.0)
                    
                    self._focus_spotify_window()
                    time.sleep(1.0)
                    
                    # Maximize window guarantees layout. 
                    width, height = pyautogui.size()
                    
                    # Try to find the play button visually using the image the user provides!
                    # This is the most bulletproof method since Spotify's layout changes.
                    try:
                        # Check for play_btn.png in root folder
                        btn_img = os.path.join(os.getcwd(), "play_btn.png")
                        if os.path.exists(btn_img):
                            btn_pos = None
                            for _ in range(10):
                                try:
                                    btn_pos = pyautogui.locateCenterOnScreen(btn_img, confidence=0.7)
                                    if btn_pos: break
                                except Exception: pass
                                time.sleep(0.5)
                                
                            if btn_pos:
                                pyautogui.click(btn_pos)
                                print(f"[Spotify] Playing: {query} (clicked via image recognition)")
                                return
                            else:
                                print("[Spotify] Play button image not found after 5s.")
                    except Exception as img_err:
                        err_str = str(img_err) or "ImageNotFoundException"
                        print(f"[Spotify] Image recognition failed/skipped: {err_str}")
                        
                    # Fallback: Double click the 'Songs' list first track or 'Top Result'
                    # The 'Songs' list first track is reliably at x=60%, y=18% 
                    target_x = int(width * 0.60)
                    target_y = int(height * 0.18)
                    
                    # Move and double click to play the song
                    pyautogui.moveTo(target_x, target_y)
                    time.sleep(0.2)
                    pyautogui.doubleClick()
                    
                    print(f"[Spotify] Playing: {query}")
                except Exception as e:
                    print(f"[Spotify] Error: {e}")

            def _spotify_like_current_song(self) -> str:
                if pyautogui is None:
                    return "Spotify like is unavailable because UI automation is disabled."
        
                try:
                    subprocess.Popen("spotify", shell=True)
                    time.sleep(1.5)
                    self._focus_spotify_window()
                    time.sleep(0.3)
                    # Spotify desktop shortcut to like/save current song.
                    pyautogui.hotkey("ctrl", "s")
                    return "Liked current song on Spotify."
                except Exception as exc:
                    return f"Could not like current song on Spotify: {exc}"

