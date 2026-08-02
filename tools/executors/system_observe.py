import logging
import pyperclip
from tools.executors.ui_automation import _ui_cache

logger = logging.getLogger("jarvis.tools.system_observe")

def exec_observe_desktop() -> str:
    """
    Returns a unified snapshot of the desktop state:
    1. Active window title
    2. Clipboard contents (if text)
    3. UI DOM tree of the active window
    """
    output = []
    
    # 1. Active window
    active_window = "Unknown"
    try:
        # pyrefly: ignore [missing-import]
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active and active.title:
            active_window = active.title
    except Exception as e:
        logger.debug(f"Failed to get active window: {e}")
        
    output.append(f"### Active Window: {active_window}")
    
    # 2. Clipboard (Removed for privacy - use read_clipboard tool instead)
        
    # 3. UI DOM
    try:
        ui_cache = _ui_cache.get_cache()
        if ui_cache:
            output.append(ui_cache)
        else:
            output.append("### UI Elements: No UI cache available yet.")
    except Exception:
        output.append("### UI Elements: Error retrieving UI cache.")
        
    return "\n\n".join(output)
