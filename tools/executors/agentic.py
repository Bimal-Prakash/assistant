import json

def exec_maximize_app(app: str) -> str:
    return json.dumps({"_client_action": "maximize_app", "app": app.strip().lower()})

def exec_restore_app(app: str) -> str:
    return json.dumps({"_client_action": "restore_app", "app": app.strip().lower()})

def exec_focus_app(app: str) -> str:
    return json.dumps({"_client_action": "focus_app", "app": app.strip().lower()})

def exec_hide_all_windows() -> str:
    return json.dumps({"_client_action": "hide_all_windows"})

def exec_snap_window(app: str, direction: str) -> str:
    return json.dumps({"_client_action": "snap_window", "app": app.strip().lower(), "direction": direction.strip().lower()})

def exec_read_clipboard() -> str:
    return json.dumps({"_client_action": "read_clipboard"})

def exec_write_clipboard(text: str) -> str:
    return json.dumps({"_client_action": "write_clipboard", "text": text})

def exec_press_shortcut(shortcut: str) -> str:
    return json.dumps({"_client_action": "press_shortcut", "shortcut": shortcut.strip()})

def exec_check_performance() -> str:
    return json.dumps({"_client_action": "check_performance"})

def exec_lock_pc() -> str:
    return json.dumps({"_client_action": "lock_pc"})

def exec_empty_recycle_bin() -> str:
    return json.dumps({"_client_action": "empty_recycle_bin"})

def exec_take_screenshot() -> str:
    return json.dumps({"_client_action": "take_screenshot"})

def exec_show_notification(title: str, message: str) -> str:
    return json.dumps({"_client_action": "show_notification", "title": title, "message": message})

def exec_set_timer(seconds: int, label: str = "") -> str:
    return json.dumps({"_client_action": "set_timer", "seconds": seconds, "label": label})

def exec_open_folder(folder_path: str) -> str:
    return json.dumps({"_client_action": "open_folder", "folder_path": folder_path.strip()})

def exec_search_files(query: str) -> str:
    return json.dumps({"_client_action": "search_files", "query": query.strip()})

def exec_whatsapp_call(contact_name: str, call_type: str = "audio") -> str:
    contact_name = (contact_name or "").strip()
    call_type = (call_type or "audio").strip().lower()
    return json.dumps({"_client_action": "whatsapp_call", "contact_name": contact_name, "call_type": call_type})
