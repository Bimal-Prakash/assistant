from .execution import ExecutionMixin
from .confirmation import ConfirmationMixin
from .memory import MemoryQueriesMixin
from .llm import LLMMixin
from .core import CoreProcessorMixin
from core.config import WAKE_WORDS


def _strip_wake_word(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    for wake_word in WAKE_WORDS:
        if lowered.startswith(wake_word):
            remainder = stripped[len(wake_word):].lstrip(" ,:-")
            return remainder.strip()
    return ""


def _confirmation_key(client: str, target: str) -> str:
    client_key = (client or "unknown").strip().lower() or "unknown"
    target_key = (target or "android").strip().lower() or "android"
    return f"{client_key}:{target_key}"


class CommandProcessor(ExecutionMixin, ConfirmationMixin, MemoryQueriesMixin, LLMMixin, CoreProcessorMixin):
    def __init__(self, spoken_text: str, client: str, session_id: str = "default"):
        self.spoken_text = spoken_text
        self.client = client
        self.session_id = session_id
        self.default_target = "pc" if client == "pc" else "android"
        self.confirmation_key = _confirmation_key(self.client, self.default_target)

        if self.client == "pc":
            self.cleaned = self.spoken_text
        else:
            self.cleaned = _strip_wake_word(self.spoken_text)
