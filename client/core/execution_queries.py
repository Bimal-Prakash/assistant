"""Local query handler — now handled by the agent.

All queries (time, date, battery, open app, etc.) now go through the
agent's ReAct loop and tool registry. This mixin is kept as a no-op
for backward compatibility with the LaptopJarvisClient class hierarchy.
"""

from typing import Any, Dict, Optional


class LocalQueryMixin:
    def _handle_system_query(self, text: str) -> Optional[Dict[str, Any]]:
        # Agent handles everything now. No local interception.
        return None
