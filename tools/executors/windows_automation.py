import logging
import webbrowser
from urllib.parse import quote_plus

# Import the exact same mixins used by the client!
from client.system.apps_core import AppManagementMixin
from client.system.agentic_core import AgenticControlMixin
from client.nlp.normalization import NormalizationMixin
from client.system.apps_search import StartMenuSearchMixin
from client.system.apps_startup import StartupMixin
from client.system.apps_spotify import SpotifyMixin

logger = logging.getLogger("jarvis.tools.windows_automation")

class BackendWindowsAutomator(
    AppManagementMixin,
    AgenticControlMixin,
    NormalizationMixin,
    StartMenuSearchMixin,
    StartupMixin,
    SpotifyMixin
):
    """
    A lightweight, headless instantiation of the client's PC execution mixins.
    Allows the backend to directly execute Windows UI actions without waiting
    for the remote client turn, enabling true observe-act-verify loops on PC.
    """
    def __init__(self):
        # Mocks for things the client normally provides
        self._start_menu_cache = None
        self._start_menu_last_build = 0
        self._startup_cache = None
        self._startup_last_build = 0
        
    def speak(self, text: str) -> None:
        logger.debug(f"Backend Automator spoke: {text}")

# Lazy Singleton
_automator_instance = None

def get_automator():
    global _automator_instance
    if _automator_instance is None:
        _automator_instance = BackendWindowsAutomator()
    return _automator_instance


def exec_pc_action(action_name: str, **kwargs) -> str:
    """
    Execute a PC client action directly in the backend.
    """
    action_name = action_name.lower()
    automator = get_automator()
    
    # Map tool names to the internal mixin methods
    if action_name == "open_app":
        app_name = kwargs.get("app", kwargs.get("app_name", ""))
        text = kwargs.get("text")
        if text and str(text).lower() in ["none", "null", "undefined", "n/a", "na"]:
            text = None
        return automator._open_app(app_name, post_text=text)
        
    if action_name == "close_app":
        app_name = kwargs.get("app", kwargs.get("app_name", ""))
        return automator._close_app(app_name)

    if action_name == "minimize_app":
        app_name = kwargs.get("app", kwargs.get("app_name", ""))
        return automator._minimize_app(app_name)

    if action_name == "open_website":
        url = str(kwargs.get("url", "")).strip()
        if not url:
            return "Website URL missing."
        webbrowser.open(url)
        return f"Opening website: {url}"

    if action_name == "send_whatsapp":
        phone = str(kwargs.get("phone", "")).strip()
        message = str(kwargs.get("message", "")).strip()
        if not phone:
            return "WhatsApp phone number is missing."
        url = f"https://wa.me/{phone}"
        if message:
            url = f"{url}?text={quote_plus(message)}"
        webbrowser.open(url)
        return "Opening WhatsApp message."
        
    if action_name == "type_string":
        text = kwargs.get("text", "")
        if text:
            try:
                import pyautogui
                pyautogui.write(text, interval=0.01)
                return f"Typed: {text}"
            except ImportError:
                return "Error: pyautogui is not installed."
        return "No text provided to type."

    agentic_methods = {
        "maximize_app": "_maximize_app",
        "restore_app": "_restore_app",
        "snap_window": "_snap_window",
        "hide_all_windows": "_hide_all_windows",
        "read_clipboard": "_read_clipboard",
        "write_clipboard": "_write_clipboard",
        "press_shortcut": "_press_shortcut",
        "check_performance": "_check_performance",
        "lock_pc": "_lock_pc",
        "empty_recycle_bin": "_empty_recycle_bin",
        "save_screenshot_to_desktop": "_take_screenshot",
        "show_notification": "_show_notification",
        "set_timer": "_set_timer",
        "open_folder": "_open_folder",
        "open_file": "_open_file",
        "whatsapp_call": "_whatsapp_call",
    }
    
    if action_name in agentic_methods:
        method_name = agentic_methods[action_name]
        method = getattr(automator, method_name, None)
        if method:
            # Map args
            if action_name in ["maximize_app", "restore_app"]:
                return method(kwargs.get("app", kwargs.get("app_name", "")))
            elif action_name == "snap_window":
                return method(kwargs.get("app", kwargs.get("app_name", "")), kwargs.get("direction", "left"))
            elif action_name == "write_clipboard":
                return method(kwargs.get("text", ""))
            elif action_name == "press_shortcut":
                return method(kwargs.get("shortcut", ""))
            elif action_name == "show_notification":
                return method(str(kwargs.get("title", "")), str(kwargs.get("message", "")))
            elif action_name == "set_timer":
                return method(int(kwargs.get("seconds", 0)), str(kwargs.get("label", "")))
            elif action_name == "open_folder":
                return method(str(kwargs.get("folder_path", "")))
            elif action_name == "open_file":
                return method(str(kwargs.get("file_path", "")))
            elif action_name == "whatsapp_call":
                return method(str(kwargs.get("contact_name", "")), str(kwargs.get("call_type", "audio")))
            else:
                return method()
                
    return f"Backend execution for {action_name} is not fully mapped."
