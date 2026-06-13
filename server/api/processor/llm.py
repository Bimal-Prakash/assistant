import logging
from typing import Optional
from core.schemas import ActionResponse
from server.dependencies import (
    model_client, MEMORY_STORE, _CONFIRMATION_LOCK,
    PENDING_POWER_CONFIRMATIONS, PENDING_TERMINAL_CONFIRMATIONS
)
from server.parser.normalizer import _normalize_action

logger = logging.getLogger("jarvis.server.api.processor.llm")


class LLMMixin:
    def handle_llm_generation(self) -> Optional[ActionResponse]:
        memory_context = MEMORY_STORE.build_context(client=self.client)

        try:
            action_obj = model_client.run_agent_loop(
                self.cleaned,
                contacts={},
                default_target=self.default_target,
                memory_context=memory_context,
                session_id=getattr(self, "session_id", "default"),
            )
        except Exception as exc:
            logger.error("Agent Loop error: %s", exc)
            return self._finalize(
                ActionResponse(
                    action="type_text",
                    text="My agent brain crashed.",
                    response="My agent brain crashed.",
                    target=self.default_target,
                )
            )

        # Check if agent loop requests confirmation registration
        if action_obj and action_obj.get("_needs_confirmation"):
            tool_name = action_obj.get("_pending_tool")
            tool_args = action_obj.get("_pending_args", {})
            if tool_name == "power_control":
                with _CONFIRMATION_LOCK:
                    PENDING_POWER_CONFIRMATIONS[self.confirmation_key] = {
                        "type": tool_args.get("type", "shutdown"),
                        "target": self.default_target,
                    }
            elif tool_name == "run_terminal":
                with _CONFIRMATION_LOCK:
                    PENDING_TERMINAL_CONFIRMATIONS[self.confirmation_key] = {
                        "command": tool_args.get("command", ""),
                        "target": self.default_target,
                    }

        # The agent loop returns a ready-to-use action dict.
        # Normalize it for safety validation, then finalize.
        normalized = _normalize_action(action_obj, default_target=self.default_target)
        logger.info("Normalized action: %s", normalized.model_dump())

        # Execute PC controls server-side if applicable
        return self._finalize_with_pc(normalized)
