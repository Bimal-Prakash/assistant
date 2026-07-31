"""Telegram messaging tool."""

import json

def exec_telegram_call(contact_name: str = "", call_type: str = "audio", **kwargs) -> str:
    name = contact_name or kwargs.get("user_name", "")
    if not name and call_type != "end":
        return "Error: contact_name is required for starting a call."
    return json.dumps({
        "_client_action": "telegram_call",
        "contact_name": name,
        "call_type": call_type,
    })
