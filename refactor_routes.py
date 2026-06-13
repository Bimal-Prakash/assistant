import os
import shutil

base_dir = r"C:\Bimal\Project\assistant"
api_dir = os.path.join(base_dir, "server", "api")
processor_dir = os.path.join(api_dir, "processor")

os.makedirs(processor_dir, exist_ok=True)

# 1. execution.py
execution_code = """import logging
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
"""

# 2. confirmation.py
confirmation_code = """import time
import logging
from typing import Optional
from core.schemas import ActionResponse
from server.dependencies import _CONFIRMATION_LOCK, PENDING_POWER_CONFIRMATIONS, PENDING_SYSTEM_CONTROL_CLARIFICATIONS
from server.parser.rules import _is_power_confirmation
from server.parser.system import _extract_volume_brightness_scope, _extract_adjust_direction, _build_system_control_action

logger = logging.getLogger("jarvis.server.api.processor.confirmation")

class ConfirmationMixin:
    def handle_pending_confirmations(self) -> Optional[ActionResponse]:
        now_ts = time.time()
        with _CONFIRMATION_LOCK:
            pending = PENDING_POWER_CONFIRMATIONS.get(self.confirmation_key)
            pending_system = PENDING_SYSTEM_CONTROL_CLARIFICATIONS.get(self.confirmation_key)
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

        return None
"""

# 3. local.py
local_code = """import time
import logging
from typing import Optional
from core.schemas import ActionResponse
from server.parser.rules import _rule_based_action, _is_power_confirmation
from server.parser.system import _extract_volume_brightness_scope, _extract_adjust_direction, _build_system_control_action, _should_prompt_for_volume_brightness
from server.dependencies import _CONFIRMATION_LOCK, PENDING_POWER_CONFIRMATIONS, PENDING_SYSTEM_CONTROL_CLARIFICATIONS, SYSTEM_CONTROL_CLARIFY_TTL_SECONDS

logger = logging.getLogger("jarvis.server.api.processor.local")

class LocalFallbackMixin:
    def handle_local_parsing(self) -> Optional[ActionResponse]:
        if self.client != "pc":
            return None

        exact_level_action = _rule_based_action(self.cleaned, default_target=self.default_target)
        if (
            exact_level_action is not None
            and exact_level_action.action in {"volume_control", "brightness_control"}
            and str(exact_level_action.level or "").isdigit()
        ):
            return self._finalize_with_pc(exact_level_action)

        ambiguous_direction = _extract_adjust_direction(self.cleaned)
        scope = _extract_volume_brightness_scope(self.cleaned)

        if ambiguous_direction and scope in {"volume", "brightness"}:
            return self._finalize_with_pc(_build_system_control_action(scope, ambiguous_direction, self.default_target))

        if ambiguous_direction and scope == "both":
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS[self.confirmation_key] = {
                    "direction": ambiguous_direction,
                    "target": self.default_target,
                    "expires_at": time.time() + SYSTEM_CONTROL_CLARIFY_TTL_SECONDS,
                }
            return self._finalize(
                ActionResponse(
                    action="type_text",
                    text="Do you want to change volume or brightness?",
                    response="Do you want to change volume or brightness?",
                    target=self.default_target,
                )
            )

        if ambiguous_direction and scope is None and _should_prompt_for_volume_brightness(self.cleaned):
            with _CONFIRMATION_LOCK:
                PENDING_SYSTEM_CONTROL_CLARIFICATIONS[self.confirmation_key] = {
                    "direction": ambiguous_direction,
                    "target": self.default_target,
                    "expires_at": time.time() + SYSTEM_CONTROL_CLARIFY_TTL_SECONDS,
                }
            return self._finalize(
                ActionResponse(
                    action="type_text",
                    text="Do you mean volume or brightness?",
                    response="Do you mean volume or brightness?",
                    target=self.default_target,
                )
            )

        local_action = _rule_based_action(self.cleaned, default_target=self.default_target)
        if local_action is not None:
            with _CONFIRMATION_LOCK:
                pending_local = PENDING_POWER_CONFIRMATIONS.get(self.confirmation_key)
                if pending_local:
                    cleaned_lower = self.cleaned.strip().lower()
                    pending_type_local = pending_local.get("type", "")
                    if (
                        cleaned_lower not in {"cancel", "no", "stop", "abort"}
                        and not _is_power_confirmation(self.cleaned, pending_type_local)
                        and pending_type_local not in cleaned_lower
                    ):
                        PENDING_POWER_CONFIRMATIONS.pop(self.confirmation_key, None)

            if local_action.action == "power_control" and local_action.type in {"shutdown", "restart"}:
                with _CONFIRMATION_LOCK:
                    PENDING_POWER_CONFIRMATIONS[self.confirmation_key] = {
                        "type": local_action.type,
                        "target": local_action.target or self.default_target,
                    }
                message = f"Please confirm by saying 'confirm {local_action.type}', or say cancel."
                return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=local_action.target))

            return self._finalize_with_pc(local_action)

        return None
"""

