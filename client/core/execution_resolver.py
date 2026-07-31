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
    """Extracts the target application name from a command using regex to stop at conjunctions."""
    import re
    text_lower = text.lower()
    ignore_words = {"the", "app", "application", "program", "window", "please", "for", "me", "it", "tab"}

    # Extract the app name and stop at words like 'and', 'then', 'on', 'in'
    match = re.search(r"\b(?:open|launch|start|boot up|close|kill|quit|exit|shut down|minimize|minimise|hide|switch tab to|switch to|switch)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\b|\s+then\b|\s+on\b|\s+in\b|$)", text_lower)
    if match:
        original_match = re.search(r"(?i)\b(?:open|launch|start|boot up|close|kill|quit|exit|shut down|minimize|minimise|hide|switch tab to|switch to|switch)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\b|\s+then\b|\s+on\b|\s+in\b|$)", text)
        if original_match:
            name_cased = original_match.group(1).strip()
            # Filter ignore words case-insensitively
            words = [w for w in name_cased.split() if w.lower() not in ignore_words]
            return " ".join(words).strip()

    # Fallback for semantic router matches without explicit verbs
    fallback_match = re.search(r"^([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\b|\s+then\b|\s+on\b|\s+in\b|$)", text_lower)
    if fallback_match:
        original_fallback = re.search(r"(?i)^([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\b|\s+then\b|\s+on\b|\s+in\b|$)", text)
        if original_fallback:
            name_cased = original_fallback.group(1).strip()
            extra_ignore = {"open", "launch", "start", "boot", "up", "close", "kill", "quit", "exit", "shut", "down", "minimize", "minimise", "hide", "can", "you", "u", "jarvis", "switch", "to"}
            all_ignore = ignore_words.union(extra_ignore)
            words = [w for w in name_cased.split() if w.lower() not in all_ignore]
            return " ".join(words).strip()

    return ""

