"""
Tool Registry for the Jarvis Agent.

Each tool has a name, description, parameter schema, and an executor function.
The agent picks tools by name; the registry executes them and returns observations.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from tools.executors import (
    exec_get_system_info,
    exec_open_app, exec_close_app, exec_minimize_app,
    exec_open_website,
    exec_search_web,
    exec_run_terminal,
    exec_volume_control,
    exec_brightness_control,
    exec_power_control,
    exec_media_control,
    exec_network_control,
    exec_mic_control,
    exec_send_whatsapp, exec_whatsapp_call,
    exec_remember_fact, exec_recall_fact, exec_recall_last_command,
    exec_final_answer,
    exec_maximize_app, exec_restore_app, exec_focus_app, exec_hide_all_windows, exec_snap_window,
    exec_read_clipboard, exec_write_clipboard, exec_press_shortcut,
    exec_check_performance, exec_lock_pc, exec_empty_recycle_bin, exec_take_screenshot,
    exec_show_notification, exec_set_timer, exec_open_folder, exec_search_files,
    exec_analyze_screen, exec_ask_chatgpt_visually
)
from tools.executors.file_system import exec_list_directory, exec_read_file, exec_write_file

logger = logging.getLogger("jarvis.tools.registry")


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------
class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        executor: Callable[..., str],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.executor = executor

    def to_prompt_str(self) -> str:
        param_desc = ", ".join(
            f'{k} ({v.get("type","string")}): {v.get("description","")}'
            for k, v in self.parameters.get("properties", {}).items()
        )
        return f"- **{self.name}**: {self.description}  Args: {{{param_desc}}}"


# ---------------------------------------------------------------------------
# The Registry
# ---------------------------------------------------------------------------
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def prompt_block(self) -> str:
        return "\n".join(t.to_prompt_str() for t in self._tools.values())

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: tool '{name}' does not exist."
        try:
            return tool.executor(**args)
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            return f"Error executing {name}: {exc}"


# ===================================================================
# Build the default registry with all tools
# ===================================================================

def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(Tool(
        name="get_system_info",
        description="Get system information like current time, date, battery level, volume, or screen brightness.",
        parameters={"properties": {
            "query": {"type": "string", "description": "What to get: 'time', 'date', 'battery', 'volume', 'brightness', or 'all'"},
        }},
        executor=exec_get_system_info,
    ))

    registry.register(Tool(
        name="open_app",
        description="Open an application on the PC. Use 'text' for search queries (e.g., song name for Spotify). Do NOT use this to call people, use whatsapp_call instead.",
        parameters={"properties": {
            "app": {"type": "string", "description": "App name (e.g., 'spotify', 'chrome', 'whatsapp')"},
            "text": {"type": "string", "description": "Optional text to search/type after opening the app"},
        }},
        executor=exec_open_app,
    ))

    registry.register(Tool(
        name="close_app",
        description="Close a running application.",
        parameters={"properties": {
            "app": {"type": "string", "description": "App name to close"},
        }},
        executor=exec_close_app,
    ))

    registry.register(Tool(
        name="minimize_app",
        description="Minimize a running application window.",
        parameters={"properties": {
            "app": {"type": "string", "description": "App name to minimize"},
        }},
        executor=exec_minimize_app,
    ))

    registry.register(Tool(
        name="open_website",
        description="Open a URL in the default browser.",
        parameters={"properties": {
            "url": {"type": "string", "description": "Full URL to open"},
        }},
        executor=exec_open_website,
    ))

    registry.register(Tool(
        name="search_web",
        description="Search the internet and return top results. Use for questions you don't know the answer to.",
        parameters={"properties": {
            "query": {"type": "string", "description": "Search query"},
        }},
        executor=exec_search_web,
    ))

    registry.register(Tool(
        name="run_terminal",
        description="Execute a PowerShell command. Dangerous commands require user confirmation.",
        parameters={"properties": {
            "command": {"type": "string", "description": "PowerShell command to execute"},
        }},
        executor=exec_run_terminal,
    ))

    registry.register(Tool(
        name="ask_chatgpt",
        description="Visually opens ChatGPT in your browser, types the question, and reads the answer off the screen using the vision model. Use this if you are stuck or need help from a smarter AI.",
        parameters={"properties": {
            "query": {"type": "string", "description": "The exact question or prompt to type into ChatGPT"}
        }},
        executor=exec_ask_chatgpt_visually,
    ))

    registry.register(Tool(
        name="volume_control",
        description="Control the PC volume.",
        parameters={"properties": {
            "level": {"type": "string", "description": "'up', 'down', 'mute', 'max', or a percentage like '50'"},
        }},
        executor=exec_volume_control,
    ))

    registry.register(Tool(
        name="brightness_control",
        description="Control the screen brightness.",
        parameters={"properties": {
            "level": {"type": "string", "description": "'up', 'down', 'max', 'min', or a percentage like '50'"},
        }},
        executor=exec_brightness_control,
    ))

    registry.register(Tool(
        name="power_control",
        description="Shutdown, restart, or sleep the PC. Shutdown/restart require confirmation.",
        parameters={"properties": {
            "type": {"type": "string", "description": "'shutdown', 'restart', or 'sleep'"},
        }},
        executor=exec_power_control,
    ))

    registry.register(Tool(
        name="media_control",
        description="GLOBAL media playback control (play, pause, next, previous). Use this tool IMMEDIATELY for any play/pause/stop/next music commands. It works globally for Spotify, YouTube, etc. DO NOT use analyze_screen or open_app first.",
        parameters={"properties": {
            "state": {"type": "string", "description": "'play_pause', 'next', or 'previous'"},
        }},
        executor=exec_media_control,
    ))

    registry.register(Tool(
        name="network_control",
        description="Control WiFi or Bluetooth.",
        parameters={"properties": {
            "type": {"type": "string", "description": "'wifi' or 'bluetooth'"},
            "state": {"type": "string", "description": "'on', 'off', or 'open'"},
        }},
        executor=exec_network_control,
    ))

    registry.register(Tool(
        name="mic_control",
        description="Mute or unmute the microphone.",
        parameters={"properties": {
            "state": {"type": "string", "description": "'mute' or 'unmute'"},
        }},
        executor=exec_mic_control,
    ))

    registry.register(Tool(
        name="send_whatsapp",
        description="Send a WhatsApp message to a phone number.",
        parameters={"properties": {
            "phone": {"type": "string", "description": "Phone number with country code"},
            "message": {"type": "string", "description": "Message text to send"},
        }},
        executor=exec_send_whatsapp,
    ))



    registry.register(Tool(
        name="remember_fact",
        description="Remember a piece of information about the user for later recall.",
        parameters={"properties": {
            "key": {"type": "string", "description": "What to remember (e.g., 'name', 'favorite_color')"},
            "value": {"type": "string", "description": "The value to remember"},
        }},
        executor=exec_remember_fact,
    ))

    registry.register(Tool(
        name="recall_fact",
        description="Recall a previously remembered fact about the user.",
        parameters={"properties": {
            "key": {"type": "string", "description": "What to recall (e.g., 'name')"},
        }},
        executor=exec_recall_fact,
    ))

    registry.register(Tool(
        name="recall_last_command",
        description="Recall what the user's last command was.",
        parameters={"properties": {}},
        executor=exec_recall_last_command,
    ))

    registry.register(Tool(
        name="final_answer",
        description="Give your final spoken response to the user. Use when you have the answer or completed the task.",
        parameters={"properties": {
            "text": {"type": "string", "description": "What to say to the user"},
        }},
        executor=exec_final_answer,
    ))

    registry.register(Tool(name="maximize_app", description="Maximize a specific application window.", parameters={"properties": {"app": {"type": "string", "description": "App name"}}}, executor=exec_maximize_app))
    registry.register(Tool(name="restore_app", description="Restore a specific application window to normal size.", parameters={"properties": {"app": {"type": "string", "description": "App name"}}}, executor=exec_restore_app))
    registry.register(Tool(name="focus_app", description="Bring an application to the foreground.", parameters={"properties": {"app": {"type": "string", "description": "App name"}}}, executor=exec_focus_app))
    registry.register(Tool(name="hide_all_windows", description="Minimize all windows to show the desktop.", parameters={"properties": {}}, executor=exec_hide_all_windows))
    registry.register(Tool(name="snap_window", description="Snap active window to a side of the screen.", parameters={"properties": {"app": {"type": "string", "description": "App name"}, "direction": {"type": "string", "description": "'left', 'right', 'top', 'bottom'"}}}, executor=exec_snap_window))
    registry.register(Tool(name="read_clipboard", description="Read the current contents of the system clipboard.", parameters={"properties": {}}, executor=exec_read_clipboard))
    registry.register(Tool(name="write_clipboard", description="Write text to the system clipboard.", parameters={"properties": {"text": {"type": "string", "description": "Text to write"}}}, executor=exec_write_clipboard))
    registry.register(Tool(name="press_shortcut", description="Press a keyboard shortcut.", parameters={"properties": {"shortcut": {"type": "string", "description": "Keyboard shortcut like 'ctrl+c'"}}}, executor=exec_press_shortcut))
    registry.register(Tool(name="check_performance", description="Check system CPU, RAM, and Disk usage.", parameters={"properties": {}}, executor=exec_check_performance))
    registry.register(Tool(name="lock_pc", description="Lock the Windows workstation.", parameters={"properties": {}}, executor=exec_lock_pc))
    registry.register(Tool(name="empty_recycle_bin", description="Empty the Windows recycle bin.", parameters={"properties": {}}, executor=exec_empty_recycle_bin))
    registry.register(Tool(name="take_screenshot", description="Take a screenshot of the current screen and save it to desktop.", parameters={"properties": {}}, executor=exec_take_screenshot))
    registry.register(Tool(name="show_notification", description="Show a native Windows toast notification.", parameters={"properties": {"title": {"type": "string", "description": "Notification title"}, "message": {"type": "string", "description": "Notification message"}}}, executor=exec_show_notification))
    registry.register(Tool(name="set_timer", description="Set a countdown timer in seconds.", parameters={"properties": {"seconds": {"type": "integer", "description": "Seconds to wait"}, "label": {"type": "string", "description": "Timer label"}}}, executor=exec_set_timer))
    registry.register(Tool(name="open_folder", description="Open a specific folder in Windows Explorer.", parameters={"properties": {"folder_path": {"type": "string", "description": "Path to the folder, or 'downloads', 'documents', etc."}}}, executor=exec_open_folder))
    registry.register(Tool(name="search_files", description="Search the file system for a specific file by name.", parameters={"properties": {"query": {"type": "string", "description": "File name to search for"}}}, executor=exec_search_files))
    registry.register(Tool(
        name="whatsapp_call",
        description="Initiate an audio or video call on WhatsApp. Use this tool IMMEDIATELY when the user asks to call someone, do not ask for more information first.",
        parameters={
            "properties": {
                "contact_name": {"type": "string", "description": "The exact, full name of the contact as spoken by the user. Do not truncate, split, or remove numbers/suffixes (e.g., if user says 'adithyaponnu26', extract 'adithyaponnu26')."},
                "call_type": {"type": "string", "description": "'audio' or 'video'. Default to 'audio' unless the user explicitly says 'video call' or 'video'."}
            },
            "required": ["contact_name"]
        },
        executor=exec_whatsapp_call
    ))

    registry.register(Tool(
        name="analyze_screen",
        description="Take a screenshot of the user's screen and use a Vision AI model to answer a question about what is on the screen.",
        parameters={"properties": {
            "query": {"type": "string", "description": "What to ask the vision model about the screen (e.g., 'What app is open?', 'Read the error message')"}
        }, "required": ["query"]},
        executor=exec_analyze_screen,
    ))

    registry.register(Tool(
        name="list_directory",
        description="List all files and folders in a specific directory. Useful for exploring the file system.",
        parameters={"properties": {
            "path": {"type": "string", "description": "Absolute or relative directory path"}
        }},
        executor=exec_list_directory,
    ))

    registry.register(Tool(
        name="read_file",
        description="Read the text content of a file. Use this to read scripts, logs, or documents.",
        parameters={"properties": {
            "file_path": {"type": "string", "description": "Absolute or relative file path"},
            "max_lines": {"type": "integer", "description": "Maximum number of lines to read (default 200)"}
        }, "required": ["file_path"]},
        executor=exec_read_file,
    ))

    registry.register(Tool(
        name="write_file",
        description="Write text content to a file. Overwrites the file if it exists.",
        parameters={"properties": {
            "file_path": {"type": "string", "description": "Absolute or relative file path"},
            "content": {"type": "string", "description": "The exact text content to write to the file"}
        }, "required": ["file_path", "content"]},
        executor=exec_write_file,
    ))

    return registry
