from typing import Dict, Any
import threading

from core.config import JARVIS_MEMORY_DATABASE_URL, JARVIS_MEMORY_HISTORY_LIMIT, JARVIS_MEMORY_FACT_LIMIT
from agent.memory import PostgresMemoryStore
from agent.llm import OllamaCommandModel

MEMORY_STORE = PostgresMemoryStore(
    database_url=JARVIS_MEMORY_DATABASE_URL,
    history_limit=JARVIS_MEMORY_HISTORY_LIMIT,
    fact_limit=JARVIS_MEMORY_FACT_LIMIT,
)
model_client = OllamaCommandModel()

_CONFIRMATION_LOCK = threading.Lock()
PENDING_POWER_CONFIRMATIONS: Dict[str, Dict[str, str]] = {}
PENDING_SYSTEM_CONTROL_CLARIFICATIONS: Dict[str, Dict[str, Any]] = {}
PENDING_TERMINAL_CONFIRMATIONS: Dict[str, Dict[str, str]] = {}
SYSTEM_CONTROL_CLARIFY_TTL_SECONDS = 15.0
