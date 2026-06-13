"""Memory query handler — now handled by the agent via tools.

This mixin is kept as a no-op for backward compatibility with the
CommandProcessor class hierarchy.
"""

import logging
from typing import Optional
from core.schemas import ActionResponse

logger = logging.getLogger("jarvis.server.api.processor.memory")


class MemoryQueriesMixin:
    def handle_memory_queries(self) -> Optional[ActionResponse]:
        # Agent handles all memory queries via recall_fact / remember_fact tools.
        return None
