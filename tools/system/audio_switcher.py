import subprocess
import time
try:
    # pyrefly: ignore [missing-import]
    import uiautomation as auto
except ImportError:
    auto = None

def switch_audio_output(device_name: str) -> str:
    if auto is None:
        return "Error: uiautomation is not installed."
        
    device_name = device_name.lower().strip()
    try:
        # Open Sound settings
        subprocess.Popen(["cmd", "/c", "start", "ms-settings:sound"], shell=False)
        time.sleep(0.5) # Give it half a second to launch
        
        window = auto.WindowControl(ClassName="ApplicationFrameWindow", Name="Settings")
        # Poll up to 5 seconds to ensure budget laptops have enough time to load the heavy settings app
        if not window.Exists(5, 1):
            return "Opened Settings, but could not auto-switch audio (window not found)."

        found_device = None
        
        def find_device_radio(ctrl):
            for child in ctrl.GetChildren():
                if child.ControlType in (auto.ControlType.RadioButtonControl, auto.ControlType.ListItemControl, auto.ControlType.ButtonControl):
                    if device_name in child.Name.lower():
                        return child
                res = find_device_radio(child)
                if res: return res
            return None

        found_device = find_device_radio(window)

        if found_device:
            found_name = found_device.Name
            try:
                sel_pattern = found_device.GetSelectionItemPattern()
                if sel_pattern:
                    sel_pattern.Select()
                else:
                    found_device.Click(simulateMove=False, waitTime=0.5)
                    
                time.sleep(0.5)
                if window.Exists(1, 1):
                    window.GetWindowPattern().Close()
                return f"Switched audio output to '{found_name}'"
            except Exception as e:
                if window.Exists(1, 1):
                    window.GetWindowPattern().Close()
                return f"Found '{found_name}', but failed to select it: {e}"

        return f"Opened Sound settings, but could not find a device matching '{device_name}'."
    except Exception as e:
        return f"Error switching audio output: {e}"
