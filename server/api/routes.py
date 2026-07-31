import re
import logging
from typing import Dict, Any
# pyrefly: ignore [missing-import]
from fastapi import APIRouter
from core.schemas import CommandRequest, ActionResponse
from server.dependencies import MEMORY_STORE, model_client
from server.api.processor import CommandProcessor
from server.proactive_daemon import PROACTIVE_QUEUE
import core.config as config

logger = logging.getLogger("jarvis.server.api")

router = APIRouter()

def get_notifications() -> Dict[str, Any]:
    try:
        action = PROACTIVE_QUEUE.get_nowait()
        return action.model_dump() if hasattr(action, "model_dump") else dict(action)
    except Exception:
        return {"action": "none"}

def set_proactive_config(payload: Dict[str, bool]) -> Dict[str, Any]:
    enabled = payload.get("enabled", False)
    config.ENABLE_PROACTIVE_BACKGROUND_TASKS = enabled
    return {"status": "ok", "proactive_enabled": config.ENABLE_PROACTIVE_BACKGROUND_TASKS}


def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "model": model_client.model,
        "host": config.HOST,
        "port": str(config.PORT),
    }

def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "api": {"up": True},
        "model": {
            "name": model_client.model,
            "api_url": model_client.api_url,
        },
        "memory": {
            "backend": MEMORY_STORE.backend,
            "configured": MEMORY_STORE.configured,
            "enabled": MEMORY_STORE.enabled,
            "last_error": MEMORY_STORE.last_error,
            "history_limit": config.JARVIS_MEMORY_HISTORY_LIMIT,
            "fact_limit": config.JARVIS_MEMORY_FACT_LIMIT,
        },
        "server": {"host": config.HOST, "port": config.PORT},
        "proactive_enabled": config.ENABLE_PROACTIVE_BACKGROUND_TASKS
    }

def command(request: CommandRequest) -> ActionResponse:
    spoken_text = request.text.strip()
    spoken_text = re.sub(r"^(?:hey\s+)?jarvis\s+", "", spoken_text, flags=re.IGNORECASE).strip()
    client = (request.client or "").strip().lower() or "unknown"
    session_id = (request.session_id or "").strip() or "default"

    logger.info("Received command: %s (session=%s)", spoken_text, session_id)

    if not spoken_text:
        return ActionResponse(action="type_text", text="I did not hear anything.", target="android")

    processor = CommandProcessor(spoken_text=spoken_text, client=client, session_id=session_id)

    if not processor.cleaned:
        return processor._finalize(
            ActionResponse(action="type_text", text="Please say hey jarvis followed by a command.", target="android")
        )

    return processor.process()


router.add_api_route("/health", health, methods=["GET"])
router.add_api_route("/status", status, methods=["GET"])
router.add_api_route("/command", command, methods=["POST"])
router.add_api_route("/notifications", get_notifications, methods=["GET"])
router.add_api_route("/config/proactive", set_proactive_config, methods=["POST"])
