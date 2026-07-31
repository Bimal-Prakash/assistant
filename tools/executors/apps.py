"""Open and close applications on the PC."""

import json


def exec_open_app(app_name: str, text: str = "") -> str:
    if not app_name:
        return "Error: app_name is required."
    return json.dumps({
        "_client_action": "open_app",
        "app": app_name.strip().lower(),
        "text": text.strip() if text else None,
    })


def exec_close_app(app: str) -> str:
    if not app:
        return "Error: app name is required."
    return json.dumps({
        "_client_action": "close_app",
        "app": app.strip().lower(),
    })


def exec_minimize_app(app: str) -> str:
    if not app:
        return "Error: app name is required."
    return json.dumps({
        "_client_action": "press_shortcut",
        "shortcut": "win+d",
    })

def exec_type_string(text: str) -> str:
    if not text:
        return "Error: text is required."
    return json.dumps({
        "_client_action": "type_string",
        "text": text,
    })
