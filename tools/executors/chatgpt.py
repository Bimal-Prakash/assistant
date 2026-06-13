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
        # 1. Open ChatGPT
        webbrowser.open("https://chatgpt.com/")
        
        # 2. Wait for the page to fully load (ChatGPT is heavy, 6 seconds is safe)
        time.sleep(6)
        
        # 3. Type the query directly into the active input box
        # Using a 0.08 second interval between keys looks very human (~150 WPM)
        pyautogui.typewrite(query, interval=0.08)
        time.sleep(1.0)
        
        # 4. Hit enter to submit
        pyautogui.press("enter")
        
        # 5. Wait for ChatGPT to finish generating the response.
        # This gives time for the UI to update and the text to stream in.
        time.sleep(12)
        
        # 6. Take a screenshot and use Moondream to read the response!
        vision_prompt = "Read the text of the main answer provided by ChatGPT on the screen."
        screen_content = exec_analyze_screen(query=vision_prompt)
        
        return f"I opened ChatGPT, asked the question, and read its response. ChatGPT says:\n\n{screen_content}"
        
    except Exception as e:
        logger.exception("Failed during visual ChatGPT interaction")
        return f"Error while trying to interact with ChatGPT: {e}"
