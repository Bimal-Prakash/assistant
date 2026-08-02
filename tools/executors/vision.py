import base64
import io
import logging
import requests
import re

from core.config import OLLAMA_API_URL, OLLAMA_VISION_MODEL

logger = logging.getLogger("jarvis.tools.vision")

def exec_look_at_screen(query: str = "Describe what is on the screen in detail.", crop_center: bool = False) -> str:
    """Takes a screenshot and asks the vision model to analyze it."""
    try:
        # pyrefly: ignore [missing-import]
        from PIL import ImageGrab, Image
    except ImportError:
        return "Error: Pillow is not installed. Cannot take screenshot."

    try:
        # 1. Take a screenshot
        screenshot = ImageGrab.grab()

        # 2. Optionally crop the center (e.g. for ChatGPT responses)
        if crop_center:
            width, height = screenshot.size
            left = int(width * 0.15)
            right = int(width * 0.85)
            top = int(height * 0.10)
            bottom = int(height * 0.95)
            screenshot = screenshot.crop((left, top, right, bottom))
            # Resize it back up so Moondream gets high resolution of the cropped area
            screenshot = screenshot.resize((width, height), Image.Resampling.LANCZOS)

        # 3. Convert to base64 JPEG to send to Ollama
        buffered = io.BytesIO()
        screenshot.save(buffered, format="JPEG", quality=90)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 3. Ask Vision Model
        system_prompt = "You are a strict, literal vision analyzer. Look at the provided screenshot. Describe ONLY what is explicitly visible. Be concise. DO NOT invent or hallucinate websites, text, apps, or UI elements that are not clearly shown in the image. Do NOT say 'As an AI' or 'I cannot see your screen'."
        payload = {
            "model": OLLAMA_VISION_MODEL,
            "prompt": query,
            "system": system_prompt,
            "images": [img_str],
            "stream": False,
            "keep_alive": 0 # Unload immediately to prevent 4GB VRAM crash
        }

        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)

        if response.status_code == 404:
            return f"Error: The vision model '{OLLAMA_VISION_MODEL}' was not found in Ollama. Please run 'ollama pull {OLLAMA_VISION_MODEL}' in a separate terminal and wait for it to finish!"

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

def _apply_grid_overlay(image, rows=10, cols=10):
    """Draws a numbered grid on the image and returns (annotated_image, cell_coordinates_map)."""
    try:
        # pyrefly: ignore [missing-import]
        from PIL import ImageDraw, ImageFont
    except ImportError:
        return image, {}

    width, height = image.size
    cell_w = width / cols
    cell_h = height / rows

    draw = ImageDraw.Draw(image)
    try:
        # Use default Arial or fallback
        font = ImageFont.truetype("arial.ttf", size=max(16, int(cell_h * 0.4)))
    except IOError:
        font = ImageFont.load_default()

    coords_map = {}
    box_num = 1

    for r in range(rows):
        for c in range(cols):
            x0 = c * cell_w
            y0 = r * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h

            # Center coordinate of the cell
            center_x = int(x0 + (cell_w / 2))
            center_y = int(y0 + (cell_h / 2))

            coords_map[box_num] = (center_x, center_y)

            # Draw semi-transparent red box (PIL doesn't do alpha well with standard Draw, so just outline)
            draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=2)

            # Draw number with a black background outline for visibility
            text = str(box_num)

            # Calculate text size using textbbox
            bbox = font.getbbox(text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            tx = center_x - (text_w / 2)
            ty = center_y - (text_h / 2)

            draw.text((tx-1, ty-1), text, font=font, fill=(0, 0, 0))
            draw.text((tx+1, ty+1), text, font=font, fill=(0, 0, 0))
            draw.text((tx, ty), text, font=font, fill=(255, 255, 0))

            box_num += 1

    return image, coords_map

def exec_vision_click(element_description: str) -> str:
    """Takes a screenshot, adds a grid, asks moondream for the box number, and clicks it."""
    try:
        # pyrefly: ignore [missing-import]
        from PIL import ImageGrab, Image
        import pyautogui
    except ImportError:
        return "Error: Required libraries (Pillow, pyautogui) are not installed."

    try:
        logger.info(f"Vision Click requested for: {element_description}")
        # 1. Grab screenshot
        screenshot = ImageGrab.grab()

        # 2. Draw grid
        annotated_img, coords_map = _apply_grid_overlay(screenshot.copy(), rows=10, cols=10)

        # 3. Convert to base64
        buffered = io.BytesIO()
        annotated_img.save(buffered, format="JPEG", quality=90)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 4. Prompt Moondream
        prompt = f"Look at the numbered grid on this screen. Which number is covering the {element_description}? Output ONLY the exact integer number."
        system_prompt = "You are a precise coordinate analyzer. You must output NOTHING but the exact integer number corresponding to the grid box covering the requested element. Do not output words, explanations, or punctuation."
        payload = {
            "model": OLLAMA_VISION_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "images": [img_str],
            "stream": False,
            "keep_alive": 0
        }

        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)

        if response.status_code == 404:
            return f"Error: The vision model '{OLLAMA_VISION_MODEL}' was not found in Ollama. Please run 'ollama pull {OLLAMA_VISION_MODEL}' in a separate terminal and wait for it to finish!"

        response.raise_for_status()

        data = response.json()
        result = data.get("response", "").strip()
        logger.info(f"moondream vision click response: {result}")

        # 5. Parse the integer
        match = re.search(r'\b([1-9][0-9]?|100)\b', result)
        if not match:
            return f"Failed to find a valid grid number in the vision model's response: '{result}'."

        box_num = int(match.group(1))

        # 6. Click it!
        if box_num in coords_map:
            x, y = coords_map[box_num]
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.click()
            return f"Successfully clicked '{element_description}' at grid box {box_num} (coordinates {x}, {y})."
        else:
            return f"Error: The vision model returned box number {box_num}, which is out of bounds."

    except Exception as e:
        logger.exception("Failed to execute vision click")
        return f"Error during vision click: {e}"
