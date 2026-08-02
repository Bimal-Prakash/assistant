import os
import subprocess
import time

try:
    # pyrefly: ignore [missing-import]
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    # pyrefly: ignore [missing-import]
    import pyperclip
except ImportError:
    pyperclip = None

try:
    # pyrefly: ignore [missing-import]
    import pyautogui
except ImportError:
    pyautogui = None

try:
    # pyrefly: ignore [missing-import]
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
        time.sleep(0.2)
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
                return f"Clipboard contains text: {text}"

        try:
            # pyrefly: ignore [missing-import]
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is not None:
                return "Clipboard contains an image."
        except Exception:
            pass

        return "Clipboard is empty or contains unsupported data."

    def _write_clipboard(self, text: str) -> str:
        if pyperclip:
            pyperclip.copy(text)
            return "Copied to clipboard"
        return "Clipboard access not available"

    def _press_shortcut(self, shortcut: str) -> str:
        if pyautogui:
            sequences = shortcut.lower().split(',')
            for seq in sequences:
                keys = seq.strip().split('+')
                pyautogui.hotkey(*keys)
            return f"Pressed {shortcut}"
        return "Keyboard automation not available"

    def _check_performance(self) -> str:
        if psutil:
            cpu = psutil.cpu_percent(interval=0.1)
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
            # pyrefly: ignore [missing-import]
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
            return "Emptied recycle bin"
        except Exception:
            return "Could not empty recycle bin"

    def _take_screenshot(self) -> str:
        if pyautogui:
            user_dir = os.path.expanduser("~")
            desktop = os.path.join(user_dir, "Desktop")
            onedrive_desktop = os.path.join(user_dir, "OneDrive", "Desktop")
            if os.path.exists(onedrive_desktop):
                desktop = onedrive_desktop

            os.makedirs(desktop, exist_ok=True)
            filename = os.path.join(desktop, f"screenshot_{int(time.time())}.png")
            pyautogui.screenshot(filename)
            return "Screenshot saved to desktop"
        return "Screenshot tool not available"

    def _show_notification(self, title: str, message: str) -> str:
        # Using PowerShell fallback directly to avoid win10toast dependency issues
        # Base64 encode to prevent PowerShell command injection
        import base64
        title_b64 = base64.b64encode(title.encode('utf-8')).decode('utf-8')
        message_b64 = base64.b64encode(message.encode('utf-8')).decode('utf-8')
        ps_script = f"""
        [reflection.assembly]::loadwithpartialname("System.Windows.Forms")
        $notify = new-object system.windows.forms.notifyicon
        $notify.icon = [system.drawing.systemicons]::information
        $notify.visible = $true
        $title = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{title_b64}"))
        $message = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{message_b64}"))
        $notify.showballoontip(10,$title,$message,[system.windows.forms.tooltipicon]::None)
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

    def _open_file(self, file_path: str) -> str:
        import os
        if os.path.exists(file_path):
            try:
                os.startfile(file_path)
                return f"Opening: {file_path}"
            except Exception as e:
                return f"Failed to open {file_path}: {e}"
        return f"File not found: {file_path}"

    def _open_folder(self, folder_path: str) -> str:
        try:
            import os
            import concurrent.futures
            import string

            user_dir = os.path.expanduser("~")

            # 1. Clean the input using regex
            import re
            clean_name = folder_path.lower()
            clean_name = re.sub(r'\b(jarvis|open|my|the|folder|directory|file|named|name|it is|which is|that is|located|in [a-zA-Z] drive)\b', '', clean_name)
            # Clean up extra spaces
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()

            # Context extraction
            parts = re.split(r'\s+in\s+|\s+inside\s+|\s+from\s+', clean_name)
            target_name = parts[0].strip()
            parent_name = parts[1].strip() if len(parts) > 1 else None

            # Ignore pronouns since last_opened_folder automatically handles contextual prioritization
            if parent_name in ["that", "this", "it", "there"]:
                parent_name = None

            shortcuts = {
                "downloads": os.path.join(user_dir, "Downloads"),
                "documents": os.path.join(user_dir, "Documents"),
                "desktop": os.path.join(user_dir, "Desktop"),
                "pictures": os.path.join(user_dir, "Pictures"),
                "videos": os.path.join(user_dir, "Videos"),
                "music": os.path.join(user_dir, "Music"),
            }
            target = shortcuts.get(target_name, folder_path)

            # Check shortcut first
            if os.path.exists(target):
                os.startfile(target)
                return f"Opening: {clean_name}"

            # Check exact match if it was an absolute path
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                return f"Opening: {folder_path}"

            # 2. Deep Parallel Search
            import json
            cache_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "core", "search_cache.json")
            search_cache = {}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        search_cache = json.load(f)
                except Exception:
                    pass
            
            cache_key = f"{target_name}_{parent_name}" if parent_name else target_name
            if cache_key in search_cache and os.path.exists(search_cache[cache_key]):
                print(f"\n[Jarvis] Found '{target_name}' in search cache.")
                self._last_opened_folder = os.path.dirname(search_cache[cache_key]) if os.path.isfile(search_cache[cache_key]) else search_cache[cache_key]
                os.startfile(search_cache[cache_key])
                return f"Opening from cache: {search_cache[cache_key]}"

            print(f"\n[Jarvis] '{target_name}' not in shortcuts or cache. Initiating Deep Parallel Search...")

            search_paths = []

            # Prioritize last opened folder if we have one
            last_opened = getattr(self, '_last_opened_folder', None)
            if last_opened and os.path.exists(last_opened):
                search_paths.append(last_opened)
                print(f"[Jarvis] Prioritizing last opened folder: {last_opened}")

            # Make sure user_dir is prioritized
            if user_dir not in search_paths:
                search_paths.append(user_dir)

            # Add all available physical drives (including C:\ because we skip system folders)
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive) and drive not in search_paths:
                    search_paths.append(drive)

            found_path = None

            def search_dir(base_dir):
                # Search recursively but skip heavy system folders
                skip_dirs = {'windows', 'program files', 'program files (x86)', 'appdata', 'node_modules', '$recycle.bin', 'programdata', 'perflogs', 'recovery', 'system volume information'}
                for root, dirs, files in os.walk(base_dir):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in skip_dirs]

                    for d in dirs:
                        # If a parent context was given ("in Bimal"), ensure the path contains the parent
                        if parent_name and parent_name not in root.lower() and parent_name not in d.lower():
                            continue

                        if d.lower() == target_name:
                            return os.path.join(root, d)
                        # Partial match if it's very close
                        if len(target_name) >= 4 and target_name in d.lower() and len(d) < len(target_name) + 5:
                            return os.path.join(root, d)

                    for f in files:
                        if parent_name and parent_name not in root.lower():
                            continue

                        name_without_ext = os.path.splitext(f)[0].lower()
                        if f.lower() == target_name or name_without_ext == target_name:
                            return os.path.join(root, f)
                        # Partial match if it's very close
                        if len(target_name) >= 4 and target_name in f.lower() and len(f) < len(target_name) + 8:
                            return os.path.join(root, f)
                return None

            # Run search in parallel threads across the root paths
            import psutil
            cpu_count = os.cpu_count() or 4
            total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            
            is_budget = cpu_count <= 4 or total_ram_gb <= 8
            if is_budget:
                max_workers = min(len(search_paths), cpu_count + 1)
                print(f"\n[Jarvis] Budget hardware detected ({cpu_count} cores, {total_ram_gb:.1f}GB RAM). Using safe thread limit: {max_workers}.")
            else:
                max_workers = len(search_paths)
                print(f"\n[Jarvis] High-end hardware detected ({cpu_count} cores, {total_ram_gb:.1f}GB RAM). Maximizing search threads: {max_workers}.")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(search_dir, path): path for path in search_paths}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        found_path = result
                        break

            if found_path and os.path.exists(found_path):
                self._last_opened_folder = os.path.dirname(found_path) if os.path.isfile(found_path) else found_path
                search_cache[cache_key] = found_path
                try:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(search_cache, f)
                except Exception:
                    pass
                os.startfile(found_path)
                return f"Deep search found and opened: {found_path}"

            return f"File/Folder not found after deep search: {folder_path}"
        except Exception as e:
            return f"Could not open folder: {folder_path} (Error: {e})"

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

        # Try to find a phonetic match in contacts.json to fix STT typos (e.g. Pawan -> Pavan)
        import json
        import difflib
        contacts_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "core", "contacts.json")
        start_t = float(os.environ.get("COMMAND_START_TIME", str(time.time())))

        try:
            if not hasattr(self, '_cached_contacts'):
                self._cached_contacts = None
                if os.path.exists(contacts_file):
                    with open(contacts_file, "r", encoding="utf-8") as f:
                        contacts_data = json.load(f)
                    if isinstance(contacts_data, dict):
                        self._cached_contacts = list(contacts_data.keys())
                    elif isinstance(contacts_data, list):
                        self._cached_contacts = contacts_data

            contact_names = self._cached_contacts or []
            if contact_names:
                    matches = difflib.get_close_matches(contact_name, contact_names, n=1, cutoff=0.6)
                    if matches and matches[0].lower() != contact_name.lower():
                        print(f"\n[WhatsApp] Phonetic correction applied: '{contact_name}' -> '{matches[0]}'")
                        contact_name = matches[0]
        except Exception:
            pass

        # Force the assistant to idle instantly so it doesn't accidentally listen while calling
        if hasattr(self, "wake_active_until"):
            self.wake_active_until = 0.0

        # Open and aggressively focus whatsapp immediately
        self._open_app("whatsapp")
        time.sleep(0.3)
        self._focus_app("whatsapp")
        time.sleep(0.2)

        if call_type == 'end':
            try:
                btn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "end_call_btn.png")
                if os.path.exists(btn_path):
                    button_location = pyautogui.locateOnScreen(btn_path, confidence=0.8, grayscale=True)
                    if button_location:
                        pyautogui.click(pyautogui.center(button_location))
                        return "Ended WhatsApp call"
            except Exception:
                pass
            return "Could not find the end call button."

        print(f"\n[WhatsApp] Proceeding with: '{contact_name}'")
        print(f"[Benchmark] WhatsApp focused: {time.time() - start_t:.2f}s")

        # Maximize + switch to Chats tab + open New Chat in rapid succession
        pyautogui.hotkey('win', 'up')
        time.sleep(0.15)
        pyautogui.hotkey('ctrl', '1')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'n')
        time.sleep(0.3)

        # Type the contact name into the New Chat search box
        pyautogui.typewrite(contact_name, interval=0.01)
        time.sleep(0.4)

        # Select the first contact result
        pyautogui.press('down')
        time.sleep(0.1)
        pyautogui.press('enter')

        # Wait for the chat to open
        time.sleep(0.3)

        print(f"[Benchmark] Contact opened: {time.time() - start_t:.2f}s")

        # Click call button using correct shortcuts with robust key presses and fallbacks
        if call_type == 'video':
            # Fallback: Image Recognition
            try:
                btn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "video_call_btn.png")
                if os.path.exists(btn_path):
                    button_location = pyautogui.locateOnScreen(btn_path, confidence=0.7, grayscale=True)
                    if button_location:
                        pyautogui.click(pyautogui.center(button_location))
                        return f"Initiating video call with {contact_name}"
            except Exception:
                pass

            # Fallback: Coordinate click (Window Title might fail for UWP, so use screen size)
            try:
                windows = gw.getWindowsWithTitle("WhatsApp")
                if windows:
                    w = windows[0]
                    pyautogui.click(x=w.right - 200, y=w.top + 55)
                else:
                    screen_width, _ = pyautogui.size()
                    pyautogui.click(x=screen_width - 250, y=55) # Video call is typically left of audio call
            except Exception:
                pass

            print(f"[Benchmark] Call started: {time.time() - start_t:.2f}s")
            return f"Initiating video call with {contact_name}"
        else:
            # Fallback: Image Recognition
            try:
                btn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "audio_call_btn.png")
                if os.path.exists(btn_path):
                    button_location = pyautogui.locateOnScreen(btn_path, confidence=0.7, grayscale=True)
                    if button_location:
                        pyautogui.click(pyautogui.center(button_location))
                        return f"Initiating audio call with {contact_name}"
            except Exception:
                pass

            # Fallback: Coordinate click (Window Title might fail for UWP, so use screen size)
            try:
                windows = gw.getWindowsWithTitle("WhatsApp")
                if windows:
                    w = windows[0]
                    pyautogui.click(x=w.right - 250, y=w.top + 55)
                else:
                    screen_width, _ = pyautogui.size()
                    pyautogui.click(x=screen_width - 190, y=55) # Voice call is typically right of video call
            except Exception:
                pass

            print(f"[Benchmark] Call started: {time.time() - start_t:.2f}s")
            return f"Initiating audio call with {contact_name}"

    def _telegram_call(self, contact_name: str, call_type: str) -> str:
        if not pyautogui:
            return "UI automation not available"

        # Try to find a phonetic match in contacts.json to fix STT typos
        import json
        import difflib
        contacts_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "core", "contacts.json")
        start_t = float(os.environ.get("COMMAND_START_TIME", str(time.time())))

        try:
            if not hasattr(self, '_cached_contacts'):
                self._cached_contacts = None
                if os.path.exists(contacts_file):
                    with open(contacts_file, "r", encoding="utf-8") as f:
                        contacts_data = json.load(f)
                    if isinstance(contacts_data, dict):
                        self._cached_contacts = list(contacts_data.keys())
                    elif isinstance(contacts_data, list):
                        self._cached_contacts = contacts_data

            contact_names = self._cached_contacts or []
            if contact_names:
                    matches = difflib.get_close_matches(contact_name, contact_names, n=1, cutoff=0.6)
                    if matches and matches[0].lower() != contact_name.lower():
                        print(f"\n[Telegram] Phonetic correction applied: '{contact_name}' -> '{matches[0]}'")
                        contact_name = matches[0]
        except Exception:
            pass

        # Force idle
        if hasattr(self, "wake_active_until"):
            self.wake_active_until = 0.0

        # Open and focus Telegram
        self._open_app("telegram")
        time.sleep(0.5)
        self._focus_app("telegram")
        time.sleep(0.3)

        if call_type == 'end':
            try:
                btn_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "end_call_btn.png")
                if os.path.exists(btn_path):
                    button_location = pyautogui.locateOnScreen(btn_path, confidence=0.8, grayscale=True)
                    if button_location:
                        pyautogui.click(pyautogui.center(button_location))
                        return "Ended Telegram call"
            except Exception:
                pass
            return "Could not find the end call button."

        print(f"\n[Telegram] Proceeding with: '{contact_name}'")
        print(f"[Benchmark] Telegram focused: {time.time() - start_t:.2f}s")

        pyautogui.hotkey('win', 'up')
        time.sleep(0.3)

        # Focus search bar
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.2)

        # Clear search
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')

        # Type name
        pyautogui.typewrite(contact_name, interval=0.01)
        time.sleep(0.5)

        # Select first result
        pyautogui.press('down')
        time.sleep(0.1)
        pyautogui.press('enter')
        time.sleep(0.4)

        print(f"[Benchmark] Contact opened: {time.time() - start_t:.2f}s")

        # Click call button (top right corner of Telegram Desktop)
        try:
            windows = gw.getWindowsWithTitle("Telegram")
            if windows:
                w = windows[0]
                if call_type == 'video':
                    pyautogui.click(x=w.right - 200, y=w.top + 45)
                else:
                    pyautogui.click(x=w.right - 140, y=w.top + 45)
        except Exception:
            pass

        print(f"[Benchmark] Call started: {time.time() - start_t:.2f}s")
        return f"Initiating {call_type} call with {contact_name} on Telegram"
