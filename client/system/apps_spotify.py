import os
import time
import subprocess
from urllib.parse import quote_plus

from client.config import *

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
                except Exception as e:
                    print(f"[Spotify] Focus window error: {e}")

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
                    # Dynamically wait instead of static 4s sleep. 
                    # A static sleep is too slow for fast PCs and too short for budget laptops.
                    time.sleep(1.5)

                    self._focus_spotify_window()
                    time.sleep(1.0)

                    # Maximize window guarantees layout.
                    width, height = pyautogui.size()

                    # Try to find the play button visually using the image the user provides!
                    # This is the most bulletproof method since Spotify's layout changes.
                    try:
                        # Check for play_btn.png in root folder robustly (3 dirnames up from client/system/)
                        btn_img = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "play_btn.png")
                        if os.path.exists(btn_img):
                            btn_pos = None
                            # Poll for up to 15 seconds (30 * 0.5s) to allow slow budget laptops to load Spotify
                            for _ in range(30):
                                import contextlib
                                with contextlib.suppress(Exception):
                                    btn_pos = pyautogui.locateCenterOnScreen(btn_img, confidence=0.7, grayscale=True)
                                    if btn_pos: break
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

                    # Fallback: We must wait for the network to load the search results!
                    # Without image recognition, we don't know exactly when it finishes.
                    print("[Spotify] Waiting 3 seconds for search results to render...")
                    time.sleep(3.0)

                    # Strategy 1: Coordinate Click (Top Result card)
                    # Modern Spotify Top Result card is around x=35%, y=45% when maximized
                    top_result_x = int(width * 0.35)
                    top_result_y = int(height * 0.45)
                    pyautogui.moveTo(top_result_x, top_result_y)
                    time.sleep(0.2)
                    pyautogui.doubleClick()
                    time.sleep(0.5)
                    
                    # Strategy 3: Play shortcut
                    pyautogui.press('enter')

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

