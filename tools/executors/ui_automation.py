import threading
import logging
import time
from typing import Dict, Any, List
import threading
logger = logging.getLogger("jarvis.tools.uiautomation")

try:
    # pyrefly: ignore [missing-import]
    import uiautomation as auto
    # Set global search timeout for uiautomation (default is 10 seconds, make it 3s to be fast)
    auto.uiautomation.SetGlobalSearchTimeout(3.0)
except ImportError:
    auto = None

def _is_interactive(control) -> bool:
    """Check if the control is an interactive element we care about."""
    try:
        ctype = control.ControlTypeName
        # List of interactive control types we want to expose to the LLM
        interactive_types = {
            "ButtonControl", "EditControl", "HyperlinkControl", 
            "MenuItemControl", "CheckBoxControl", "RadioButtonControl",
            "ComboBoxControl", "ListItemControl", "TabItemControl",
            "DocumentControl"
        }
        return ctype in interactive_types
    except Exception:
        return False

class UICacheManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(UICacheManager, cls).__new__(cls)
                cls._instance._cache = ""
                cls._instance._running = True
                cls._instance._thread = threading.Thread(target=cls._instance._worker, daemon=True)
                cls._instance._thread.start()
            return cls._instance

    def _worker(self):
        # Fix COM Threading error (CoInitialize)
        if auto is not None:
            _initializer = auto.UIAutomationInitializerInThread()
            
        while self._running:
            try:
                if auto is None:
                    time.sleep(5)
                    continue
                    
                window = auto.GetForegroundControl()
                if not window:
                    time.sleep(1)
                    continue
                    
                window_name = window.Name
                output = [f"### UI Elements for Active Window: '{window_name}'\n"]
                
                elements = []
                for control, depth in auto.WalkControl(window, maxDepth=6):
                    if _is_interactive(control):
                        name = control.Name
                        if not name:
                            try:
                                name = control.AutomationId
                            except Exception:
                                pass
                                
                        if name:
                            elements.append({
                                "name": name,
                                "type": control.ControlTypeName.replace("Control", ""),
                                "depth": depth
                            })
                            
                    if len(elements) >= 100:
                        output.append("*Note: Output truncated to 100 elements.*")
                        break
                        
                if not elements:
                    self._cache = f"Analyzed window '{window_name}' but found no named interactive elements. (This might be a custom-rendered app like a video game that doesn't expose native UI)."
                else:
                    for el in elements:
                        indent = "  " * (el["depth"] - 1)
                        output.append(f"{indent}- [{el['type']}] \"{el['name']}\"")
                    self._cache = "\n".join(output)
                    
            except Exception as e:
                logger.debug(f"UI Cache worker encountered an issue: {e}")
                
            time.sleep(1)

    def get_cache(self) -> str:
        return self._cache

# Initialize the singleton
_ui_cache = UICacheManager()

def exec_analyze_ui() -> str:
    """Returns the cached UI DOM tree instantly."""
    if auto is None:
        return "Error: uiautomation is not installed. Run 'pip install uiautomation'."
    
    cache_data = _ui_cache.get_cache()
    if not cache_data:
        return "UI cache is warming up. Please try again in a moment."
    return cache_data

def exec_click_ui_element(element_name: str) -> str:
    """Finds a UI element by name in the active window and clicks it."""
    if auto is None:
        return "Error: uiautomation is not installed."
        
    try:
        window = auto.GetForegroundControl()
        if not window:
            return "Could not find an active window."
            
        # Try to find exactly by name
        control = window.Control(Name=element_name, searchDepth=7)
        
        if not control.Exists(0, 0):
            # Fallback: search by AutomationId
            control = window.Control(AutomationId=element_name, searchDepth=7)
            if not control.Exists(0, 0):
                return f"Could not find any UI element named '{element_name}' in '{window.Name}'."
                
        # Move mouse and click
        control.Click(simulateMove=False)
        return f"Clicked the '{element_name}' element."
        
    except Exception as e:
        logger.exception("Failed to click UI element")
        return f"Error clicking element: {e}"

def exec_type_ui_element(element_name: str, text: str) -> str:
    """Finds an input field by name, focuses it, and types text."""
    if auto is None:
        return "Error: uiautomation is not installed."
        
    try:
        window = auto.GetForegroundControl()
        if not window:
            return "Could not find an active window."
            
        # Try to find exactly by name
        control = window.Control(Name=element_name, searchDepth=7)
        
        if not control.Exists(0, 0):
            # Fallback: search by AutomationId
            control = window.Control(AutomationId=element_name, searchDepth=7)
            if not control.Exists(0, 0):
                return f"Could not find any UI element named '{element_name}' in '{window.Name}'."
                
        # Set focus and type
        control.SetFocus()
        time.sleep(0.1)
        control.SendKeys(text)
        return f"Typed '{text}' into '{element_name}'."
        
    except Exception as e:
        logger.exception("Failed to type into UI element")
        return f"Error typing into element: {e}"
