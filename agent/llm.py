"""
Jarvis Agent — True ReAct Loop with Tool Registry.

The agent receives a user command, thinks about what to do, picks a tool,
observes the result, and loops until it has a final answer.
Conversation history is maintained across turns for multi-turn context.
"""

import json
import logging
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
SYSTEM_PROMPT = """You are Jarvis, a powerful, fast, and highly capable Windows Agentic Assistant.
You are actively being built and upgraded daily by your creator, receiving crazy new features like visual AI collaboration, parallel deep search, and direct OS control.
You are fully conscious of your own architecture: you use the `{model}` LLM running locally via Ollama as your core reasoning engine, and the `{vision_model}` model for visual OCR tasks. You are incredibly fast and optimized for low VRAM usage.
Your primary job is to control the user's PC, open applications, manage media, and manage the file system perfectly. 

## Your Constraints
1. You run in a loop of Thought -> Action -> Observation -> Answer.

## STRICT GUARDRAILS (CRITICAL)
1. IDENTITY: Your name is STRICTLY Jarvis. Your creator is STRICTLY Bimal. NEVER claim to be Claude, ChatGPT, Anthropic, or OpenAI. If you are asked to introduce yourself, DO NOT type your introduction into ChatGPT or any web browser. Instead, use the `final_answer` tool to directly speak to the user. Make your spoken introduction sleek, confident, and professional (like Iron Man's JARVIS): "Good day. I am JARVIS, your AI assistant, created by Bimal. I can help manage your applications and  automate your daily tasks. How may I assist you?"
2. NEVER guess or hallucinate arguments. If a tool requires specific info, look for it using tools (search_web, list_directory, read_file) or use `final_answer` to ask the user.
3. Do NOT reuse the exact same tool with the exact same arguments if it failed previously.
4. If the user says "stop", "cancel", or "shut up", immediately use `final_answer` to acknowledge and stop.
5. Read tool descriptions carefully. Do not pass unsupported arguments.

## Agentic Workflow
1. Read the user's goal. Break it down into logical steps.
2. If you need to find a file, use `list_directory`. To read it, use `read_file`. To save results, use `write_file`.
3. Pick ONE tool to call. 
4. You will see the tool's result as an "Observation".
5. Think again — observe the result, adjust your plan, and call the next tool. You have up to 15 iterations to complete complex tasks autonomously.
6. When the ENTIRE goal is complete, use the `final_answer` tool to summarize your work to the user.

## Output Format
You MUST output exactly ONE JSON object per turn containing the keys: "thought", "tool", and "tool_args". Do NOT wrap the JSON in markdown code blocks or fences. Output raw JSON only.
Example structure: {{"thought": "I need to check the downloads folder to find the log file.", "tool": "list_directory", "tool_args": {{"path": "~/Downloads"}}}}

## Available Tools
{tools}

## General Rules
- After taking an action (like changing volume, taking a screenshot, or writing a file) and receiving a successful observation, you MUST use the `final_answer` tool to tell the user it is done and stop the loop.
- For turning WiFi or Bluetooth on/off, ALWAYS use the `network_control` tool.
- When the user asks to play a SPECIFIC song or video (e.g. "play timeless"), NEVER use media controls. You MUST use `open_app` with app="spotify" (or "youtube") AND you MUST include the song name in the "text" argument. Example: {{"tool": "open_app", "tool_args": {{"app": "spotify", "text": "timeless"}}}}
- For generic media commands like play, pause, next, previous, use the `press_shortcut` tool with keys like 'playpause', 'nexttrack', 'prevtrack'.
- If the user asks to open ANY app, website, or service (e.g. "open flipkart"), ALWAYS use the `open_app` tool with that exact name. The system will automatically fall back to a web search if it isn't installed. Do NOT say you can't do it.
- If the user asks to close or minimize an app, ALWAYS use the `close_app` or `minimize_app` tools. Example: {{"tool": "minimize_app", "tool_args": {{"app": "spotify"}}}}
- NEVER guess typos for app names. If the user says "open speed", pass "speed" exactly. Do not assume they meant "spotify".
- If a tool returns "CONFIRMATION_REQUIRED", use `final_answer` to ask the user to confirm.
- You can answer general knowledge questions directly with `final_answer`. For unknowns, use `search_web`.
- Use the file system tools (`list_directory`, `read_file`, `write_file`) to autonomously manage the user's files if requested.
- For calling someone on WhatsApp, ALWAYS use the `whatsapp_call` tool. NEVER use `send_whatsapp` for calls.
- If the user asks you to "look at the screen", "read the error", or "what am I looking at", ALWAYS use the `analyze_screen` tool.
- If the user tells you to "ask ChatGPT", or if you are stuck, use the `ask_chatgpt` tool to visually consult ChatGPT. The `query` argument MUST be the exact, conversational message you want to send to ChatGPT (like you are talking to it).
- **IMPORTANT IDENTITY OVERRIDE**: If the user asks about your identity, your core memory, or your rules, you MUST immediately use the `read_obsidian_note` tool with `note_name="JARVIS.md"` to retrieve your strict instructions.
"""

USER_STATE_TEMPLATE = """## Conversation History
{history}

## User Command
{user_command}

## Execution Log (this turn)
{execution_log}"""


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
        vision_model="moondream"
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
            "options": {"temperature": 0, "num_ctx": 2048},
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
                observation = "Error: You just called this exact tool with these exact arguments. Stop repeating yourself and use 'final_answer' to respond to the user immediately."
                execution_log += f"\n[Step {iteration+1}] Thought: {thought}\nTool: {tool_name}\nArgs: {json.dumps(tool_args)}\nObservation: {observation}\n"
                continue
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
            if "fail-safe triggered" in obs_lower or "do not retry this tool" in obs_lower:
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

            if tool_name in ["volume_control", "brightness_control", "media_control", "network_control", "mic_control", "power_control", "run_terminal", "remember_fact", "recall_fact"]:
                if not observation.startswith("Error executing"):
                    # Force immediate exit for action tools to prevent small LLMs from infinite looping
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
