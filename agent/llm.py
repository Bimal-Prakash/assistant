"""
Jarvis Agent — True ReAct Loop with Tool Registry.

The agent receives a user command, thinks about what to do, picks a tool,
observes the result, and loops until it has a final answer.
Conversation history is maintained across turns for multi-turn context.
"""

import json
import logging
import os
import time
from json import JSONDecodeError
from typing import Any, Dict, List, Optional

import requests

from core.config import OLLAMA_API_URL, OLLAMA_KEEP_ALIVE_SECONDS, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
from tools.registry import build_default_registry, ToolRegistry
from agent.mcp_client import get_all_mcp_tools, call_mcp_tool

logger = logging.getLogger("jarvis.agent")


class ModelError(Exception):
    pass


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

CRITICAL: Read the Conversation History! If the conversation history ALREADY contains the context or answer you need (e.g. a previously mentioned artist, name, or fact), you MUST use it directly. DO NOT search for it again. If the Execution Log contains the observation you need, use `final_answer` to respond. DO NOT repeat the exact same tool call!"""


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
        now = time.time()
        if session_id not in self._sessions:
            self._sessions[session_id] = {"turns": [], "last_active": now}
        session = self._sessions[session_id]
        session["turns"].append({"role": role, "content": content})
        session["last_active"] = now
        # Trim to max turns (each turn = 1 entry)
        if len(session["turns"]) > self._max_turns * 2:
            session["turns"] = session["turns"][-(self._max_turns * 2):]

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

    def _call_model(self, sys_prompt: str, user_prompt: str) -> Dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Step-by-step reasoning about the command and next steps."
                },
                "tool": {
                    "type": "string",
                    "enum": [t.name for t in self.registry.all_tools()],
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
            "stream": False,
            "format": schema,
            "keep_alive": self.keep_alive_seconds,
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
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
        logger.info("Raw model output: %s", raw_text[:500])

        try:
            return _extract_json(raw_text)
        except JSONDecodeError as exc:
            raise ModelError(f"Model did not return strict JSON: {exc}") from exc

    def run_agent_loop(
        self,
        user_text: str,
        contacts: Dict[str, str],
        default_target: str = "pc",
        memory_context: str = "",
        session_id: str = "default",
        max_iterations: int = 15,
    ) -> Dict[str, Any]:
        """
        Runs the ReAct agent loop.
        Returns a dict that the client can execute as an action.
        """
        # Record user turn in conversation
        self.conversations.add_turn(session_id, "user", user_text)

        # Build the tools prompt block
        tools_block = self.registry.prompt_block()

        # Execution log accumulates within this single request
        execution_log = ""
        previous_calls = set()

        for iteration in range(max_iterations):
            sys_prompt, user_prompt = _build_prompt(
                user_text=user_text,
                tools_block=tools_block,
                conversation_history=self.conversations.get_history(session_id),
                execution_log=execution_log,
            )

            try:
                action_obj = self._call_model(sys_prompt, user_prompt)
            except ModelError as e:
                logger.error("Agent model error on step %d: %s", iteration + 1, e)
                return self._make_speak_action("I encountered an error while thinking.", default_target)

            thought = action_obj.get("thought", "")
            tool_name = action_obj.get("tool", "")
            tool_args = action_obj.get("tool_args", {})

            logger.info(
                "Agent Step %d — THOUGHT: %s | TOOL: %s | ARGS: %s",
                iteration + 1, thought, tool_name, json.dumps(tool_args, ensure_ascii=False),
            )

            # Detect repeated tool calls to prevent infinite loops
            call_sig = json.dumps({"tool": tool_name, "args": tool_args}, sort_keys=True)
            if call_sig in previous_calls:
                logger.warning("Agent repeated same tool call. Breaking loop to prevent infinite loop.")
                if tool_name == "semantic_search_obsidian":
                    err_msg = "I searched my local notes but I couldn't find an answer for that."
                elif tool_name == "ask_chatgpt":
                    err_msg = "I tried asking ChatGPT, but I couldn't get a clear answer."
                elif tool_name == "analyze_ui":
                    err_msg = "I looked at the screen but I couldn't find the button or element you were referring to."
                else:
                    err_msg = "I tried to execute that action, but it didn't work as expected. Could you rephrase?"
                
                self.conversations.add_turn(session_id, "assistant", err_msg)
                return self._make_speak_action(err_msg, default_target)
            previous_calls.add(call_sig)

            # ---- final_answer: we're done ----
            if tool_name == "final_answer":
                answer_text = tool_args.get("text") or tool_args.get("message") or tool_args.get("response")
                if not answer_text and isinstance(tool_args, dict) and tool_args:
                    # Fallback: just grab the first value in the dict
                    answer_text = next(iter(tool_args.values()))
                
                if not answer_text:
                    observation = "Error: final_answer requires a 'text' argument containing what you want to say to the user. Please try again."
                    execution_log += f"\n[Step {iteration+1}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation: {observation}\n"
                    continue
                    
                self.conversations.add_turn(session_id, "assistant", str(answer_text))
                return self._make_speak_action(str(answer_text), default_target)

            # ---- Client-side actions ----
            # These return JSON with _client_action; we return them to the client.
            CLIENT_ACTIONS = {
                "open_app", "close_app", "minimize_app", "maximize_app", "restore_app", 
                "focus_app", "hide_all_windows", "snap_window", "read_clipboard", 
                "write_clipboard", "press_shortcut", "check_performance", "lock_pc", 
                "empty_recycle_bin", "take_screenshot", "show_notification", "set_timer", 
                "open_folder", "search_files", "whatsapp_call", "open_website", "send_whatsapp"
            }
            if tool_name in CLIENT_ACTIONS:
                observation = self.registry.execute(tool_name, tool_args)
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
                # If it wasn't a client action JSON, treat as observation
                execution_log += f"\n[Step {iteration+1}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation: {observation}\n"
                continue

            # ---- Server-side tools (everything else) ----
            observation = self.registry.execute(tool_name, tool_args)
            logger.info("Tool observation: %s", observation[:300])

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

            if tool_name in ["volume_control", "brightness_control", "media_control", "network_control", "mic_control", "power_control"]:
                if not observation.startswith("Error executing"):
                    # Force immediate exit for basic hardware actions to prevent small LLMs from infinite looping
                    self.conversations.add_turn(session_id, "assistant", observation)
                    return self._make_speak_action(observation, default_target)

            execution_log += f"\n[Step {iteration+1}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation: {observation}\n"

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
