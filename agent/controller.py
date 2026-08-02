import logging
from typing import Dict, Any

logger = logging.getLogger("jarvis.agent.controller")

def verify_action_success(action_name: str, args: Dict[str, Any], pre_state: str, post_state: str) -> str:
    """
    Verifies if the action succeeded based on the before/after desktop state.
    Returns an empty string if it appears successful, or an error string if it failed.
    """
    pre_lower = pre_state.lower()
    post_lower = post_state.lower()
    
    if action_name == "open_app":
        app = args.get("app_name", "").lower()
        # If the app name is not in the active window title after opening, it might have failed.
        if app and app not in post_lower:
            return f"Verification Failed: You tried to open '{app}', but the active window is now reporting something else. Did it open correctly? Check the UI Elements."
            
    elif action_name == "close_app":
        app = args.get("app", "").lower()
        # If we tried to close an app, and it is STILL the active window, it failed.
        if app and app in post_lower.split("### clipboard snippet")[0]:  # Only check window/UI part, not clipboard
            return f"Verification Failed: You tried to close '{app}', but it still appears to be open or active."
            

    # For many actions (like getting system info, or web search), 
    # the tool's own string output is the verification, so we trust it if it didn't throw an exception.
    
    return ""
