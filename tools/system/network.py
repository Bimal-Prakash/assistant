import subprocess
import time
# pyrefly: ignore [missing-import]
import uiautomation as auto

def network_control(network_type: str, state: str) -> str:
    network_type = network_type.lower().strip()
    state = state.lower().strip()
    desired_state = 1 if state == "on" else 0

    try:
        if network_type == "wifi":
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:network-wifi"], shell=False)
            target_name = "Wi-Fi"
            search_terms = ["Wi-Fi", "WiFi"]
        elif network_type == "bluetooth":
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:bluetooth"], shell=False)
            target_name = "Bluetooth"
            search_terms = ["Bluetooth"]
        else:
            raise ValueError("Unsupported network type")

        time.sleep(1.5)
        
        window = auto.WindowControl(ClassName="ApplicationFrameWindow", Name="Settings")
        if not window.Exists(3, 1):
            return f"Opened Settings, but could not auto-toggle {target_name} (window not found)."

        toggle = None
        
        # Traverse the DOM to find the exact toggle button
        def find_toggle(ctrl):
            for child in ctrl.GetChildren():
                if any(term in child.Name for term in search_terms) and "toggle" in child.ClassName.lower():
                    return child
                res = find_toggle(child)
                if res: return res
            return None
            
        toggle = find_toggle(window)

        if not toggle:
            # Fallback: Just grab the first toggle switch on the screen
            first_toggle = window.Control(ClassName="ToggleSwitch")
            if first_toggle.Exists(0.5, 0.5):
                toggle = first_toggle

        if toggle:
            try:
                current = toggle.CurrentToggleState()
                # Only click if we need to change state
                if current != desired_state:
                    toggle.Click(simulateMove=False, waitTime=0.1)
                
                # Cleanup window
                if window.Exists(1, 1):
                    window.GetWindowPattern().Close()
                    
                return f"{target_name} turned {state}"
            except Exception as e:
                if window.Exists(1, 1):
                    window.GetWindowPattern().Close()
                return f"Failed to click {target_name} toggle: {e}"

        return f"Successfully opened {target_name} settings, please toggle manually."

    except Exception as e:
        return f"Error toggling {network_type}: {e}"
