import logging
from typing import Optional
from core.schemas import ActionResponse
from tools.dispatch import execute_pc_system_action
from server.dependencies import MEMORY_STORE

logger = logging.getLogger("jarvis.server.api.processor.execution")

class ExecutionMixin:
    def _maybe_execute_pc_control(self, action: ActionResponse) -> Optional[ActionResponse]:
        if action.target != "pc":
            return None
        pc_supported = {"volume_control", "brightness_control", "power_control", "mic_control", "media_control", "network_control"}
        if action.action not in pc_supported:
            return None
        result = execute_pc_system_action(action.model_dump())
        message = result.get("message", "PC action processed")
        return ActionResponse(action="type_text", text=message, response=message, target="android")

    def _remember_and_return(self, action: ActionResponse) -> ActionResponse:
        try:
            MEMORY_STORE.remember_interaction(client=self.client, user_text=self.cleaned, action=action.model_dump())
        except Exception as exc:
            logger.warning("Memory write failed: %s", exc)
        return action

    def _finalize(self, action: ActionResponse) -> ActionResponse:
        return self._remember_and_return(action=action)

    def _finalize_with_pc(self, action: ActionResponse) -> ActionResponse:
        pc_result = self._maybe_execute_pc_control(action)
        if pc_result is not None:
            logger.info("PC control executed: %s", pc_result.model_dump())
            return self._finalize(pc_result)
        return self._finalize(action)
