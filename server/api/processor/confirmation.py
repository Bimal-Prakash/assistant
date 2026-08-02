import time
import logging
from typing import Optional
from core.schemas import ActionResponse
from server.dependencies import _CONFIRMATION_LOCK, PENDING_SYSTEM_CONTROL_CLARIFICATIONS
from server.parser.system import _extract_volume_brightness_scope, _extract_adjust_direction, _build_system_control_action

logger = logging.getLogger("jarvis.server.api.processor.confirmation")

class ConfirmationMixin:
    def handle_pending_confirmations(self) -> Optional[ActionResponse]:
        now_ts = time.time()
        with _CONFIRMATION_LOCK:
            pending_system = PENDING_SYSTEM_CONTROL_CLARIFICATIONS.get(self.confirmation_key)
            if pending_system and float(pending_system.get("expires_at", 0.0)) <= now_ts:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(self.confirmation_key, None)
                pending_system = None

        if self.client == "pc" and pending_system:
            cleaned_lower = self.cleaned.strip().lower()
            if cleaned_lower in {"cancel", "cancel it", "no", "stop", "abort"}:
                with _CONFIRMATION_LOCK:
                    PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(self.confirmation_key, None)
                return self._finalize(
                    ActionResponse(
                        action="type_text",
                        text="Cancelled. I did not change volume or brightness.",
                        response="Cancelled. I did not change volume or brightness.",
                        target=self.default_target,
                    )
                )

            follow_scope = _extract_volume_brightness_scope(self.cleaned)
            if follow_scope in {"volume", "brightness"}:
                with _CONFIRMATION_LOCK:
                    pending_payload = PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(self.confirmation_key, {})
                direction = str(pending_payload.get("direction", "up")).strip().lower()
                if direction not in {"up", "down"}:
                    direction = "up"
                target = str(pending_payload.get("target", self.default_target)).strip().lower() or self.default_target
                return self._finalize_with_pc(_build_system_control_action(follow_scope, direction, target))

            if follow_scope is None and _extract_adjust_direction(self.cleaned) is None:
                with _CONFIRMATION_LOCK:
                    PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(self.confirmation_key, None)

        return None
