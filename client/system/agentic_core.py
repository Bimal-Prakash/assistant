import os
import subprocess
import time
from typing import Optional, Dict, Any

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import psutil
except ImportError:
    psutil = None

class AgenticControlMixin:
    def _maximize_app(self, app_name: str) -> str:
        if gw:
            windows = gw.getWindowsWithTitle(app_name)
            if not windows:
                all_windows = gw.getAllTitles()
                matches = [t for t in all_windows if app_name.lower() in t.lower()]
                if matches:
                    windows = gw.getWindowsWithTitle(matches[0])
            if windows:
                for w in windows:
                    w.maximize()
                return f"Maximizing {app_name}"
        return f"Could not maximize {app_name}"

    def _restore_app(self, app_name: str) -> str:
        if gw:
            windows = gw.getWindowsWithTitle(app_name)
            if not windows:
                all_windows = gw.getAllTitles()
                matches = [t for t in all_windows if app_name.lower() in t.lower()]
                if matches:
                    windows = gw.getWindowsWithTitle(matches[0])
            if windows:
                for w in windows:
                    w.restore()
                return f"Restoring {app_name}"
        return f"Could not restore {app_name}"

    def _focus_app(self, app_name: str) -> str:
        if gw:
            windows = gw.getWindowsWithTitle(app_name)
            if not windows:
                all_windows = gw.getAllTitles()
                matches = [t for t in all_windows if app_name.lower() in t.lower()]
                if matches:
                    windows = gw.getWindowsWithTitle(matches[0])
            if windows:
                for w in windows:
                    try:
                        w.activate()
                    except Exception:
                        pass
                return f"Focused on {app_name}"
        return f"Could not focus {app_name}"

    def _hide_all_windows(self) -> str:
        if pyautogui:
            pyautogui.hotkey('win', 'd')
            return "Showing desktop"
        return "Could not hide windows"

    def _snap_window(self, app_name: str, direction: str) -> str:
        self._focus_app(app_name)
        time.sleep(0.5)
        if pyautogui:
            if direction == 'left':
                pyautogui.hotkey('win', 'left')
            elif direction == 'right':
                pyautogui.hotkey('win', 'right')
            elif direction == 'top':
                pyautogui.hotkey('win', 'up')
            elif direction == 'bottom':
                pyautogui.hotkey('win', 'down')
            return f"Snapped {app_name} to {direction}"
        return f"Could not snap {app_name}"

    def _read_clipboard(self) -> str:
        if pyperclip:
            text = pyperclip.paste()
            if text:
                return f"Clipboard contains: {text}"
            return "Clipboard is empty"
        return "Clipboard access not available"

    def _write_clipboard(self, text: str) -> str:
        if pyperclip:
            pyperclip.copy(text)
            return "Copied to clipboard"
        return "Clipboard access not available"

    def _press_shortcut(self, shortcut: str) -> str:
        if pyautogui:
            keys = shortcut.lower().split('+')
            pyautogui.hotkey(*keys)
            return f"Pressed {shortcut}"
        return "Keyboard automation not available"

    def _check_performance(self) -> str:
        if psutil:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            return f"CPU: {cpu}%, RAM: {ram}%, Disk: {disk}%"
        return "Performance monitoring not available"

    def _lock_pc(self) -> str:
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "PC locked"
        except Exception:
            return "Could not lock PC"

    def _empty_recycle_bin(self) -> str:
        try:
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
            return "Emptied recycle bin"
        except Exception:
            return "Could not empty recycle bin"

    def _take_screenshot(self) -> str:
        if pyautogui:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            filename = os.path.join(desktop, f"screenshot_{int(time.time())}.png")
            pyautogui.screenshot(filename)
            return f"Screenshot saved to desktop"
        return "Screenshot tool not available"

    def _show_notification(self, title: str, message: str) -> str:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return f"Showing notification: {title}"
        except ImportError:
            # Fallback to powershell
            ps_script = f"""
            [reflection.assembly]::loadwithpartialname("System.Windows.Forms")
            $notify = new-object system.windows.forms.notifyicon
            $notify.icon = [system.drawing.systemicons]::information
            $notify.visible = $true
            $notify.showballoontip(10,"{title}","{message}",[system.windows.forms.tooltipicon]::None)
            """
            subprocess.run(["powershell", "-Command", ps_script], check=False)
            return f"Showing notification: {title}"

    def _set_timer(self, seconds: int, label: str) -> str:
        def timer_thread():
            time.sleep(seconds)
            self._show_notification("Timer Complete", label or "Time is up!")
        
        import threading
        t = threading.Thread(target=timer_thread, daemon=True)
        t.start()
        return f"Timer set for {seconds} seconds"

    def _open_folder(self, folder_path: str) -> str:
        try:
            user_dir = os.path.expanduser("~")
            shortcuts = {
                "downloads": os.path.join(user_dir, "Downloads"),
                "documents": os.path.join(user_dir, "Documents"),
                "desktop": os.path.join(user_dir, "Desktop"),
                "pictures": os.path.join(user_dir, "Pictures"),
            }
            target = shortcuts.get(folder_path.lower(), folder_path)
            if os.path.exists(target):
                os.startfile(target)
                return f"Opening folder: {folder_path}"
            return f"Folder not found: {folder_path}"
        except Exception:
            return f"Could not open folder: {folder_path}"

    def _search_files(self, query: str) -> str:
        try:
            # Uses Windows Search via explorer
            subprocess.Popen(["explorer", f"search-ms:query={query}"])
            return f"Searching for {query}"
        except Exception:
            return f"Could not search for {query}"

    def _whatsapp_call(self, contact_name: str, call_type: str) -> str:
        if not pyautogui:
            return "UI automation not available"

        # Force the assistant to idle instantly so it doesn't accidentally listen while calling
        if hasattr(self, "wake_active_until"):
            self.wake_active_until = 0.0
        
        # Open whatsapp using existing method
        self._open_app("whatsapp")
        time.sleep(1) # Short wait before prompting

        print(f"\n[WhatsApp] Going to call '{contact_name}'. If this is wrong, type the correct name now (you have 5 seconds) and press Enter. (Type 'cancel' to abort):")
        corrected_name = ""
        start_time = time.time()
        canceled = False
        try:
            import msvcrt
            while time.time() - start_time < 5.0:
                if hasattr(self, "_check_abort") and self._check_abort():
                    canceled = True
                    print("\n[WhatsApp] Call aborted by voice command.")
                    break
                if msvcrt.kbhit():
                    c = msvcrt.getwch()
                    if c in ('\r', '\n'):
                        print()
                        if corrected_name.strip().lower() in ("cancel", "abort", "stop"):
                            canceled = True
                        break
                    elif c == '\b':
                        if corrected_name:
                            corrected_name = corrected_name[:-1]
                            print("\b \b", end="", flush=True)
                    else:
                        corrected_name += c
                        print(c, end="", flush=True)
                else:
                    time.sleep(0.05)
        except Exception:
            for _ in range(100):
                if hasattr(self, "_check_abort") and self._check_abort():
                    canceled = True
                    print("\n[WhatsApp] Call aborted by voice command.")
                    break
                time.sleep(0.05)
            
        if canceled:
            return "Call canceled by user."

        if corrected_name.strip():
            contact_name = corrected_name.strip()
            print(f"\n[WhatsApp] Using corrected name: '{contact_name}'")
        else:
            print(f"\n[WhatsApp] Proceeding with: '{contact_name}'")

        # Wait remaining time to ensure WhatsApp is fully loaded
        time.sleep(2)
        
        # Aggressively focus WhatsApp to prevent typing in the IDE
        self._focus_app("whatsapp")
        time.sleep(1.0)
        
        # Ensure we are out of any specific chat context
        pyautogui.press('esc')
        time.sleep(0.5)

        # Search for contact
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.5)
        # Clear existing search text
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('backspace')
        time.sleep(0.2)
        pyautogui.typewrite(contact_name, interval=0.05)
        time.sleep(2.0) # Wait for search results
        pyautogui.press('down')
        time.sleep(0.5)
        pyautogui.press('enter')
        # Wait for the chat to fully open
        time.sleep(2.0)
        
        # Maximize window to ensure stable coordinates for fallback clicking
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle("WhatsApp")
            if windows:
                if not windows[0].isMaximized:
                    windows[0].maximize()
                    time.sleep(1.0)
        except Exception:
            pass
        
        # Removed the 'esc' press here because in modern WhatsApp, Esc closes the chat!
        
        # Click call button using correct shortcuts with robust key presses and fallbacks
        if call_type == 'video':
            # UWP
            pyautogui.hotkey('ctrl', 'shift', 'v')
            time.sleep(0.5)
            # Legacy/Web
            pyautogui.hotkey('alt', 'shift', 'v')
            
            # Fallback 1: Image Recognition (if user provided 'video_call_btn.png')
            try:
                import os
                btn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "video_call_btn.png")
                if os.path.exists(btn_path):
                    button_location = pyautogui.locateOnScreen(btn_path, confidence=0.8)
                    if button_location:
                        pyautogui.click(pyautogui.center(button_location))
                        return f"Initiating video call with {contact_name}"
            except Exception:
                pass
                
            # Fallback 2: Coordinate click (Video call button is approx right - 200, top + 55)
            try:
                if windows:
                    w = windows[0]
                    pyautogui.click(x=w.right - 200, y=w.top + 55)
            except Exception:
                pass
                
            return f"Initiating video call with {contact_name}"
        else:
            # UWP Audio call is ctrl+shift+a
            pyautogui.hotkey('ctrl', 'shift', 'a')
            time.sleep(0.5)
            # Legacy/Web
            pyautogui.hotkey('alt', 'shift', 'a')
            
            # Fallback 1: Image Recognition (if user provided 'audio_call_btn.png')
            try:
                import os
                btn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "audio_call_btn.png")
                if os.path.exists(btn_path):
                    button_location = pyautogui.locateOnScreen(btn_path, confidence=0.8)
                    if button_location:
                        pyautogui.click(pyautogui.center(button_location))
                        return f"Initiating audio call with {contact_name}"
            except Exception:
                pass
            
            # Fallback 2: Coordinate click (Audio call button is approx right - 250, top + 55)
            try:
                if windows:
                    w = windows[0]
                    pyautogui.click(x=w.right - 250, y=w.top + 55)
            except Exception:
                pass
                
            return f"Initiating audio call with {contact_name}"
