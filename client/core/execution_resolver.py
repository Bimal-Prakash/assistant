"""Command resolver — sends everything to the backend agent.

No local interception. The agent handles all reasoning.
"""

import logging
import time
from typing import Any, Dict

from client.config import SPOKEN_FILLER_ENABLED
from client.core.semantic_router import SemanticRouter

logger = logging.getLogger("jarvis.client")

# Global lazy-initialized semantic router and NLP model
_semantic_router = None
_nlp = None

def _extract_app_name(text: str) -> str:
    """Uses spaCy NLP Dependency Parsing to extract the target application name from a command."""
    global _nlp
    if _nlp is None:
        # pyrefly: ignore [missing-import]
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        
    doc = _nlp(text)
    
    # Look for proper nouns or nouns that are not part of conversational filler
    ignore_words = {
        "open", "launch", "start", "boot", "up", "close", "kill", "quit", 
        "shut", "down", "exit", "please", "can", "you", "the", "a", "an",
        "app", "application", "window", "program", "for", "me", "hey", "jarvis",
        "favor", "screen", "computer", "system", "do", "huge", "bring"
    }
    
    # Strategy 1: Named Entities (ORG, PRODUCT)
    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT", "PERSON") and ent.text.lower() not in ignore_words:
            return ent.text

    # Strategy 2: Direct Objects (dobj) or Propositional Objects (pobj) connected to verbs
    for token in doc:
        if token.dep_ in ("dobj", "pobj") and token.text.lower() not in ignore_words:
            # Reconstruct compound nouns (like "google chrome" or "vs code")
            compounds = [t.text for t in token.lefts if t.dep_ == "compound" and t.text.lower() not in ignore_words]
            return " ".join(compounds + [token.text]).strip()

    # Strategy 3: Fallback noun chunking
    for chunk in doc.noun_chunks:
        chunk_text = " ".join([t.text for t in chunk if t.text.lower() not in ignore_words and not t.is_punct])
        if chunk_text.strip():
            return chunk_text.strip()
            
    # Strategy 4: Ultimate fallback (original logic)
    app_tokens = []
    for token in doc:
        if token.lemma_.lower() not in ignore_words and token.text.lower() not in ignore_words and not token.is_punct:
            app_tokens.append(token.text)
            
    return " ".join(app_tokens).strip()

def _resolve_context_app_name(app_name: str) -> str:
    """If the app_name is a generic pronoun, uses the Z-order window list to find the active target."""
    if not app_name or app_name.lower() in {"this", "it", "that", "that window", "the app", "the window", "current window", "the program"}:
        try:
            # pyrefly: ignore [missing-import]
            import pygetwindow as gw
            windows = gw.getAllTitles()
            for w in windows:
                w_str = str(w).strip()
                if not w_str:
                    continue
                w_lower = w_str.lower()
                # Skip empty windows, Program Manager, and the IDE/Terminal running the assistant
                if w_lower in {"", "program manager", "settings", "taskbar"}:
                    continue
                if any(skip in w_lower for skip in ["antigravity", "code", "cursor", "windows terminal", "cmd.exe", "powershell", "python", "run.py"]):
                    continue
                # The first valid window in Z-order is the most recently active non-assistant window (e.g., VLC)
                return w_str
        except Exception as e:
            import logging
            logging.getLogger("jarvis").debug(f"Failed to resolve context app name: {e}")
    return app_name