# 4. memory.py
memory_code = """import re
import logging
from typing import Optional
from core.schemas import ActionResponse
from server.dependencies import MEMORY_STORE

logger = logging.getLogger("jarvis.server.api.processor.memory")

class MemoryQueriesMixin:
    def handle_memory_queries(self) -> Optional[ActionResponse]:
        cleaned_lower = re.sub(r"\s+", " ", self.cleaned.strip().lower())
        
        if cleaned_lower in {"open", "start", "launch", "run"}:
            message = "Which app should I open?"
            return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=self.default_target))

        if (
            "my name" in cleaned_lower
            and (
                "what" in cleaned_lower
                or "know" in cleaned_lower
                or cleaned_lower in {"my name", "no my name"}
            )
        ):
            name = MEMORY_STORE.get_fact(client=self.client, fact_key="name")
            if name:
                msg = f"Your name is {name}."
            else:
                msg = "I do not know your name yet. So tell me your name."
            return self._finalize(ActionResponse(action="type_text", text=msg, response=msg, target=self.default_target))

        if (
            "what did you open before" in cleaned_lower
            or "what did you open" in cleaned_lower
            or "which app did you open before" in cleaned_lower
            or "what app did you open before" in cleaned_lower
        ):
            last_app = MEMORY_STORE.get_last_opened_app(client=self.client)
            if last_app:
                msg = f"Last app I opened was {last_app}."
            else:
                msg = "I have no open-app history yet."
            return self._finalize(ActionResponse(action="type_text", text=msg, response=msg, target=self.default_target))

        if (
            "what did i ask last time" in cleaned_lower
            or "what did i ask you last time" in cleaned_lower
            or "what did i ask u last time" in cleaned_lower
            or "what did i tell you last time" in cleaned_lower
            or "what did i tell u last time" in cleaned_lower
            or "what did i ask you to do" in cleaned_lower
            or "what did i ask u to do" in cleaned_lower
            or "what was my last command" in cleaned_lower
            or cleaned_lower == "last command"
        ):
            last_text = MEMORY_STORE.get_last_user_text(client=self.client)
            if last_text:
                msg = f"Your last command was: {last_text}."
            else:
                msg = "I do not have a previous command saved yet."
            return self._finalize(ActionResponse(action="type_text", text=msg, response=msg, target=self.default_target))

        return None
"""

# 5. llm.py
llm_code = """import time
import logging
from typing import Optional
from core.schemas import ActionResponse
from server.dependencies import model_client, MEMORY_STORE, _CONFIRMATION_LOCK, PENDING_POWER_CONFIRMATIONS, PENDING_SYSTEM_CONTROL_CLARIFICATIONS, SYSTEM_CONTROL_CLARIFY_TTL_SECONDS
from server.parser.contacts import CONTACTS
from server.parser.rules import _is_conversational_query, _rule_based_action
from server.parser.system import _extract_volume_brightness_scope, _should_prompt_for_volume_brightness, _extract_adjust_direction
from server.parser.normalizer import _normalize_action
from agent.llm import ModelError

logger = logging.getLogger("jarvis.server.api.processor.llm")

class LLMMixin:
    def handle_llm_generation(self) -> Optional[ActionResponse]:
        cleaned_lower = self.cleaned.strip().lower()
        memory_context = MEMORY_STORE.build_context(client=self.client)

        if _is_conversational_query(cleaned_lower):
            try:
                response_text = model_client.generate_text(self.cleaned, memory_context=memory_context)
            except ModelError as exc:
                logger.error("Chat model error: %s", exc)
                response_text = "I cannot reach the local AI model right now."
            return self._finalize(
                ActionResponse(
                    action="type_text",
                    text=response_text,
                    response=response_text,
                    target=self.default_target,
                )
            )

        try:
            action_obj = model_client.generate_action(
                self.cleaned,
                CONTACTS,
                default_target=self.default_target,
                memory_context=memory_context,
            )
        except ModelError as exc:
            logger.error("Model error: %s", exc)
            fallback = _rule_based_action(self.cleaned, default_target=self.default_target)
            if fallback is not None:
                logger.info("Using rule-based fallback action: %s", fallback.model_dump())
                return self._finalize_with_pc(fallback)
            return self._finalize(
                ActionResponse(
                    action="type_text",
                    text="I cannot reach the local AI model right now.",
                    response="I cannot reach the local AI model right now.",
                    target=self.default_target,
                )
            )

        normalized = _normalize_action(action_obj, default_target=self.default_target)

        if self.client == "pc" and normalized.action in {"volume_control", "brightness_control"}:
            scope = _extract_volume_brightness_scope(self.cleaned)
            if scope is None and _should_prompt_for_volume_brightness(self.cleaned):
                model_direction = str(normalized.level or "").strip().lower()
                if model_direction not in {"up", "down"}:
                    model_direction = _extract_adjust_direction(self.cleaned) or "up"
                with _CONFIRMATION_LOCK:
                    PENDING_SYSTEM_CONTROL_CLARIFICATIONS[self.confirmation_key] = {
                        "direction": model_direction,
                        "target": self.default_target,
                        "expires_at": time.time() + SYSTEM_CONTROL_CLARIFY_TTL_SECONDS,
                    }
                return self._finalize(
                    ActionResponse(
                        action="type_text",
                        text="Do you mean volume or brightness?",
                        response="Do you mean volume or brightness?",
                        target=self.default_target,
                    )
                )

        if normalized.action == "type_text":
            echoed = (normalized.text or "").strip().lower()
            if echoed == cleaned_lower or cleaned_lower in {"what", "huh", "ok", "hmm"}:
                message = "Please tell me a specific command, for example: open chrome, play music, or turn off wifi."
                return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=self.default_target))

        if normalized.action == "power_control" and normalized.type in {"shutdown", "restart"}:
            with _CONFIRMATION_LOCK:
                PENDING_POWER_CONFIRMATIONS[self.confirmation_key] = {
                    "type": normalized.type,
                    "target": normalized.target or self.default_target,
                }
            message = f"Please confirm by saying 'confirm {normalized.type}', or say cancel."
            return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=normalized.target))

        logger.info("Normalized action: %s", normalized.model_dump())
        return self._finalize_with_pc(normalized)
"""

