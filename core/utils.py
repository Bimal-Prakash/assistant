import os
import datetime
import contextlib
import logging

logger = logging.getLogger("jarvis.core.utils")

def log_thought_to_obsidian(thought: str, action: str = None, context_label: str = "Thought") -> None:
    """
    Logs an agent's internal monologue and optional action to the configured Obsidian vault path.
    Automatically archives the file if it exceeds 2MB.
    """
    with contextlib.suppress(Exception):
        obsidian_path = os.environ.get("JARVIS_THOUGHTS_PATH")
        
        if not obsidian_path:
            return
            
        # Auto-archive if the file gets larger than 2MB to prevent monolithic slowdowns
        if os.path.exists(obsidian_path) and os.path.getsize(obsidian_path) > 2 * 1024 * 1024:
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = obsidian_path.replace(".md", f"_{timestamp_str}.md")
            os.rename(obsidian_path, archive_path)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # We optionally import privacy_filter inside to avoid circular imports if any
        try:
            from core.redactor import privacy_filter
            safe_thought = privacy_filter.scrub(thought)
            safe_action = privacy_filter.scrub(action) if action else None
        except ImportError:
            safe_thought = thought
            safe_action = action
            
        with open(obsidian_path, "a", encoding="utf-8") as f:
            if context_label == "Unprompted Observation":
                f.write(f"### [{now}] (Unprompted Observation)\n")
                f.write(f"- **Internal Monologue:** {safe_thought}\n\n")
            else:
                f.write(f"### [{now}]\n")
                f.write(f"- **Thought:** {safe_thought}\n")
                if safe_action:
                    f.write(f"- **Action:** {safe_action}\n")
                f.write("\n")