class ResolverMixin:
    def _resolve_action_for_command(self, command: str) -> Dict[str, Any]:
        import os, time
        now = time.time()
        start_t = float(os.environ.get("COMMAND_START_TIME", str(now)))
        
        # --- FAST PATH BYPASS ---
        # Bypasses the 10-15s LLM inference entirely for common commands
        cmd_lower = command.lower().strip()
        import re
        
        # Try to extract a name if the user wants to call someone
        call_match = re.search(r"\b(?:call|ring)\s+([a-zA-Z0-9_ ]+)", cmd_lower)
        
        if call_match:
            name = call_match.group(1).split(" and ")[0].split(" then ")[0].split(" because ")[0].strip()
            if name.lower().startswith("my "):
                name = name[3:].strip()
            
            # --- ULTRA-FAST OBSIDIAN ALIAS RESOLUTION ---
            # Quickly scan the local vault to resolve "mom", "dad", etc., into real names
            def resolve_alias(alias: str) -> str:
                vault = os.getenv("OBSIDIAN_VAULT_PATH", "")
                if not vault:
                    print("[Obsidian] Error: OBSIDIAN_VAULT_PATH not set in .env")
                    return alias
                if not os.path.exists(vault):
                    print(f"[Obsidian] Error: Vault path does not exist: {vault}")
                    return alias
                
                import glob, re
                
                # Normalize alias to handle "best friend" vs "bestfriend"
                clean_alias = alias.replace(" ", "").replace("'", "").replace('"', '')
                
                # (Unused global pattern removed)
                
                files_searched = 0
                for path in glob.iglob(os.path.join(vault, "**", "*.md"), recursive=True):
                    files_searched += 1
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            # Strip spaces and punctuation from the file content temporarily just for matching the alias part
                            # Actually, simpler to just use the regex which is already quite forgiving
                            for line in content.splitlines():
                                line_clean = line.replace(" ", "").replace("'", "").replace('"', '').lower()
                                if clean_alias.lower() in line_clean:
                                    # Normalize the line slightly: make "best friends" into "bestfriend" so the regex catches it
                                    semi_clean = line.replace("friends", "friend").replace("best friend", "bestfriend")
                                    
                                    # Fallback simple regex on the original line
                                    # Put longest phrases first ('name is' before 'is'), add word boundaries to '\bis\b' to avoid matching 'his'
                                    # Extract multi-word names inside quotes, or 1-2 words if no quotes
                                    # Prevent matching across sentences by replacing .*? with [^\.,;]*?
                                    extract_pattern = re.compile(
                                        rf"(?i)(?:{re.escape(alias)}|{re.escape(clean_alias)})[^\.,;]*?(?:name is|\bis\b|:|=|->)\s*[\"']?([A-Za-z0-9\s]+?)[\"']?(?:\s+|,|\.|$)",
                                        re.IGNORECASE
                                    )
                                    match = extract_pattern.search(semi_clean)
                                    if not match:
                                        match = extract_pattern.search(line)
                                        
                                    if match:
                                        print(f"\n[Obsidian] Resolved alias '{alias}' -> '{match.group(1)}' (in {os.path.basename(path)})")
                                        return match.group(1).strip()
                    except Exception: pass
                
                print(f"[Obsidian] Scanned {files_searched} notes. Alias '{alias}' not found.")
                return alias
                
            resolved_name = resolve_alias(name)
            
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "whatsapp_call",
                "contact_name": resolved_name
            }
            
        if any(ph in cmd_lower for ph in ["what did i copy", "read clipboard", "what's on my clipboard", "read what i copied"]):
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "read_clipboard"
            }

        # Media Control Fast Path
        play_pause_keywords = ["play", "pause", "play pause", "pause music", "play music", "stop music", "pause the song", "play the song", "stop the song", "pause it", "play it"]
        next_keywords = ["next", "next song", "play next song", "skip song", "next track", "skip this"]
        prev_keywords = ["previous", "previous song", "play previous song", "go back", "previous track", "last song"]

        if cmd_lower in play_pause_keywords:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "playpause"}
        elif cmd_lower in next_keywords:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "nexttrack"}
        elif cmd_lower in prev_keywords:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "prevtrack"}

        # Open Folder / File Fast Path
        is_open_cmd = cmd_lower.startswith("open ") or cmd_lower.startswith("can you open ")
        if is_open_cmd and any(ind in cmd_lower for ind in ["folder", "directory", " in that", " in this", " in it", "file", "document", "pdf"]):
            # Normalize to 'open ' to extract the path correctly
            normalized_cmd = command.lower().replace("can you open ", "open ")
            folder_to_open = normalized_cmd[5:].split(" and ")[0].split(" then ")[0].split(" because ")[0].strip()
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "open_folder",
                "folder_path": folder_to_open
            }

        # Open App Fast Path
        if cmd_lower.startswith("open "):
            import re
            app_to_open = re.split(r'\s+and\s+|\s+then\s+|\s+because\s+', command[5:], flags=re.IGNORECASE)[0].strip()
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "open_app",
                "app": app_to_open
            }

        # Close App Fast Path
        if cmd_lower.startswith("close ") or cmd_lower.startswith("clsoe "):
            import re
            app_to_close = re.split(r'\s+and\s+|\s+then\s+|\s+because\s+', command[6:], flags=re.IGNORECASE)[0].strip()
            app_to_close = _resolve_context_app_name(app_to_close)
            
            if app_to_close:
                print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
                return {
                    "action": "close_app",
                    "app": app_to_close
                }

        # Minimize App Fast Path
        if cmd_lower.startswith("minimize ") or cmd_lower.startswith("minimise "):
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "win+d"}

        # Play Song Fast Path
        import re
        play_match = re.match(r"(?i)^(?:can you )?play\s+(.*?)\s+(?:on|in)\s+([a-zA-Z0-9]+)$", cmd_lower)
        if play_match:
            song_name = play_match.group(1).strip()
            app_name = play_match.group(2).strip()
            
            # If the user asks for a random song, or uses pronouns requiring context ("their", "his", "that"), 
            # fall back to the LLM so the agent can actually resolve the context or pick a specific song intelligently!
            vague_keywords = [
                "any song", "random", "whatever", "you like", "some song", "something", 
                "any of", "their", "his", "her", "this", "that", "those", "my"
            ]
            if not any(k in song_name for k in vague_keywords):
                print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
                return {
                    "action": "open_app",
                    "app": app_name,
                    "text": song_name
                }

        # --- SEMANTIC ROUTER BYPASS ---
        global _semantic_router
        if _semantic_router is None:
            _semantic_router = SemanticRouter()
            
        semantic_intent = _semantic_router.route(command)
        if semantic_intent:
            print(f"[Benchmark] Semantic Intent detected: {semantic_intent} ({time.time() - start_t:.2f}s)")
            if semantic_intent == "OPEN_APP":
                app_name = _extract_app_name(command)
                if app_name:
                    return {"action": "open_app", "app": app_name}
            elif semantic_intent == "CLOSE_APP":
                app_name = _extract_app_name(command)
                app_name = _resolve_context_app_name(app_name)
                if app_name:
                    return {"action": "close_app", "app": app_name}
            elif semantic_intent == "MEDIA_CONTROL_PLAYPAUSE":
                return {"action": "press_shortcut", "shortcut": "playpause"}
            elif semantic_intent == "MEDIA_CONTROL_NEXT":
                return {"action": "press_shortcut", "shortcut": "nexttrack"}
            elif semantic_intent == "MEDIA_CONTROL_PREV":
                return {"action": "press_shortcut", "shortcut": "prevtrack"}
            elif semantic_intent == "MINIMIZE_APP":
                return {"action": "press_shortcut", "shortcut": "win+d"}
            elif semantic_intent == "WHATSAPP_CALL":
                import re
                call_match = re.search(r"\b(?:call|ring)\s+([a-zA-Z0-9_ ]+)", cmd_lower)
                if call_match:
                    name = call_match.group(1).strip()
                    # Reroute directly to the Call Fast Path logic (which resolves aliases)
                    # For simplicity, we just trigger the whatsapp tool here natively
                    return {"action": "whatsapp_call", "contact_name": name}
                # If regex fails, let it fall through to the LLM
            # If it's MEMORY_SEARCH, let the LLM handle it because it requires crafting a proper semantic query
            # and formulating a conversational answer.

        if self.backend_reachable is None or (now - self._last_backend_check_ts) > 120:
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
