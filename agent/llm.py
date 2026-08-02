"""
Jarvis Agent — True ReAct Loop with Tool Registry.

The agent receives a user command, thinks about what to do, picks a tool,
observes the result, and loops until it has a final answer.
Conversation history is maintained across turns for multi-turn context.
"""

import json
import logging
import os
import re
import time
from json import JSONDecodeError
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.config import OLLAMA_API_URL, OLLAMA_KEEP_ALIVE_SECONDS, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
from tools.registry import build_default_registry, ToolRegistry
from agent.mcp_client import get_all_mcp_tools, call_mcp_tool

logger = logging.getLogger("jarvis.agent")


class ModelError(Exception):
    pass

_CHROMA_CLIENT = None
_CHROMA_COLLECTION = None
import threading
_CHROMA_LOCK = threading.Lock()


# ------------------------------------------------------------------
# JSON extraction from model output (handles markdown fences, etc.)
# ------------------------------------------------------------------
def _extract_json(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        raise JSONDecodeError("Empty model response", text, 0)

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
        raise JSONDecodeError("Root JSON is not an object", text, 0)
    except JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except JSONDecodeError:
            continue

    final_answer_match = re.match(r"^\**\s*final_answer\s*\**\s*:\s*(.+)$", text, flags=re.IGNORECASE | re.DOTALL)
    if final_answer_match:
        answer = final_answer_match.group(1).strip()
        return {
            "thought": "The model returned a final answer in plain text instead of JSON. I will normalize it.",
            "tool": "final_answer",
            "tool_args": {"text": answer},
        }

    raise JSONDecodeError("No JSON object found", text, 0)


# ------------------------------------------------------------------
# System prompt builder
# ------------------------------------------------------------------
from core.prompts import SYSTEM_PROMPT

USER_STATE_TEMPLATE = """## Conversation History
{history}

## User Command
{user_command}

## Execution Log (this turn)
{execution_log}

CRITICAL INSTRUCTIONS:
1. If the Execution Log contains search results, READ THEM. If you find the answer (even partially), use `final_answer`.
2. NEVER repeat the exact same tool call. If you are stuck, use `final_answer` to ask the user.

OUTPUT FORMAT:
You MUST respond with a single valid JSON object containing exactly three keys: "thought", "tool", and "tool_args". Do NOT include markdown formatting. Do NOT include conversational text.
Example:
{{
  "thought": "The observation says 'The capital of France is Paris'. I will use the final_answer tool to relay this.",
  "tool": "final_answer",
  "tool_args": {{"text": "The capital of France is Paris."}}
}}"""


def _build_prompt(
    user_text: str,
    tools_block: str,
    conversation_history: List[Dict[str, str]],
    execution_log: str = "",
) -> str:
    if conversation_history:
        history_lines = []
        for turn in conversation_history:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            history_lines.append(f"{role}: {content}")
        history_str = "\n".join(history_lines)
    else:
        history_str = "(no previous conversation)"

    sys_prompt = SYSTEM_PROMPT.format(
        tools=tools_block,
        model=OLLAMA_MODEL or "configured",
        vision_model="moondream",
        assistant_name=os.getenv("JARVIS_ASSISTANT_NAME", "JARVIS"),
        creator_name=os.getenv("JARVIS_CREATOR_NAME", "an unknown developer")
    )
    user_prompt = USER_STATE_TEMPLATE.format(
        history=history_str,
        user_command=user_text,
        execution_log=execution_log or "(none yet)",
    )
    return sys_prompt, user_prompt


# ------------------------------------------------------------------
# Conversation Manager — keeps short-term turn history
# ------------------------------------------------------------------
class ConversationManager:
    def __init__(self, max_turns: int = 5, ttl_seconds: float = 300.0):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._max_turns = max_turns
        self._ttl = ttl_seconds

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        import time
        now = time.time()
        if session_id not in self._sessions:
            self._sessions[session_id] = {"turns": [], "last_active": now}
        session = self._sessions[session_id]
        session["turns"].append({"role": role, "content": content})
        session["last_active"] = now
        # Trim to max turns (each turn = 1 entry)
        if len(session["turns"]) > self._max_turns * 2:
            session["turns"] = session["turns"][-(self._max_turns * 2):]

        import threading
        threading.Thread(target=self._index_chat_turn, args=(role, content), daemon=True).start()

    def _index_chat_turn(self, role: str, content: str):
        if not content.strip() or role == "system":
            return

        try:
            global _CHROMA_CLIENT, _CHROMA_COLLECTION, _CHROMA_LOCK
            with _CHROMA_LOCK:
                if _CHROMA_CLIENT is None:
                    # pyrefly: ignore [missing-import]
                    import chromadb
                    # pyrefly: ignore [missing-import]
                    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
                    from core.config import OLLAMA_API_URL
                    import os

                    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db_chat")
                    _CHROMA_CLIENT = chromadb.PersistentClient(path=db_path)
                    base_url = OLLAMA_API_URL.replace("/api/generate", "")
                    ef = OllamaEmbeddingFunction(
                        model_name="nomic-embed-text",
                        url=f"{base_url}/api/embeddings"
                    )
                    _CHROMA_COLLECTION = _CHROMA_CLIENT.get_or_create_collection(name="chat_history", embedding_function=ef)
            import time

            doc_id = f"{int(time.time()*1000)}_{role}"
            doc = f"{role.capitalize()}: {content}"
            _CHROMA_COLLECTION.add(
                documents=[doc],
                metadatas=[{"role": role, "timestamp": time.time()}],
                ids=[doc_id]
            )
        except Exception as e:
            logger.warning(f"Failed to index chat turn: {e}")

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        self._cleanup()
        session = self._sessions.get(session_id)
        if not session:
            return []
        return list(session["turns"])

    def _cleanup(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s["last_active"] > self._ttl]
        for sid in expired:
            del self._sessions[sid]


# ------------------------------------------------------------------
# The Agent
# ------------------------------------------------------------------
class OllamaCommandModel:
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        api_url: str = OLLAMA_API_URL,
        timeout_seconds: int = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.keep_alive_seconds = OLLAMA_KEEP_ALIVE_SECONDS
        self.registry: ToolRegistry = build_default_registry()
        self.conversations = ConversationManager()
        self.pending_actions: Dict[str, Dict[str, Any]] = {}
        self._register_mcp_tools()

    def _register_mcp_tools(self) -> None:
        """Register any active MCP tools into the registry."""
        from tools.registry import Tool
        for mcp_tool in get_all_mcp_tools():
            name = mcp_tool["name"]

            def _make_executor(tool_name: str):
                def _executor(**kwargs):
                    return call_mcp_tool(tool_name, kwargs)
                return _executor

            self.registry.register(Tool(
                name=name,
                description=mcp_tool.get("description", "MCP tool"),
                parameters=mcp_tool.get("inputSchema", {"properties": {}}),
                executor=_make_executor(name),
            ))

    def _call_model(self, sys_prompt: str, user_prompt: str, context: Optional[List[int]] = None) -> Tuple[Dict[str, Any], List[int]]:
        schema = {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Step-by-step reasoning. IMPORTANT: If you just received an observation from a search tool, you MUST explicitly quote the relevant sentences from the observation here before deciding your next tool."
                },
                "tool": {
                    "type": "string",
                    "enum": [t.name for t in self.registry.all_tools()] + ["final_answer"],
                    "description": "The exact name of the tool to run, or 'final_answer'."
                },
                "tool_args": {
                    "type": "object",
                    "description": "The arguments for the tool. For 'final_answer', must include the 'text' key."
                }
            },
            "required": ["thought", "tool", "tool_args"]
        }

        payload = {
            "model": self.model,
            "system": sys_prompt,
            "prompt": user_prompt,
            "context": context or [],
            "stream": False,
            "keep_alive": self.keep_alive_seconds,
            "options": {
                "temperature": 0,
                "num_ctx": 3072,
                "num_predict": 512,
                "num_batch": 256,
            },
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ModelError(f"Failed to reach Ollama API at {self.api_url}: {exc}") from exc

        if response.status_code != 200:
            raise ModelError(f"Ollama API returned status {response.status_code}: {response.text[:300]}")

        try:
            body = response.json()
        except ValueError as exc:
            raise ModelError("Ollama response was not valid JSON") from exc

        raw_text = str(body.get("response", "")).strip()
        context = body.get("context", [])
        logger.info("Raw model output: %s", raw_text[:500])

        try:
            return _extract_json(raw_text), context
        except JSONDecodeError as exc:
            raise ModelError(f"Model did not return strict JSON: {exc}") from exc

    def _force_unload_model(self) -> None:
        """Unload the current model from VRAM to make room for other models (e.g. vision)."""
        logger.info(f"Force unloading model {self.model} from VRAM...")
        payload = {
            "model": self.model,
            "prompt": "",
            "keep_alive": 0
        }
        try:
            requests.post(self.api_url, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to unload model {self.model}: {e}")

    def _classify_intent(self, user_text: str) -> str:
        """Classifies the user intent into a specific category to filter tools."""
        from core.prompts import CLASSIFIER_PROMPT
        try:
            payload = {
                "model": self.model,
                "prompt": f"User: \"{user_text}\"\n",
                "system": CLASSIFIER_PROMPT,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_ctx": 2048,
                }
            }
            if self.keep_alive_seconds > 0:
                payload["keep_alive"] = f"{self.keep_alive_seconds}s"
            elif self.keep_alive_seconds == -1:
                payload["keep_alive"] = "-1"

            import requests
            response = requests.post(self.api_url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            
            result = response.json().get("response", "").strip().lower()
            
            valid_categories = {"system_control", "app_control", "web", "obsidian", "memory", "file", "chat", "vision", "system_interact", "general"}
            
            for word in result.split():
                clean_word = "".join(c for c in word if c.isalnum() or c == "_")
                if clean_word in valid_categories:
                    return clean_word
                    
            return "general"
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            return "general"

    def run_agent_loop(
        self,
        user_text: str,
        contacts: Dict[str, str],
        default_target: str = "pc",
        memory_context: str = "",
        session_id: str = "default",
        max_iterations: int = 5,
        client_device: str = "pc",
    ) -> Dict[str, Any]:
        """
        Runs the ReAct agent loop.
        Returns a dict that the client can execute as an action.
        """
        # Record user turn in conversation
        self.conversations.add_turn(session_id, "user", user_text)

        # Check pending actions for confirmation
        forced_action = None
        if session_id in self.pending_actions:
            import re
            user_lower = user_text.lower()
            is_confirming = bool(re.search(r'\b(yes|yeah|do it|proceed|confirm|ok|sure|go ahead|yep|y)\b', user_lower))
            
            pending = self.pending_actions.pop(session_id)
            if is_confirming:
                logger.info(f"User confirmed pending action: {pending['tool']}")
                forced_action = pending
            else:
                logger.info(f"User rejected pending action: {pending['tool']}")

        # Stage 1: Classify Intent
        category = self._classify_intent(user_text)
        logger.info(f"Classified intent category: {category}")

        # Stage 2: Build the tools prompt block
        tools_block = self.registry.prompt_block(category=category)

        # Execution log accumulates within this single request
        execution_log = ""
        previous_calls = {}
        
        from tools.executors.system_observe import exec_observe_desktop
        from agent.controller import verify_action_success
        import time

        step_count = 0
        while step_count < max_iterations:
            step_count += 1
            
            # Observe Phase
            pre_observe = exec_observe_desktop()
            
            sys_prompt, user_prompt = _build_prompt(
                user_text=user_text,
                tools_block=tools_block,
                conversation_history=self.conversations.get_history(session_id),
                execution_log=execution_log + f"\n\n[System Observation Before Action]\n{pre_observe}",
            )

            if forced_action and step_count == 1:
                action_obj = forced_action
                action_obj["thought"] = "User explicitly confirmed this action. Executing now."
            else:
                try:
                    action_obj, _ = self._call_model(sys_prompt, user_prompt, None)
                except ModelError as e:
                    logger.error("Agent model error on step %d: %s", step_count, e)
                    return self._make_speak_action("I encountered an error while thinking.", default_target)

            thought = action_obj.get("thought", "")
            tool_name = action_obj.get("tool", "")
            tool_args = action_obj.get("tool_args", {})

            logger.info(
                "Agent Step %d — THOUGHT: %s | TOOL: %s | ARGS: %s",
                step_count, thought, tool_name, json.dumps(tool_args, ensure_ascii=False),
            )

            # --- AGI Thought Logging to Obsidian ---
            if thought:
                import os, datetime
                import contextlib
                from core.redactor import privacy_filter
                with contextlib.suppress(Exception):
                    obsidian_path = os.environ.get("JARVIS_THOUGHTS_PATH")
                    
                    if obsidian_path:
                        # Auto-archive if the file gets larger than 2MB to prevent monolithic slowdowns
                        if os.path.exists(obsidian_path) and os.path.getsize(obsidian_path) > 2 * 1024 * 1024:
                            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            archive_path = obsidian_path.replace(".md", f"_{timestamp_str}.md")
                            os.rename(obsidian_path, archive_path)

                        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        safe_thought = privacy_filter.scrub(thought)
                        safe_args = privacy_filter.scrub(json.dumps(tool_args, ensure_ascii=False))
                        with open(obsidian_path, "a", encoding="utf-8") as f:
                            f.write(f"### [{now}]\n")
                            f.write(f"- **Thought:** {safe_thought}\n")
                            f.write(f"- **Action:** `{tool_name}` with args: `{safe_args}`\n\n")

            # Detect repeated tool calls to prevent infinite loops
            call_sig = json.dumps({"tool": tool_name, "args": tool_args}, sort_keys=True)
            if call_sig in previous_calls:
                previous_calls[call_sig] += 1
                if previous_calls[call_sig] >= 2:
                    logger.warning("Agent repeated same tool call 2 times. Forcing abort to prevent loop.")
                    return self._make_speak_action("I don't have enough information to answer that.", default_target)
                
                logger.warning("Agent repeated same tool call. Injecting error to prompt.")
                observation = f"ERROR: You just repeated the exact same tool call `{tool_name}` with identical arguments! You MUST use a different tool, change the arguments (e.g. use a shorter search query), or use `final_answer` to respond."
                execution_log += f"\n[Step {step_count}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation:\n<observation>\n{observation}\n</observation>\n"
                continue
            else:
                previous_calls[call_sig] = 1

            # --- Privacy Policy Layer ---
            tool_obj = self.registry.get(tool_name)
            if tool_obj:
                from core.audit import audit_logger
                if tool_obj.data_access:
                    audit_logger.log_access(tool_name, tool_obj.data_access, tool_obj.risk_tier)
                
                if tool_obj.risk_tier in ["dangerous", "external"]:
                    import re
                    user_lower = user_text.lower()
                    confirmed = bool(re.search(r'\b(yes|yeah|do it|proceed|confirm|ok|sure|go ahead)\b', user_lower))
                    if forced_action and step_count == 1:
                        confirmed = True
                        
                    if not confirmed:
                        self.pending_actions[session_id] = {"tool": tool_name, "tool_args": tool_args}
                        return {
                            "action": "confirm_action",
                            "target": default_target,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "risk_tier": tool_obj.risk_tier,
                            "response": f"Confirmation required for high-risk action: {tool_name}"
                        }
                    else:
                        logger.info(f"User implicitly/explicitly confirmed high-risk action {tool_name}")

            # ---- final_answer: we're done ----
            if tool_name == "final_answer":
                answer_text = (
                    tool_args.get("text")
                    or tool_args.get("message")
                    or tool_args.get("response")
                    or tool_args.get("answer")
                )

                if not answer_text:
                    observation = "Error: final_answer requires a 'text' argument containing what you want to say to the user. Please try again."
                    execution_log += f"\n[Step {step_count}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation:\n<observation>\n{observation}\n</observation>\n"
                    continue

                self.conversations.add_turn(session_id, "assistant", str(answer_text))
                return self._make_speak_action(str(answer_text), default_target)

            # ---- Client-side actions ----
            # These return JSON with _client_action; we return them to the client.
            CLIENT_ACTIONS = {
                "open_app", "close_app", "minimize_app", "maximize_app", "restore_app",
                "hide_all_windows", "snap_window", "read_clipboard",
                "write_clipboard", "press_shortcut", "check_performance", "lock_pc",
                "empty_recycle_bin", "save_screenshot_to_desktop", "show_notification", "set_timer",
                "open_folder", "open_file", "whatsapp_call", "open_website", "send_whatsapp", "type_string"
            }
            # Inject client device so the registry knows whether to execute backend UI automation
            if isinstance(tool_args, dict):
                tool_args["client_device"] = client_device

            if tool_name in CLIENT_ACTIONS:
                observation = self.registry.execute(tool_name, tool_args)
                if client_device != "pc":
                    try:
                        client_action = json.loads(observation)
                        if isinstance(client_action, dict) and "_client_action" in client_action:
                            action_type = client_action.pop("_client_action")
                            response_text = f"Executing {tool_name}."
                            self.conversations.add_turn(session_id, "assistant", response_text)
                            result = {"action": action_type, "target": default_target, "response": response_text}
                            result.update(client_action)
                            return result
                    except (json.JSONDecodeError, ValueError):
                        pass
                # If it wasn't a client action JSON (or if it's PC native), treat as observation
                execution_log += f"\n[Step {step_count}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation:\n<observation>\n{observation}\n</observation>\n"
                continue

            # ---- Server-side tools (everything else) ----
            if tool_name == "look_at_screen":
                self._force_unload_model()

            observation = self.registry.execute(tool_name, tool_args)
            logger.info("Tool observation: %s", observation[:300])

            # Verify Phase
            time.sleep(0.5) # Give UI a moment to update
            post_observe = exec_observe_desktop()
            verification_error = verify_action_success(tool_name, tool_args, pre_observe, post_observe)
            
            if verification_error:
                observation += f"\n\n[VERIFICATION FAILURE]\n{verification_error}"
                logger.warning(f"Action verification failed: {verification_error}")
            
            # --- INSTANT KILL SWITCH & FATAL ABORT ---
            obs_lower = observation.lower()
            if "fail-safe triggered" in obs_lower:
                abort_msg = "Task aborted! The kill switch or fail-safe was triggered."
                self.conversations.add_turn(session_id, "assistant", abort_msg)
                return self._make_speak_action(abort_msg, default_target)

            # Check if confirmation is required
            if observation.startswith("CONFIRMATION_REQUIRED"):
                confirm_msg = observation.replace("CONFIRMATION_REQUIRED:", "").strip()
                self.conversations.add_turn(session_id, "assistant", confirm_msg)
                return {
                    "action": "type_text",
                    "text": confirm_msg,
                    "response": confirm_msg,
                    "target": default_target,
                    "_needs_confirmation": True,
                    "_pending_tool": tool_name,
                    "_pending_args": tool_args,
                }
            
            if "error:" in obs_lower and "fatal" in obs_lower:
                logger.error("Fatal error from tool %s. Aborting loop.", tool_name)
                return self._make_speak_action(f"I encountered a fatal error running {tool_name}.", default_target)

            if tool_name in ["volume_control", "brightness_control", "media_control", "network_control", "mic_control", "power_control", "look_at_screen"]:
                if not observation.startswith("Error executing"):
                    # Force immediate exit for basic hardware actions to prevent small LLMs from infinite looping
                    self.conversations.add_turn(session_id, "assistant", observation)
                    return self._make_speak_action(observation, default_target)

            execution_log += f"\n[Step {step_count}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation:\n<observation>\n{observation}\n</observation>\n"

        # Ran out of iterations
        fallback = "I thought too long and had to stop. Could you rephrase?"
        self.conversations.add_turn(session_id, "assistant", fallback)
        return self._make_speak_action(fallback, default_target)

    @staticmethod
    def _make_speak_action(text: str, target: str) -> Dict[str, Any]:
        return {
            "action": "type_text",
            "text": text,
            "response": text,
            "target": target,
        }
