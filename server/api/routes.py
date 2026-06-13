import re
import logging
from typing import Dict, Any
from fastapi import APIRouter
from core.config import HOST, PORT, JARVIS_MEMORY_HISTORY_LIMIT, JARVIS_MEMORY_FACT_LIMIT
from core.schemas import CommandRequest, ActionResponse
from server.dependencies import MEMORY_STORE, model_client
from server.api.processor import CommandProcessor

logger = logging.getLogger("jarvis.server.api")

router = APIRouter()


def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "model": model_client.model,
        "host": HOST,
        "port": str(PORT),
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
            "history_limit": JARVIS_MEMORY_HISTORY_LIMIT,
            "fact_limit": JARVIS_MEMORY_FACT_LIMIT,
        },
        "server": {"host": HOST, "port": PORT},
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
