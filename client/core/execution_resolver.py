"""Command resolver — sends everything to the backend agent.

No local interception. The agent handles all reasoning.
"""

import logging
import time
from typing import Any, Dict

from client.config import SPOKEN_FILLER_ENABLED

logger = logging.getLogger("jarvis.client")


class ResolverMixin:
    def _resolve_action_for_command(self, command: str) -> Dict[str, Any]:
        now = time.time()
        if self.backend_reachable is None or (now - self._last_backend_check_ts) > 15:
            self._check_backend_status(retries=1, delay_seconds=0.2)

        if self.backend_reachable is False:
            return {
                "action": "type_text",
                "response": "Backend is offline. Please check if the server is running.",
                "text": "Backend is offline. Please check if the server is running.",
            }

        try:
            self._update_hud(intent="thinking", action="processing command")
            self._play_chime("thinking")
            if SPOKEN_FILLER_ENABLED:
                self.speak("Sure, let me check that.")
            action = self.send_command(command)
            self.backend_reachable = True
            return action
        except Exception as exc:
            logger.exception("Backend send_command failed: %s", exc)
            self.backend_reachable = False
            return {
                "action": "type_text",
                "response": "Backend connection failed. Please try again.",
                "text": "Backend connection failed. Please try again.",
            }