def _resolve_context_app_name(app_name: str) -> str:
    """If the app_name is a generic pronoun, uses the Z-order window list to find the active target."""
    if not app_name or app_name.lower() in {"this", "it", "that", "that window", "the app", "the window", "current window", "the program", "this tab", "current tab", "the tab"}:
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
        import os
        now = time.time()
        start_t = float(os.environ.get("COMMAND_START_TIME", str(now)))

        # --- FAST PATH BYPASS ---
        # Bypasses the 10-15s LLM inference entirely for common commands
        cmd_lower = command.lower().strip()
        import re

        # If the command contains commas or explicit multi-step keywords, it is complex.
        # We must route it to the LLM (Backend) so it can plan the multiple steps.
        is_complex = "," in cmd_lower or " then " in cmd_lower

        # If the user explicitly mentions another communication app, force it to the LLM
        # so the fast-path doesn't blindly assume it's a WhatsApp call.
        other_platforms = ["telegram", "telegream", "telegra", "discord", "skype", "teams", "zoom", "slack"]
        mentions_other_platform = any(p in cmd_lower for p in other_platforms)

        # We will use this flag to conditionally skip bypasses below
        skip_bypass = is_complex or mentions_other_platform

        # Try to extract a name if the user wants to call someone
        call_match = re.search(r"\b(?:call|ring)\s+([a-zA-Z0-9_ ]+)", cmd_lower) if not skip_bypass else None

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

                import glob
                import re

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

                # If it's a generic family word, returning it will just make WhatsApp search for "mother"
                # which is probably wrong. Return None to force it to the LLM, which has a smarter semantic search.
                family_words = {"mother", "mom", "dad", "father", "brother", "sister", "friend", "wife", "husband"}
                if alias.lower() in family_words:
                    print(f"[Obsidian] '{alias}' is a relationship word but wasn't found in regex. Falling back to LLM.")
                    return None

                return alias

            resolved_name = resolve_alias(name)

            if resolved_name:
                print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
                return {
                    "action": "whatsapp_call",
                    "contact_name": resolved_name
                }

        if not skip_bypass and any(ph in cmd_lower for ph in ["what did i copy", "read clipboard", "what's on my clipboard", "read what i copied"]):
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "read_clipboard"
            }

        # Media Control, Open App, Close App, and Minimize App are now completely handled
        # by the enhanced TF-IDF Semantic Router below for faster and smarter NLP resolution.

        # Open Folder / File Fast Path
        folder_indicators = ["folder", "directory", " in that", " in this", " in it"]
        file_indicators = ["file", "document", "pdf", "resume", "photo", "image", "picture", "video", "csv", "txt", "spreadsheet"]
        is_open_cmd = cmd_lower.startswith("open ") or cmd_lower.startswith("can you open ")
        
        # Only open FOLDERS in the fast path. Files require semantic context from the LLM.
        if not skip_bypass and is_open_cmd and any(ind in cmd_lower for ind in folder_indicators):
            # Normalize to 'open ' to extract the path correctly
            normalized_cmd = command.lower().replace("can you open ", "open ")
            folder_to_open = normalized_cmd[5:].split(" and ")[0].split(" then ")[0].split(" because ")[0].strip()
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "open_folder",
                "folder_path": folder_to_open
            }

        # Open App Fast Path (Exclude both folders and files, and pronouns)
        is_app_open = bool(re.search(r"\b(?:open|launch|start|switch to|switch)\b", cmd_lower))
        has_pronoun = any(f" {p} " in f" {cmd_lower} " for p in ["it", "this", "that"])
        if not skip_bypass and is_app_open and not any(ind in cmd_lower for ind in folder_indicators + file_indicators) and not has_pronoun:
            app_name = _extract_app_name(command)
            if app_name:
                print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
                return {
                    "action": "open_app",
                    "app": app_name
                }

        # Close App Fast Path
        is_app_close = any(cmd_lower.startswith(p) for p in ["close ", "kill ", "quit ", "exit ", "jarvis close ", "can you close "])
        if not skip_bypass and is_app_close:
            app_name = _extract_app_name(command)
            app_name = _resolve_context_app_name(app_name)
            if app_name:
                print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
                return {
                    "action": "close_app",
                    "app": app_name
                }
                
        # Switch Tab Fast Path
        switch_tab_phrases = ["next tab", "switch tab", "go to next tab"]
        if not skip_bypass and any(p in cmd_lower for p in switch_tab_phrases):
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "ctrl+tab"}
            
        prev_tab_phrases = ["previous tab", "go to previous tab", "last tab", "go back a tab"]
        if not skip_bypass and any(p in cmd_lower for p in prev_tab_phrases):
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "ctrl+shift+tab"}
        # Play / Media Control Fast Path Expansion
        import re

        # If it's a simple unpause/resume command
        simple_play = re.match(r"(?i)^(?:can you |jarvis )?(?:just )?play(?: the (?:fucking )?(?:song|music|track))?$", cmd_lower)
        if not skip_bypass and simple_play:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "playpause"}

        # If they specify 'on/in <app>'
        play_match = re.match(r"(?i)^(?:can you |jarvis )?play\s+(.*?)\s+(?:on|in)\s+([a-zA-Z0-9]+)$", cmd_lower) if not skip_bypass else None

        # If they just say 'play <song>' without 'on <app>', assume Spotify as default
        if not play_match and not skip_bypass:
            play_match_default = re.match(r"(?i)^(?:can you |jarvis )?play\s+(.+)$", cmd_lower)
            if play_match_default:
                # Mock a match object but with Spotify as default
                song_name = play_match_default.group(1).strip()
                # Exclude if it's a generic word that should be playpause or media control
                generic_words = {
                    "the song", "the music", "the track", "it", "music", "song",
                    "some music", "audio", "next song", "next track", "the next song",
                    "previous song", "previous track", "last song", "the previous song"
                }
                if song_name.lower() not in generic_words and not song_name.lower().startswith("next ") and not song_name.lower().startswith("previous ") and not song_name.lower().startswith("last "):
                    play_match = re.match(r"(.*)", "")  # Dummy match
                    # We can't actually assign attributes to match, so we just set variables
                    app_name = "spotify"
                else:
                    play_match = None
            else:
                play_match = None
        else:
            if play_match:
                song_name = play_match.group(1).strip()
                app_name = play_match.group(2).strip()

        if play_match and not skip_bypass:
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

        semantic_intent = _semantic_router.route(command) if not skip_bypass else None
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
                return {"action": "press_shortcut", "shortcut": "prevtrack,prevtrack"}
            elif semantic_intent == "MINIMIZE_APP":
                return {"action": "press_shortcut", "shortcut": "win+d"}
            elif semantic_intent == "WHATSAPP_CALL":
                if not mentions_other_platform:
                    import re
                    call_match = re.search(r"\b(?:call|ring)\s+([a-zA-Z0-9_ ]+)", cmd_lower)
                    if call_match:
                        name = call_match.group(1).strip()
                        # Reroute directly to the Call Fast Path logic (which resolves aliases)
                        # For simplicity, we just trigger the whatsapp tool here natively
                        return {"action": "whatsapp_call", "contact_name": name}
            elif semantic_intent == "NETWORK_CONTROL":
                from tools.executors.network import exec_network_control
                net_type = "bluetooth" if "bluetooth" in cmd_lower else "wifi"
                state = "off" if any(w in cmd_lower for w in ["off", "disable", "stop"]) else "on"
                result = exec_network_control(type=net_type, state=state)
                return {"action": "type_text", "text": result, "response": result}
            elif semantic_intent == "BRIGHTNESS_CONTROL":
                from tools.system.brightness import brightness_control
                level = "up"
                if any(w in cmd_lower for w in ["down", "lower", "decrease"]): level = "down"
                if "max" in cmd_lower: level = "max"
                if "min" in cmd_lower: level = "min"
                import re
                pct_match = re.search(r"(\d+)\s*(?:percent|%)", cmd_lower)
                if pct_match: level = pct_match.group(1)
                result = brightness_control(level)
                return {"action": "type_text", "text": result, "response": result}
            elif semantic_intent == "VOLUME_CONTROL":
                from tools.system.volume import volume_control
                level = "up"
                if any(w in cmd_lower for w in ["down", "lower", "decrease"]): level = "down"
                if "mute" in cmd_lower and "unmute" not in cmd_lower: level = "mute"
                if "max" in cmd_lower: level = "max"
                if "min" in cmd_lower: level = "min"
                import re
                pct_match = re.search(r"(\d+)\s*(?:percent|%)", cmd_lower)
                if pct_match: level = pct_match.group(1)
                result = volume_control(level)
                return {"action": "type_text", "text": result, "response": result}
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
