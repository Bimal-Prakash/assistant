import time
import webbrowser
import logging
import json

try:
    import pyautogui
except ImportError:
    pyautogui = None

logger = logging.getLogger("jarvis.tools.chatgpt")

def exec_ask_chatgpt_visually(query: str) -> str:
    """Visually opens ChatGPT in the browser, types the query, and copies the response text."""
    if pyautogui is None:
        return "Error: pyautogui is not installed. Cannot physically interact with the browser."
        
    logger.info(f"Visual ChatGPT Collaboration triggered for query: {query}")
    
    try:
        # 1. Check if ChatGPT is already open and focus it, otherwise open new tab
        opened_existing = False
        try:
            # pyrefly: ignore [missing-import]
            import pygetwindow as gw
            all_windows = gw.getAllTitles()
            matches = [t for t in all_windows if "chatgpt" in t.lower() and ("chrome" in t.lower() or "edge" in t.lower() or "brave" in t.lower() or "firefox" in t.lower())]
            if matches:
                windows = gw.getWindowsWithTitle(matches[0])
                if windows:
                    w = windows[0]
                    if not w.isMaximized:
                        w.maximize()
                    try:
                        w.activate()
                    except Exception:
                        pass
                    opened_existing = True
                    logger.info("Focused existing ChatGPT window.")
                    time.sleep(1.0)
        except Exception as e:
            logger.debug(f"Window focus failed: {e}")
            
        if not opened_existing:
            webbrowser.open("https://chatgpt.com/")
            time.sleep(6) # Wait for new page to fully load
        
        # 3. Type the query directly into the active input box
        # Using a 0.08 second interval between keys looks very human (~150 WPM)
        pyautogui.typewrite(query, interval=0.08)
        time.sleep(1.0)
        
        # 4. Hit enter to submit
        pyautogui.press("enter")
        
        # 5. Wait for ChatGPT to finish generating the response.
        # This gives time for the UI to update and the text to stream in.
        time.sleep(12)
        
        # (Removed physical browser zoom; we now crop the image computationally)
            
        # 7. Move mouse to the center of the screen and scroll down forcefully
        # This ensures the chat container actually scrolls to the bottom
        try:
            screen_width, screen_height = pyautogui.size()
            pyautogui.moveTo(screen_width / 2, screen_height / 2)
            pyautogui.scroll(-5000)
        except Exception:
            pass
        time.sleep(1.0)
        
        # 7. Press Ctrl+A to select all, then Ctrl+C to copy
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)
        
        # Deselect text
        pyautogui.press("esc")
        
        # 8. Read the clipboard
        try:
            import pyperclip
            clipboard_content = pyperclip.paste()
        except ImportError:
            return "I opened ChatGPT and asked the question, but the 'pyperclip' library is missing so I cannot read the response from the clipboard."
            
        if not clipboard_content or len(clipboard_content.strip()) < 10:
            return "I opened ChatGPT, but I couldn't copy the response text. Do NOT retry this tool."
            
        # 9. Extract the actual response (Basic parsing)
        # ChatGPT's web UI text usually ends with the last thing it generated.
        # We'll just return the last 2000 characters of the clipboard to capture the response.
        text = clipboard_content.strip()
        if len(text) > 2000:
            text = "... " + text[-2000:]
            
        return f"I opened ChatGPT, asked the question, and read the response. ChatGPT says:\n\n{text}"
        
    except Exception as e:
        logger.exception("Failed during visual ChatGPT interaction")
        return f"Error while trying to interact with ChatGPT: {e}"
