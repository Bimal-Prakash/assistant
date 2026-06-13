import time
import logging
from typing import Optional
from core.schemas import ActionResponse
from server.dependencies import _CONFIRMATION_LOCK, PENDING_POWER_CONFIRMATIONS, PENDING_SYSTEM_CONTROL_CLARIFICATIONS, PENDING_TERMINAL_CONFIRMATIONS
from server.parser.rules import _is_power_confirmation
from server.parser.system import _extract_volume_brightness_scope, _extract_adjust_direction, _build_system_control_action

logger = logging.getLogger("jarvis.server.api.processor.confirmation")

class ConfirmationMixin:
    def handle_pending_confirmations(self) -> Optional[ActionResponse]:
        now_ts = time.time()
        with _CONFIRMATION_LOCK:
            pending = PENDING_POWER_CONFIRMATIONS.get(self.confirmation_key)
            pending_system = PENDING_SYSTEM_CONTROL_CLARIFICATIONS.get(self.confirmation_key)
            pending_terminal = PENDING_TERMINAL_CONFIRMATIONS.get(self.confirmation_key)
            if pending_system and float(pending_system.get("expires_at", 0.0)) <= now_ts:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS.pop(self.confirmation_key, None)
                pending_system = None

        if pending:
            pending_type = pending["type"]
            pending_target = pending["target"]
            cleaned_lower = self.cleaned.strip().lower()

            if _is_power_confirmation(self.cleaned, pending_type):
                with _CONFIRMATION_LOCK:
                    PENDING_POWER_CONFIRMATIONS.pop(self.confirmation_key, None)
                confirmed_action = ActionResponse(
                    action="power_control",
                    type=pending_type,
                    target=pending_target,
                    response=f"{pending_type.title()} confirmed.",
                )
                pc_result = self._maybe_execute_pc_control(confirmed_action)
                if pc_result is not None:
                    logger.info("PC power control executed after confirmation: %s", pc_result.model_dump())
                    return self._finalize(pc_result)
                return self._finalize(confirmed_action)

            if cleaned_lower in {"cancel", "cancel it", "no", "stop", "abort"}:
                with _CONFIRMATION_LOCK:
                    PENDING_POWER_CONFIRMATIONS.pop(self.confirmation_key, None)
                message = f"Cancelled {pending_type} request."
                return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=pending_target))

            if pending_type not in cleaned_lower:
                with _CONFIRMATION_LOCK:
                    PENDING_POWER_CONFIRMATIONS.pop(self.confirmation_key, None)
                pending = None
            else:
                message = f"Please confirm by saying 'confirm {pending_type}', or say cancel."
                return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=pending_target))

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

        if pending_terminal:
            cleaned_lower = self.cleaned.strip().lower()
            cmd = pending_terminal["command"]
            target = pending_terminal["target"]
            
            if cleaned_lower in {"cancel", "cancel it", "no", "stop", "abort"}:
                with _CONFIRMATION_LOCK:
                    PENDING_TERMINAL_CONFIRMATIONS.pop(self.confirmation_key, None)
                return self._finalize(ActionResponse(action="type_text", text="Cancelled terminal command.", response="Cancelled.", target=target))
                
            if cleaned_lower in {"yes", "confirm", "confirm terminal", "do it", "run it", "execute"}:
                with _CONFIRMATION_LOCK:
                    PENDING_TERMINAL_CONFIRMATIONS.pop(self.confirmation_key, None)
                    
                from tools.dispatch import execute_pc_system_action
                result = execute_pc_system_action({"action": "run_terminal", "command": cmd})
                output = result.get("message", "Executed.")
                
                return self._finalize(ActionResponse(action="type_text", text=f"Executed. Output: {output}", response="Command executed.", target=target))
                
            with _CONFIRMATION_LOCK:
                PENDING_TERMINAL_CONFIRMATIONS.pop(self.confirmation_key, None)

        return None
