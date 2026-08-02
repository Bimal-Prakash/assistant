"""
Tool Registry for the Jarvis Agent.

Each tool has a name, description, parameter schema, and an executor function.
The agent picks tools by name; the registry executes them and returns observations.
"""

from tools.executors import exec_get_current_media_info
from tools.executors import exec_remember_fact
import logging
from typing import Any, Callable, Dict, List, Optional


from tools.executors.apps import exec_type_string
from tools.executors import (
    exec_get_system_info,
    exec_open_app, exec_close_app, exec_minimize_app,
    exec_open_website,
    exec_search_web,
    exec_run_terminal,
    exec_volume_control,
    exec_brightness_control,
    exec_power_control,
    exec_media_control, exec_get_current_media_info,
    exec_network_control,
    exec_mic_control,
    exec_send_whatsapp, exec_whatsapp_call, exec_telegram_call,
    exec_search_memory,
    exec_final_answer,
    exec_switch_audio_output,
    exec_maximize_app, exec_restore_app, exec_hide_all_windows, exec_snap_window,
    exec_read_clipboard, exec_write_clipboard, exec_press_shortcut,
    exec_check_performance, exec_lock_pc, exec_empty_recycle_bin, exec_take_screenshot,
    exec_show_notification, exec_set_timer, exec_open_folder, exec_open_file, exec_search_files,
    exec_look_at_screen, exec_ask_chatgpt_visually, exec_vision_click,
    exec_analyze_ui, exec_click_ui_element, exec_type_ui_element
)
from tools.executors.file_system import exec_list_directory, exec_read_file, exec_write_file
from tools.executors.obsidian import exec_search_obsidian, exec_read_obsidian_note
from tools.executors.system_observe import exec_observe_desktop

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
        risk_tier: str = "safe",
        data_access: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.executor = executor
        self.risk_tier = risk_tier
        self.data_access = data_access or []

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
        self._categories = {
            "system_control": {"get_system_info", "volume_control", "brightness_control", "power_control", "network_control", "mic_control", "switch_audio_output", "set_timer", "check_performance"},
            "app_control": {"open_app", "close_app", "minimize_app", "maximize_app", "restore_app", "hide_all_windows", "snap_window", "run_terminal", "media_control", "get_current_media_info"},
            "web": {"open_website", "search_web"},
            "obsidian": {"search_obsidian", "read_obsidian_note"},
            "memory": {"remember_fact", "search_memory"},
            "file": {"list_directory", "read_file", "write_file", "empty_recycle_bin", "open_folder", "open_file", "search_files"},
            "chat": {"send_whatsapp", "whatsapp_call", "telegram_call"},
            "vision": {"take_screenshot", "save_screenshot_to_desktop", "look_at_screen", "ask_chatgpt", "vision_click", "analyze_ui", "click_ui_element", "type_ui_element"},
            "system_interact": {"read_clipboard", "write_clipboard", "press_shortcut", "type_string", "show_notification", "observe_desktop"}
        }

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def prompt_block(self, category: Optional[str] = None) -> str:
        if category and category in self._categories:
            allowed_tools = self._categories[category] | {"final_answer"}
            tools = [t for name, t in self._tools.items() if name in allowed_tools]
            if not tools:
                tools = self.all_tools()
        else:
            tools = self.all_tools()
        return "\n".join(t.to_prompt_str() for t in tools)

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: tool '{name}' does not exist."
        if "required" in tool.parameters:
            missing = [req for req in tool.parameters["required"] if req not in args]
            if missing:
                return f"Error: Missing required arguments: {', '.join(missing)}. Do NOT retry this tool blindly. If you lack the required info, use final_answer to ask the user!"

        try:
            client_device = args.get("client_device", "pc")
            
            # Check if this tool is a client action mapped to the backend native execution
            CLIENT_ACTIONS = {
                "open_app", "close_app", "minimize_app", "maximize_app", "restore_app",
                "hide_all_windows", "snap_window", "read_clipboard",
                "write_clipboard", "press_shortcut", "check_performance", "lock_pc",
                "empty_recycle_bin", "save_screenshot_to_desktop", "show_notification", "set_timer",
                "open_folder", "open_file", "whatsapp_call", "open_website", "send_whatsapp", "type_string"
            }
            if name in CLIENT_ACTIONS and client_device == "pc":
                from tools.executors.windows_automation import exec_pc_action
                return exec_pc_action(name, **args)
            
            # Execute normally for android, or non-client tools
            if "client_device" in args:
                del args["client_device"]
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
        name="observe_desktop",
        description="Returns a unified snapshot of the desktop state, including the active window title, clipboard snippet, and the UI elements of the active window.",
        parameters={"properties": {}},
        executor=exec_observe_desktop,
    ))

    registry.register(Tool(
        name="get_system_info",
        description="Get time, date, battery, volume, or brightness.",
        parameters={"properties": {
            "query": {"type": "string", "description": "What to get: 'time', 'date', 'battery', 'volume', 'brightness', or 'all'"},
        }, "required": ["query"]},
        executor=exec_get_system_info,
    ))

    registry.register(Tool(
        name="open_app",
        description="Open an application (like Notepad, Chrome, Spotify) or a website (like Facebook, YouTube). ALWAYS use this to 'open' an app, 'play' a song/video, 'switch' to an app, or switch to a browser tab. DO NOT use 'open_file' for this.",
        parameters={"properties": {
            "app": {"type": "string", "description": "App name (e.g., 'notepad', 'chrome', 'whatsapp')"},
            "text": {"type": "string", "description": "Text to search or type. If none, omit this parameter."},
        }, "required": ["app"]},
        executor=exec_open_app,
    ))

    registry.register(Tool(
        name="close_app",
        description="MANDATORY tool to close, kill, or quit a running application. You MUST use this tool to close apps.",
        parameters={"properties": {
            "app": {"type": "string", "description": "App name to close"},
        }, "required": ["app"]},
        executor=exec_close_app,
        risk_tier="sensitive",
        data_access=["filesystem", "system"],
    ))

    registry.register(Tool(
        name="minimize_app",
        description="MANDATORY tool to minimize or hide a running application window. You MUST use this tool to minimize apps.",
        parameters={"properties": {
            "app": {"type": "string", "description": "App name to minimize"},
        }, "required": ["app"]},
        executor=exec_minimize_app,
    ))

    registry.register(Tool(
        name="open_website",
        description="Open a URL in the default browser.",
        parameters={"properties": {
            "url": {"type": "string", "description": "Full URL to open"},
        }, "required": ["url"]},
        executor=exec_open_website,
        risk_tier="sensitive",
        data_access=["network"],
    ))

    registry.register(Tool(
        name="search_web",
        description="Search the internet, returns top results. Does NOT save files.",
        parameters={"properties": {
            "query": {"type": "string", "description": "Search query"},
        }, "required": ["query"]},
        executor=exec_search_web,
        data_access=["network"],
    ))

    registry.register(Tool(
        name="run_terminal",
        description="Execute a PowerShell command. Dangerous commands require user confirmation.",
        parameters={"properties": {
            "command": {"type": "string", "description": "PowerShell command to execute"},
        }, "required": ["command"]},
        executor=exec_run_terminal,
        risk_tier="dangerous",
        data_access=["filesystem", "system"],
    ))

    registry.register(Tool(
        name="ask_chatgpt",
        description="Opens ChatGPT in browser, types query, reads answer via clipboard. Use when stuck on complex tasks.",
        parameters={"properties": {
            "query": {"type": "string", "description": "The exact question or prompt to type into ChatGPT"}
        }, "required": ["query"]},
        executor=exec_ask_chatgpt_visually,
    ))

    registry.register(Tool(
        name="analyze_ui",
        description="Reads the active window's UI DOM tree and returns a list of interactive elements (buttons, inputs, etc). Use this FIRST before clicking or typing to find the exact element names.",
        parameters={"properties": {}},
        executor=exec_analyze_ui,
        risk_tier="sensitive",
        data_access=["sensitive_data"],
    ))

    registry.register(Tool(
        name="click_ui_element",
        description="Finds a UI element by exact name or ID in the active window and clicks it. Use analyze_ui first to find the exact name.",
        parameters={"properties": {
            "element_name": {"type": "string", "description": "The exact Name or AutomationId of the element to click"}
        }, "required": ["element_name"]},
        executor=exec_click_ui_element,
    ))

    registry.register(Tool(
        name="type_ui_element",
        description="Finds an input field by exact name or ID, focuses it, and types text. Use analyze_ui first to find the exact name.",
        parameters={"properties": {
            "element_name": {"type": "string", "description": "The exact Name or AutomationId of the input field"},
            "text": {"type": "string", "description": "The text to type"}
        }, "required": ["element_name", "text"]},
        executor=exec_type_ui_element,
    ))


    registry.register(Tool(
        name="volume_control",
        description="Control the PC volume.",
        parameters={"properties": {
            "level": {"type": "string", "description": "'up', 'down', 'mute', 'max', or a percentage like '50'"},
        }, "required": ["level"]},
        executor=exec_volume_control,
    ))

    registry.register(Tool(
        name="brightness_control",
        description="Control the screen brightness.",
        parameters={"properties": {
            "level": {"type": "string", "description": "'up', 'down', 'max', 'min', or a percentage like '50'"},
        }, "required": ["level"]},
        executor=exec_brightness_control,
    ))

    registry.register(Tool(
        name="power_control",
        description="Shutdown, restart, or sleep the PC. Shutdown/restart require confirmation.",
        parameters={"properties": {
            "type": {"type": "string", "description": "'shutdown', 'restart', or 'sleep'"},
        }, "required": ["type"]},
        executor=exec_power_control,
        risk_tier="dangerous",
        data_access=["filesystem", "system"],
    ))

    registry.register(Tool(
        name="switch_audio_output",
        description="Switch the Windows audio output device (e.g. to 'headphones', 'speakers', 'earbuds').",
        parameters={"properties": {
            "device_name": {"type": "string", "description": "The name of the audio device to switch to"}
        }, "required": ["device_name"]},
        executor=exec_switch_audio_output,
    ))

    registry.register(Tool(
        name="media_control",
        description="Global play/pause/next/previous for any active media player.",
        parameters={"properties": {
            "state": {"type": "string", "description": "'play_pause', 'next', or 'previous'"},
        }, "required": ["state"]},
        executor=exec_media_control,
    ))

    registry.register(Tool(
        name="get_current_media_info",
        description="Get the title, artist, and playback status of the currently playing media. Use this when the user asks 'what song is this', 'what am I listening to', or 'what is playing'.",
        parameters={"properties": {}},
        executor=exec_get_current_media_info,
    ))

    registry.register(Tool(
        name="network_control",
        description="Control WiFi or Bluetooth.",
        parameters={"properties": {
            "type": {"type": "string", "description": "'wifi' or 'bluetooth'"},
            "state": {"type": "string", "description": "'on', 'off', or 'open'"},
        }, "required": ["type", "state"]},
        executor=exec_network_control,
    ))

    registry.register(Tool(
        name="mic_control",
        description="Mute or unmute the microphone.",
        parameters={"properties": {
            "state": {"type": "string", "description": "'mute' or 'unmute'"},
        }, "required": ["state"]},
        executor=exec_mic_control,
    ))

    registry.register(Tool(
        name="send_whatsapp",
        description="Send a WhatsApp message to a phone number.",
        parameters={"properties": {
            "phone": {"type": "string", "description": "Phone number with country code"},
            "message": {"type": "string", "description": "Message text to send"},
        }, "required": ["phone", "message"]},
        executor=exec_send_whatsapp,
        risk_tier="external",
        data_access=["network"],
    ))



    # We restore remember_fact to append to the Obsidian vault
    registry.register(Tool(
        name="remember_fact",
        description="Remember a piece of information, preference, or file path (e.g., the correct path for a resume). This saves it permanently to the user's Obsidian vault.",
        parameters={"properties": {
            "key": {"type": "string", "description": "What to remember (e.g., 'resume_path', 'favorite_color')"},
            "value": {"type": "string", "description": "The value or absolute path to remember"},
        }, "required": ["key", "value"]},
        executor=exec_remember_fact,
    ))

    # registry.register(Tool(
    #     name="recall_fact",
    #     description="Recall a previously remembered fact about the user.",
    #     parameters={"properties": {
    #         "key": {"type": "string", "description": "What to recall (e.g., 'name')"},
    #     }, "required": ["key"]},
    #     executor=exec_recall_fact,
    # ))

    #     name="recall_last_command",
    #     description="Recall what the user's last command was.",
    #     parameters={"properties": {}},
    #     executor=exec_recall_last_command,
    #     risk_tier="sensitive",
    #     data_access=["sensitive_data"],
    # ))

    registry.register(Tool(
        name="final_answer",
        description="Give your final spoken response to the user. Use when you have the answer, completed the task, or need to ask the user a question.",
        parameters={"properties": {
            "text": {"type": "string", "description": "What to say to the user"},
        }, "required": ["text"]},
        executor=exec_final_answer,
    ))

    # Fallback alias for models that hallucinate an 'ask_user' tool
    registry.register(Tool(
        name="ask_user",
        description="Ask the user a question. This is exactly the same as final_answer.",
        parameters={"properties": {
            "question": {"type": "string", "description": "The question to ask"}
        }, "required": ["question"]},
        executor=lambda question: exec_final_answer(text=question),
    ))

    # Fallback aliases for shutdown hallucinations
    registry.register(Tool(
        name="shutdown_pc",
        description="Shutdown the PC.",
        parameters={"properties": {}},
        executor=lambda **kwargs: exec_power_control(type="shutdown"),
    ))

    registry.register(Tool(
        name="shutdown",
        description="Shutdown the PC.",
        parameters={"properties": {}},
        executor=lambda **kwargs: exec_power_control(type="shutdown"),
    ))

    registry.register(Tool(name="maximize_app", description="Maximize a specific application window.", parameters={"properties": {"app": {"type": "string", "description": "App name"}}, "required": ["app"]}, executor=exec_maximize_app))
    registry.register(Tool(name="restore_app", description="Restore a specific application window to normal size.", parameters={"properties": {"app": {"type": "string", "description": "App name"}}, "required": ["app"]}, executor=exec_restore_app))
    # Removed focus_app entirely because the 3B model confuses it with open_app. open_app handles focusing on Windows anyway.
    registry.register(Tool(name="hide_all_windows", description="Minimize all windows to show the desktop.", parameters={"properties": {}}, executor=exec_hide_all_windows))
    registry.register(Tool(name="snap_window", description="Snap active window to a side of the screen.", parameters={"properties": {"app": {"type": "string", "description": "App name"}, "direction": {"type": "string", "description": "'left', 'right', 'top', 'bottom'"}}, "required": ["app", "direction"]}, executor=exec_snap_window))
    registry.register(Tool(name="read_clipboard", description="Read clipboard contents (text or image).", parameters={"properties": {}}, executor=exec_read_clipboard, risk_tier="sensitive", data_access=["sensitive_data"]))
    registry.register(Tool(name="write_clipboard", description="Write text to the system clipboard.", parameters={"properties": {"text": {"type": "string", "description": "Text to write"}}, "required": ["text"]}, executor=exec_write_clipboard))
    registry.register(Tool(name="press_shortcut", description="Press a keyboard shortcut or media key for playback.", parameters={"properties": {"shortcut": {"type": "string", "description": "Shortcut or media key ('playpause', 'nexttrack', 'prevtrack')"}}, "required": ["shortcut"]}, executor=exec_press_shortcut))
    registry.register(Tool(name="check_performance", description="Check system CPU, RAM, and Disk usage.", parameters={"properties": {}}, executor=exec_check_performance))
    registry.register(Tool(name="lock_pc", description="Lock the Windows workstation.", parameters={"properties": {}}, executor=exec_lock_pc))
    registry.register(Tool(name="empty_recycle_bin", description="Empty the Windows recycle bin.", parameters={"properties": {}}, executor=exec_empty_recycle_bin, risk_tier="dangerous", data_access=["filesystem", "system"]))
    registry.register(Tool(name="save_screenshot_to_desktop", description="Save a screenshot to desktop. DO NOT use this to look at or read the screen. Use look_at_screen instead.", parameters={"properties": {}}, executor=exec_take_screenshot))
    registry.register(Tool(name="show_notification", description="Show a native Windows toast notification.", parameters={"properties": {"title": {"type": "string", "description": "Notification title"}, "message": {"type": "string", "description": "Notification message"}}, "required": ["title", "message"]}, executor=exec_show_notification))
    registry.register(Tool(name="set_timer", description="Set a countdown timer in seconds.", parameters={"properties": {"seconds": {"type": "integer", "description": "Seconds to wait"}, "label": {"type": "string", "description": "Timer label"}}, "required": ["seconds", "label"]}, executor=exec_set_timer))
    registry.register(Tool(name="open_folder", description="Open a specific folder or directory in Windows Explorer. DO NOT use this to open files or documents.", parameters={"properties": {"folder_path": {"type": "string", "description": "Path to the folder, or 'downloads', 'documents', etc."}}, "required": ["folder_path"]}, executor=exec_open_folder))
    registry.register(Tool(name="open_file", description="Open a document or file using its EXACT ABSOLUTE PATH. DO NOT guess the path or pass a partial name. You MUST use 'search_files' first to find the absolute path.", parameters={"properties": {"file_path": {"type": "string", "description": "The exact absolute path of the file to open (e.g., 'C:\\Users\\name\\Downloads\\resume.pdf')"}}, "required": ["file_path"]}, executor=exec_open_file))
    registry.register(Tool(name="search_files", description="Search the file system for a file by exact or partial name. Optionally specify a path to search in.", parameters={"properties": {"query": {"type": "string", "description": "File name or partial name to search for (e.g. 'resume')"}, "path": {"type": "string", "description": "Optional path or folder name to search in (e.g. 'Downloads')"}}, "required": ["query"]}, executor=exec_search_files))
    registry.register(Tool(
        name="whatsapp_call",
        description="Call a contact on WhatsApp or end an ongoing call. Automatically searches and opens the app.",
        parameters={"properties": {
            "contact_name": {"type": "string", "description": "The name of the contact (not required for ending a call)"},
            "call_type": {"type": "string", "description": "'audio', 'video', or 'end'"}
        }, "required": ["call_type"]},
        executor=exec_whatsapp_call,
        risk_tier="external",
        data_access=["network"],
    ))

    registry.register(Tool(
        name="telegram_call",
        description="Call a contact on Telegram or end an ongoing call. Automatically searches and opens the app.",
        parameters={"properties": {
            "contact_name": {"type": "string", "description": "The name of the contact (not required for ending a call)"},
            "call_type": {"type": "string", "description": "'audio', 'video', or 'end'"}
        }, "required": ["call_type"]},
        executor=exec_telegram_call,
        risk_tier="external",
        data_access=["network"],
    ))

    registry.register(Tool(
        name="look_at_screen",
        description="Take a screenshot of the user's screen and use a Vision AI model to answer a question about what is on the screen.",
        parameters={"properties": {
            "query": {"type": "string", "description": "What to ask the vision model about the screen (e.g., 'What app is open?', 'Read the error message')"}
        }, "required": ["query"]},
        executor=exec_look_at_screen,
        risk_tier="sensitive",
        data_access=["sensitive_data"],
    ))

    registry.register(Tool(
        name="vision_click",
        description="Take a screenshot, overlay a grid, and use the Vision AI model to find and click on a specific UI element. Use this when standard UI automation fails or you don't know where a button is.",
        parameters={"properties": {
            "element_description": {"type": "string", "description": "What to click on (e.g., 'the WhatsApp call button', 'the heart icon')"}
        }, "required": ["element_description"]},
        executor=exec_vision_click,
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
        risk_tier="sensitive",
        data_access=["sensitive_data"],
    ))

    registry.register(Tool(
        name="write_file",
        description="Write text content to a text file on the hard drive. Overwrites the file if it exists. DO NOT use this to write into an application window (like Notepad); use 'type_text' for that instead.",
        parameters={"properties": {
            "file_path": {"type": "string", "description": "Absolute or relative file path"},
            "content": {"type": "string", "description": "The exact text content to write to the file"}
        }, "required": ["file_path", "content"]},
        executor=exec_write_file,
        risk_tier="dangerous",
        data_access=["filesystem", "system"],
    ))

    registry.register(Tool(
        name="type_text",
        description="Type text into whatever application is currently focused and active (e.g. into Notepad, Word, or Chrome). Use this INSTEAD of 'write_file' if you are trying to write into an open application.",
        parameters={"properties": {
            "text": {"type": "string", "description": "The exact text to type"}
        }, "required": ["text"]},
        executor=exec_type_string,
    ))

    registry.register(Tool(
        name="search_obsidian",
        description="Search all markdown files in the user's Obsidian vault for a specific topic or keyword. Use this when the user refers to 'this' or 'that' related to their notes.",
        parameters={"properties": {
            "query": {"type": "string", "description": "The word or phrase to search for in notes"}
        }, "required": ["query"]},
        executor=exec_search_obsidian,
        risk_tier="sensitive",
        data_access=["sensitive_data"],
    ))

    registry.register(Tool(
        name="search_memory",
        description="Search BOTH your conversational memory and the user's Obsidian notes using AI vector search simultaneously. ALWAYS use this whenever you need to recall past conversations, or find personal information about the user, their family, their friends, or their preferences.",
        parameters={"properties": {
            "query": {"type": "string", "description": "The concept or meaning to search for"}
        }, "required": ["query"]},
        executor=exec_search_memory,
        risk_tier="sensitive",
        data_access=["sensitive_data"],
    ))

    registry.register(Tool(
        name="read_obsidian_note",
        description="Read the entire content of a specific Obsidian note by its file name.",
        parameters={"properties": {
            "note_name": {"type": "string", "description": "The exact name of the note to read (with or without .md)"}
        }, "required": ["note_name"]},
        executor=exec_read_obsidian_note,
        risk_tier="sensitive",
        data_access=["sensitive_data"],
    ))

    return registry
