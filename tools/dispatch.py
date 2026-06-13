import logging
from typing import Any, Dict
from .system.volume import volume_control
from .system.brightness import brightness_control
from .system.power import power_control
from .system.mic import mic_control
from .system.media import media_control
from .system.network import network_control
from .web import search_web
import subprocess

logger = logging.getLogger("jarvis.pc_controls")

def execute_pc_system_action(action_obj: Dict[str, Any]) -> Dict[str, Any]:
    action = str(action_obj.get("action", "")).lower()

    try:
        if action == "volume_control":
            level = str(action_obj.get("level", "")).lower()
            message = volume_control(level)
        elif action == "brightness_control":
            level = str(action_obj.get("level", "")).lower()
            message = brightness_control(level)
        elif action == "power_control":
            power_type = str(action_obj.get("type", "")).lower()
            message = power_control(power_type, delay_seconds=3)
        elif action == "mic_control":
            state = str(action_obj.get("state", "")).lower()
            message = mic_control(state)
        elif action == "media_control":
            command = str(action_obj.get("state", action_obj.get("type", ""))).lower()
            message = media_control(command)
        elif action == "network_control":
            network_type = str(action_obj.get("type", "")).lower()
            state = str(action_obj.get("state", "")).lower()
            message = network_control(network_type, state)
        elif action == "search_web":
            query = str(action_obj.get("query", ""))
            message = search_web(query)
        elif action == "run_terminal":
            command = str(action_obj.get("command", ""))
            try:
                result = subprocess.run(
                    ["powershell", "-Command", command],
                    capture_output=True, text=True, timeout=10
                )
                output = result.stdout.strip()
                err = result.stderr.strip()
                if err:
                    message = f"Terminal Output:\n{output}\nTerminal Error:\n{err}"
                else:
                    message = f"Terminal Output:\n{output}"
            except Exception as cmd_exc:
                message = f"Failed to run terminal: {cmd_exc}"
        else:
            return {"ok": False, "message": "Unsupported PC control action"}

        return {"ok": True, "message": message}
    except Exception as exc:
        logger.exception("PC control failed for action=%s", action)
        return {"ok": False, "message": f"PC control failed: {exc}"}
