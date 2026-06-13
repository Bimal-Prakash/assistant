import re
from typing import Dict, Any
from core.config import ALLOWED_ACTIONS
from core.schemas import ActionResponse
from .system import _parse_percentage_level, _clean_response_text, _clean_slot_text
from .contacts import _normalize_phone, _resolve_contact_phone

def _extract_target(action_obj: Dict[str, Any], default: str = "android") -> str:
    target = str(action_obj.get("target", default)).strip().lower()
    return target if target in {"android", "pc"} else default

def _normalize_action(action_obj: Dict[str, Any], default_target: str = "android") -> ActionResponse:
    action = str(action_obj.get("action", "")).strip().lower()
    response_text = _clean_response_text(action_obj.get("response"))
    if action not in ALLOWED_ACTIONS:
        return ActionResponse(
            action="type_text",
            text="I could not understand that command.",
            response="I could not understand that command.",
            target="android",
        )

    target = _extract_target(action_obj, default=default_target)

    if action == "open_app":
        app_name = str(action_obj.get("app", "")).strip().lower()
        post_text = _clean_slot_text(action_obj.get("text"))
        if not app_name:
            return ActionResponse(action="type_text", text="Please specify which app to open.", target=target)
        return ActionResponse(
            action="open_app",
            app=app_name,
            text=post_text,
            response=response_text or f"Opening {app_name}.",
            target=target,
        )

    if action == "close_app":
        app_name = str(action_obj.get("app", "")).strip().lower()
        if not app_name:
            return ActionResponse(action="type_text", text="Please specify which app to close.", target=target)
        return ActionResponse(
            action="close_app",
            app=app_name,
            response=response_text or f"Closing {app_name}.",
            target=target,
        )

    if action == "open_website":
        url = str(action_obj.get("url", "")).strip()
        if not url:
            return ActionResponse(action="type_text", text="Please specify the website.", target=target)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        return ActionResponse(
            action="open_website",
            url=url,
            response=response_text or "Opening website.",
            target=target,
        )

    if action == "call_contact":
        contact = str(action_obj.get("contact", "")).strip()
        phone = str(action_obj.get("phone", "")).strip()
        if not contact and not phone:
            return ActionResponse(action="type_text", text="Please tell me who to call.", target=target)

        normalized_phone = _normalize_phone(phone) if phone else None
        if not normalized_phone and contact:
            normalized_phone = _resolve_contact_phone(contact)

        if not normalized_phone:
            return ActionResponse(
                action="type_text",
                text=f"I could not find contact {contact or 'that person'}.",
                response=f"I could not find contact {contact or 'that person'}.",
                target=target,
            )

        return ActionResponse(
            action="call_contact",
            contact=contact or "Unknown",
            phone=normalized_phone,
            response=response_text or f"Calling {contact or normalized_phone}.",
            target=target,
        )

    if action == "send_whatsapp":
        contact = str(action_obj.get("contact", "")).strip()
        message = str(action_obj.get("message", action_obj.get("text", ""))).strip()
        phone = str(action_obj.get("phone", "")).strip()

        if not contact and not phone and not message:
            return ActionResponse(
                action="open_app",
                app="whatsapp",
                response=action_obj.get("response") or "Opening WhatsApp.",
                target=target,
            )

        normalized_phone = _normalize_phone(phone) if phone else None
        if not normalized_phone and contact:
            normalized_phone = _resolve_contact_phone(contact)

        if not normalized_phone:
            return ActionResponse(
                action="type_text",
                text=f"I could not find WhatsApp contact {contact or 'that person'}.",
                response=f"I could not find WhatsApp contact {contact or 'that person'}.",
                target=target,
            )

        return ActionResponse(
            action="send_whatsapp",
            contact=contact or "Unknown",
            phone=normalized_phone,
            message=message,
            response=response_text or f"Opening WhatsApp for {contact or normalized_phone}.",
            target=target,
        )

    if action == "volume_control":
        raw_level = str(action_obj.get("level", "")).strip().lower()
        percentage = _parse_percentage_level(raw_level)
        if raw_level not in {"up", "down", "mute", "max"} and percentage is None:
            return ActionResponse(
                action="type_text",
                text="Use volume up, down, mute, max, or a percentage like 50%.",
                target=target,
            )
        level = str(percentage) if percentage is not None else raw_level
        return ActionResponse(
            action="volume_control",
            level=level,
            target=target,
            response=response_text or f"Adjusting volume {level}.",
        )

    if action == "brightness_control":
        raw_level = str(action_obj.get("level", "")).strip().lower()
        percentage = _parse_percentage_level(raw_level)
        if raw_level not in {"up", "down", "max", "min"} and percentage is None:
            return ActionResponse(
                action="type_text",
                text="Use brightness up, down, max, min, or a percentage like 50%.",
                target=target,
            )
        level = str(percentage) if percentage is not None else raw_level
        return ActionResponse(
            action="brightness_control",
            level=level,
            target=target,
            response=response_text or f"Adjusting brightness {level}.",
        )

    if action == "power_control":
        power_type = str(action_obj.get("type", "")).strip().lower()
        if power_type not in {"shutdown", "restart", "sleep"}:
            return ActionResponse(action="type_text", text="Use shutdown, restart or sleep.", target=target)
        return ActionResponse(
            action="power_control",
            type=power_type,
            target=target,
            response=response_text or f"Power action {power_type} requested.",
        )

    if action == "mic_control":
        state = str(action_obj.get("state", "")).strip().lower()
        if state not in {"mute", "unmute"}:
            return ActionResponse(action="type_text", text="Use mic mute or unmute.", target=target)
        return ActionResponse(
            action="mic_control",
            state=state,
            target=target,
            response=response_text or f"Microphone {state}.",
        )

    if action == "media_control":
        media_state = str(action_obj.get("state", action_obj.get("type", ""))).strip().lower()
        if media_state in {"play", "pause", "play_pause", "toggle"}:
            normalized_state = "play_pause"
        elif media_state in {"next", "next_track"}:
            normalized_state = "next"
        elif media_state in {"previous", "prev", "previous_track"}:
            normalized_state = "previous"
        else:
            return ActionResponse(action="type_text", text="Use play, pause, next, or previous.", target=target)
        return ActionResponse(
            action="media_control",
            state=normalized_state,
            target=target,
            response=response_text or f"Media control {normalized_state}.",
        )

    if action == "network_control":
        network_type = str(action_obj.get("type", "")).strip().lower()
        state = str(action_obj.get("state", "")).strip().lower()
        if network_type not in {"wifi", "bluetooth"}:
            return ActionResponse(action="type_text", text="Use wifi or bluetooth.", target=target)
        if state not in {"on", "off", "open"}:
            return ActionResponse(action="type_text", text="Use on, off, or open.", target=target)
        return ActionResponse(
            action="network_control",
            type=network_type,
            state=state,
            target=target,
            response=response_text or f"Network control {network_type} {state}.",
        )

    if action == "system_control":
        control_type = str(action_obj.get("type", "")).strip().lower()
        level = str(action_obj.get("level", "")).strip().lower()
        state = str(action_obj.get("state", "")).strip().lower()

        if control_type == "volume":
            return _normalize_action(
                {"action": "volume_control", "level": level, "target": target, "response": response_text},
                default_target=target,
            )
        if control_type == "brightness":
            return _normalize_action(
                {"action": "brightness_control", "level": level, "target": target, "response": response_text},
                default_target=target,
            )
        if control_type == "mic":
            return _normalize_action(
                {"action": "mic_control", "state": state, "target": target, "response": response_text},
                default_target=target,
            )

        return ActionResponse(
            action="system_control",
            type=control_type,
            level=level or None,
            state=state or None,
            target=target,
            response=response_text or "System control command received.",
        )

    agentic_actions = {
        "minimize_app", "maximize_app", "restore_app", "focus_app", "hide_all_windows",
        "snap_window", "read_clipboard", "write_clipboard", "press_shortcut",
        "check_performance", "lock_pc", "empty_recycle_bin", "take_screenshot",
        "show_notification", "set_timer", "open_folder", "search_files", "whatsapp_call",
        "spotify_like"
    }

    if action in agentic_actions:
        return ActionResponse(
            action=action,
            target=target,
            response=response_text or f"Executing {action}.",
            app=action_obj.get("app"),
            direction=action_obj.get("direction"),
            text=action_obj.get("text"),
            shortcut=action_obj.get("shortcut"),
            title=action_obj.get("title"),
            message=action_obj.get("message"),
            seconds=action_obj.get("seconds"),
            label=action_obj.get("label"),
            folder_path=action_obj.get("folder_path"),
            query=action_obj.get("query"),
            contact_name=action_obj.get("contact_name"),
            call_type=action_obj.get("call_type"),
        )

    text = str(action_obj.get("text", "")).strip() or "I am not sure how to do that yet."
    return ActionResponse(
        action="type_text",
        text=text,
        response=response_text or text,
        target=target,
    )
