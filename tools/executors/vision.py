import base64
import io
import logging
import requests

from core.config import OLLAMA_API_URL

logger = logging.getLogger("jarvis.tools.vision")

def exec_analyze_screen(query: str) -> str:
    """Takes a screenshot and asks the Moondream vision model to analyze it."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Error: Pillow is not installed. Cannot take screenshot."

    try:
        # 1. Take a screenshot
        screenshot = ImageGrab.grab()
        
        # 2. Convert to base64 JPEG to send to Ollama
        buffered = io.BytesIO()
        screenshot.save(buffered, format="JPEG", quality=80)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # 3. Ask Moondream
        payload = {
            "model": "moondream",
            "prompt": query,
            "images": [img_str],
            "stream": False,
            "keep_alive": 0 # Unload immediately to prevent 4GB VRAM crash
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        result = data.get("response", "").strip()
        
        if not result:
            return "The vision model returned an empty response. Do NOT retry this tool."
            
        return result
        
    except requests.exceptions.Timeout:
        return "Error: The vision model took too long to respond. It might still be loading into VRAM."
    except Exception as e:
        logger.exception("Failed to analyze screen")
        return f"Error analyzing screen: {e}"
