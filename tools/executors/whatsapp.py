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

def exec_whatsapp_call(contact_name: str, call_type: str = "audio") -> str:
    if not contact_name:
        return "Error: contact_name is required."
    return json.dumps({
        "_client_action": "whatsapp_call",
        "contact_name": contact_name,
        "call_type": call_type,
    })
