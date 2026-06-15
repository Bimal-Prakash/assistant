"""WhatsApp messaging tool."""

import json


def exec_send_whatsapp(phone: str, message: str = "") -> str:
    if not phone:
        return "Error: phone number is required."
    return json.dumps({
        "_client_action": "send_whatsapp",
        "phone": phone,
        "message": message,
    })

def exec_whatsapp_call(contact_name: str = "", call_type: str = "audio", **kwargs) -> str:
    # If the LLM hallucinates 'user_name' instead of 'contact_name', catch it!
    name = contact_name or kwargs.get("user_name", "")
    if not name:
        return "Error: contact_name is required."
    return json.dumps({
        "_client_action": "whatsapp_call",
        "contact_name": name,
        "call_type": call_type,
    })
