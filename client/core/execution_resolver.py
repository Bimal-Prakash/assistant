"""Command resolver — sends everything to the backend agent.

No local interception. The agent handles all reasoning.
"""

import logging
import time
from typing import Any, Dict

from client.config import SPOKEN_FILLER_ENABLED

logger = logging.getLogger("jarvis.client")


class ResolverMixin:
    def _resolve_action_for_command(self, command: str) -> Dict[str, Any]:
        import os, time
        now = time.time()
        start_t = float(os.environ.get("COMMAND_START_TIME", str(now)))
        
        # --- FAST PATH BYPASS ---
        # Bypasses the 10-15s LLM inference entirely for common commands
        cmd_lower = command.lower().strip()
        if cmd_lower.startswith("call "):
            name = command[5:].strip()
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
                
                # Regex handles:
                pattern = re.compile(
                    rf"(?i){re.escape(clean_alias)}.*?(?:is|:|=|->|name is)\s*[\"']?([A-Za-z]+)[\"']?",
                    re.IGNORECASE
                )
                
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
                                    extract_pattern = re.compile(
                                        rf"(?i)(?:{re.escape(alias)}|{re.escape(clean_alias)}).*?(?:name is|\bis\b|:|=|->)\s*[\"']?([A-Za-z0-9\s]+?)[\"']?(?:\s+|,|\.|$)",
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
        if cmd_lower in ["play", "pause", "play pause", "pause music", "play music", "stop music"]:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "playpause"}
        elif cmd_lower in ["next", "next song", "play next song", "skip song", "next track"]:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "nexttrack"}
        elif cmd_lower in ["previous", "previous song", "play previous song", "go back", "previous track"]:
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {"action": "press_shortcut", "shortcut": "prevtrack"}

        # Open App Fast Path
        if cmd_lower.startswith("open "):
            app_to_open = command[5:].strip()
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "open_app",
                "app": app_to_open
            }

        # Close App Fast Path
        if cmd_lower.startswith("close "):
            app_to_close = command[6:].strip()
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
            print(f"[Benchmark] Intent detected (Fast Path Bypass): {time.time() - start_t:.2f}s")
            return {
                "action": "open_app",
                "app": app_name,
                "text": song_name
            }

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
