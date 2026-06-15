import time
import webbrowser
import logging
import json

try:
    import pyautogui
except ImportError:
    pyautogui = None

from tools.executors.vision import exec_analyze_screen

logger = logging.getLogger("jarvis.tools.chatgpt")

def exec_ask_chatgpt_visually(query: str) -> str:
    """Visually opens ChatGPT in the browser, types the query, and uses the vision model to read the response."""
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
            time.sleep(4) # Wait for new page to load
        
        # 3. Type the query directly into the active input box
        pyautogui.typewrite(query, interval=0.02)
        time.sleep(0.5)
        
        # 4. Hit enter to submit
        pyautogui.press("enter")
        
        # 5. Wait for ChatGPT to finish generating the response.
        time.sleep(8)
        
        # 6. Zoom in so the vision model can read the text easily
        # Browsers use Ctrl + '=' or Ctrl + '+' to zoom in, Ctrl + '0' to reset
        for _ in range(2):
            pyautogui.hotkey('ctrl', '=')
            time.sleep(0.1)
            
        # 7. Move mouse to the center of the screen and scroll down forcefully
        # This ensures the chat container actually scrolls to the bottom
        try:
            screen_width, screen_height = pyautogui.size()
            pyautogui.moveTo(screen_width / 2, screen_height / 2)
            pyautogui.scroll(-5000)
        except Exception:
            pass
        time.sleep(0.5)
        
        # 7. Take a screenshot and use Moondream to read the response!
        vision_prompt = "Read the text of the main answer provided by ChatGPT on the screen."
        screen_content = exec_analyze_screen(query=vision_prompt)
        
        pyautogui.hotkey('ctrl', '0')
        time.sleep(0.2)
        
        if "empty response" in screen_content.lower():
            return f"I opened ChatGPT, but {screen_content} Do NOT retry this tool."
            
        return f"I opened ChatGPT, asked the question, and read its response. ChatGPT says:\n\n{screen_content}"
        
    except Exception as e:
        logger.exception("Failed during visual ChatGPT interaction")
        return f"Error while trying to interact with ChatGPT: {e}"