# 6. core.py
core_code = """import logging
from core.schemas import ActionResponse
from server.parser.rules import _is_close_command

logger = logging.getLogger("jarvis.server.api.processor.core")

class CoreProcessorMixin:
    def process(self) -> ActionResponse:
        logger.info("Command after wake-word strip: %s", self.cleaned)

        response = self.handle_pending_confirmations()
        if response:
            return response

        response = self.handle_local_parsing()
        if response:
            return response

        if _is_close_command(self.cleaned):
            message = "Close will not shut down your PC. Say exit to stop Jarvis."
            return self._finalize(ActionResponse(action="type_text", text=message, response=message, target=self.default_target))

        response = self.handle_memory_queries()
        if response:
            return response

        response = self.handle_llm_generation()
        if response:
            return response
        
        # Fallback
        return self._finalize(ActionResponse(action="type_text", text="Command could not be processed.", target=self.default_target))
"""

# 7. __init__.py
init_code = """from .execution import ExecutionMixin
from .confirmation import ConfirmationMixin
from .local import LocalFallbackMixin
from .memory import MemoryQueriesMixin
from .llm import LLMMixin
from .core import CoreProcessorMixin
from core.config import WAKE_WORDS

def _strip_wake_word(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    for wake_word in WAKE_WORDS:
        if lowered.startswith(wake_word):
            remainder = stripped[len(wake_word) :].lstrip(" ,:-")
            return remainder.strip()
    return ""

def _confirmation_key(client: str, target: str) -> str:
    client_key = (client or "unknown").strip().lower() or "unknown"
    target_key = (target or "android").strip().lower() or "android"
    return f"{client_key}:{target_key}"

class CommandProcessor(ExecutionMixin, ConfirmationMixin, LocalFallbackMixin, MemoryQueriesMixin, LLMMixin, CoreProcessorMixin):
    def __init__(self, spoken_text: str, client: str):
        self.spoken_text = spoken_text
        self.client = client
        self.default_target = "pc" if client == "pc" else "android"
        self.confirmation_key = _confirmation_key(self.client, self.default_target)
        
        if self.client == "pc":
            self.cleaned = self.spoken_text
        else:
            self.cleaned = _strip_wake_word(self.spoken_text)
"""

with open(os.path.join(processor_dir, "execution.py"), "w") as f: f.write(execution_code)
with open(os.path.join(processor_dir, "confirmation.py"), "w") as f: f.write(confirmation_code)
with open(os.path.join(processor_dir, "local.py"), "w") as f: f.write(local_code)
with open(os.path.join(processor_dir, "memory.py"), "w") as f: f.write(memory_code)
with open(os.path.join(processor_dir, "llm.py"), "w") as f: f.write(llm_code)
with open(os.path.join(processor_dir, "core.py"), "w") as f: f.write(core_code)
with open(os.path.join(processor_dir, "__init__.py"), "w") as f: f.write(init_code)

print("Processor generated")
