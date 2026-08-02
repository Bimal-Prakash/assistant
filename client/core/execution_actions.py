import webbrowser
from urllib.parse import quote_plus
from typing import Any, Dict

from client.config import *

class ActionExecutionMixin:
                def _sanitize_text(self, text: str) -> str:
                    if not text:
                        return text
                    # Strip markdown formatting like quotes, asterisks, bold, etc.
                    text = text.replace('"', '').replace('*', '')
                    return text.strip()

                def execute_pc_action(self, action: Dict[str, Any]) -> None:
                    action_name = str(action.get("action", "")).lower()

                    if action_name == "open_website":
                        url = str(action.get("url", "")).strip()
                        if url:
                            webbrowser.open(url)
                            return
                        self.speak("Website URL missing")
                        return

                    if action_name == "open_app":
                        app_name = str(action.get("app", "")).strip()
                        raw_text = action.get("text")
                        post_text = raw_text.strip() if isinstance(raw_text, str) else None
                        if post_text and post_text.lower() in {"none", "null", "undefined", "n/a", "na"}:
                            post_text = None
                        if app_name:
                            open_result = self._open_app(app_name, post_text=post_text)
                            if open_result.startswith("Opening "):
                                return
                            else:
                                self.speak(open_result)
                            return
                        self.speak("App name missing")
                        return

                    if action_name == "close_app":
                        app_name = str(action.get("app", "")).strip()
                        if app_name:
                            close_result = self._close_app(app_name)
                            if close_result.startswith("Closing "):
                                return
                            else:
                                self.speak(close_result)
                            return
                        self.speak("App name missing")
                        return

                    if action_name == "minimize_app":
                        app_name = str(action.get("app", "")).strip()
                        if app_name:
                            min_result = getattr(self, "_minimize_app", lambda x: "Minimize not supported")(app_name)
                            if min_result.startswith("Minimizing "):
                                return
                            else:
                                self.speak(min_result)
                            return
                        self.speak("App name missing")
                        return
                        
                    if action_name == "confirm_action":
                        tool_name = action.get("tool_name", "this action")
                        msg = f"I need your permission to use {tool_name}. Please confirm if I should proceed."
                        self.speak(msg)
                        return

                    if action_name == "send_whatsapp":
                        phone = str(action.get("phone", "")).strip()
                        message = self._sanitize_text(str(action.get("message", "")).strip())
                        if phone:
                            query = f"https://wa.me/{phone}"
                            if message:
                                query = f"{query}?text={quote_plus(message)}"
                            webbrowser.open(query)
                            return
                        self.speak("WhatsApp phone number is missing.")
                        return

                    if action_name == "type_string":
                        import pyautogui
                        text_to_type = str(action.get("text", ""))
                        if text_to_type:
                            # Use a small interval to make typing look natural but fast
                            pyautogui.write(text_to_type, interval=0.01)
                            return "Typed text successfully."
                        self.speak("No text to type.")
                        return

                    if action_name == "spotify_like":
                        result = self._spotify_like_current_song()
                        msg = action.get("response") or result
                        if msg and not self._is_quiet_success_message(msg):
                            self.speak(msg)
                        if result and result != action.get("response"):
                            print(result)
                        return

                    if action_name == "get_system_info":
                        from tools.executors.system_info import exec_get_system_info
                        query = str(action.get("query", "time"))
                        result = exec_get_system_info(query)
                        if result and not self._is_quiet_success_message(result):
                            self.speak(result)
                        return result

                    agentic_methods = {
                        "maximize_app": "_maximize_app",
                        "restore_app": "_restore_app",
                        "focus_app": "_focus_app",
                        "snap_window": "_snap_window",
                        "hide_all_windows": "_hide_all_windows",
                        "read_clipboard": "_read_clipboard",
                        "write_clipboard": "_write_clipboard",
                        "press_shortcut": "_press_shortcut",
                        "check_performance": "_check_performance",
                        "lock_pc": "_lock_pc",
                        "empty_recycle_bin": "_empty_recycle_bin",
                        "take_screenshot": "_take_screenshot",
                        "show_notification": "_show_notification",
                        "set_timer": "_set_timer",
                        "open_folder": "_open_folder",
                        "open_file": "_open_file",
                        "search_files": "_search_files",
                        "whatsapp_call": "_whatsapp_call",
                        "telegram_call": "_telegram_call"
                    }
                    if action_name in agentic_methods:
                        method_name = agentic_methods[action_name]
                        method = getattr(self, method_name, lambda *args, **kwargs: "Feature not available")

                        kwargs = {}
                        if action_name in ["maximize_app", "restore_app", "focus_app"]:
                            kwargs["app_name"] = str(action.get("app", "")).strip()
                        elif action_name == "snap_window":
                            kwargs["app_name"] = str(action.get("app", "")).strip()
                            kwargs["direction"] = str(action.get("direction", "")).strip()
                        elif action_name == "write_clipboard":
                            kwargs["text"] = self._sanitize_text(str(action.get("text", "")))
                        elif action_name == "press_shortcut":
                            kwargs["shortcut"] = str(action.get("shortcut", "")).strip()
                        elif action_name == "show_notification":
                            kwargs["title"] = self._sanitize_text(str(action.get("title", "")))
                            kwargs["message"] = self._sanitize_text(str(action.get("message", "")))
                        elif action_name == "set_timer":
                            kwargs["seconds"] = int(action.get("seconds", 0))
                            kwargs["label"] = self._sanitize_text(str(action.get("label", "")))
                        elif action_name == "open_folder":
                            kwargs["folder_path"] = str(action.get("folder_path", "")).strip()
                        elif action_name == "open_file":
                            kwargs["file_path"] = str(action.get("file_path", "")).strip()
                        elif action_name == "search_files":
                            kwargs["query"] = self._sanitize_text(str(action.get("query", "")))
                        elif action_name in ["whatsapp_call", "telegram_call"]:
                            kwargs["contact_name"] = self._sanitize_text(str(action.get("contact_name", "")))
                            kwargs["call_type"] = str(action.get("call_type", "audio")).strip()

                        result = method(**kwargs)
                        if result and not self._is_quiet_success_message(result):
                            self.speak(result)
                        return result

                    if action_name == "get_current_media_info":
                        try:
                            from tools.system.media import get_current_media_info
                            info = get_current_media_info()
                            self.speak(info)
                        except Exception as e:
                            self.speak(f"Could not get media info: {e}")
                        return

                    if action_name == "type_text":
                        message = str(action.get("response") or action.get("text") or "Okay")
                        message = self._sanitize_text(message)
                        if not self._is_quiet_success_message(message):
                            self.speak(message)
                        return

                    # PC control actions are executed on backend and returned as type_text.
                    message = str(action.get("response") or "Done")
                    if not self._is_quiet_success_message(message):
                        self.speak(message)

