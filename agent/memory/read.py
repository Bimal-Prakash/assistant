import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.memory")

class MemoryReadMixin:
        def get_last_opened_app(self, client: str) -> Optional[str]:
            if not self._ensure_ready():
                return None
    
            client_key = (client or "unknown").strip().lower() or "unknown"
    
            try:
                if False and self._backend == "postgres":
                    with self._connect_postgres() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT action_json::text
                                FROM jarvis_memory_interactions
                                WHERE client = %s
                                ORDER BY created_at DESC
                                LIMIT 40
                                """,
                                (client_key,),
                            )
                            rows = cur.fetchall()
                else:
                    with self._connect_sqlite() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            """
                            SELECT action_json
                            FROM jarvis_memory_interactions
                            WHERE client = ?
                            ORDER BY datetime(created_at) DESC
                            LIMIT 40
                            """,
                            (client_key,),
                        )
                        rows = cur.fetchall()
    
                for row in rows:
                    raw = str(row[0] if isinstance(row, (list, tuple)) else row)
                    try:
                        action_obj = json.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(action_obj, dict):
                        continue
                    if str(action_obj.get("action", "")).strip().lower() == "open_app":
                        app = str(action_obj.get("app", "")).strip()
                        if app:
                            return app
                return None
            except Exception as exc:
                self._mark_not_ready(exc)
                logger.warning("Failed to load last opened app: %s", exc)
                return None

        def get_last_user_text(self, client: str) -> Optional[str]:
            if not self._ensure_ready():
                return None
    
            client_key = (client or "unknown").strip().lower() or "unknown"
    
            try:
                with self._connect_sqlite() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT user_text
                        FROM jarvis_memory_interactions
                        WHERE client = ?
                        ORDER BY datetime(created_at) DESC, id DESC
                        LIMIT 1
                        """,
                        (client_key,),
                    )
                    row = cur.fetchone()
                if row and str(row[0]).strip():
                    return str(row[0]).strip()
                return None
            except Exception as exc:
                self._mark_not_ready(exc)
                logger.warning("Failed to load last user text: %s", exc)
                return None

        def get_fact(self, client: str, fact_key: str) -> Optional[str]:
            if not self._ensure_ready():
                return None
    
            client_keys = [(client or "unknown").strip().lower() or "unknown"]
            if "pc" not in client_keys:
                client_keys.append("pc")
    
            key = (fact_key or "").strip().lower()
            if not key:
                return None
    
            try:
                with self._connect_sqlite() as conn:
                    cur = conn.cursor()
                    placeholders = ",".join("?" for _ in client_keys)
                    cur.execute(
                        f"""
                        SELECT fact_value
                        FROM jarvis_memory_facts
                        WHERE client IN ({placeholders}) AND fact_key = ?
                        ORDER BY datetime(updated_at) DESC
                        LIMIT 1
                        """,
                        tuple(client_keys + [key]),
                    )
                    row = cur.fetchone()
                if row and str(row[0]).strip():
                    return str(row[0]).strip()
                return None
            except Exception as exc:
                self._mark_not_ready(exc)
                logger.warning("Failed to load fact %s: %s", key, exc)
                return None

        def get_last_media_query(self, client: str) -> Optional[str]:
            if not self._ensure_ready():
                return None
    
            client_keys = [(client or "unknown").strip().lower() or "unknown"]
            if "pc" not in client_keys:
                client_keys.append("pc")
    
            try:
                with self._connect_sqlite() as conn:
                    cur = conn.cursor()
                    placeholders = ",".join("?" for _ in client_keys)
                    cur.execute(
                        f"""
                        SELECT action_json
                        FROM jarvis_memory_interactions
                        WHERE client IN ({placeholders})
                        ORDER BY datetime(created_at) DESC, id DESC
                        LIMIT 80
                        """,
                        tuple(client_keys),
                    )
                    rows = cur.fetchall()
    
                for row in rows:
                    raw = str(row[0] if isinstance(row, (list, tuple)) else row)
                    try:
                        action_obj = json.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(action_obj, dict):
                        continue
    
                    action = str(action_obj.get("action", "")).strip().lower()
                    app = str(action_obj.get("app", "")).strip().lower()
                    text = str(action_obj.get("text", "")).strip()
                    url = str(action_obj.get("url", "")).strip()
                    normalized_text = re.sub(r"\s+", " ", text.lower()).strip()
                    if normalized_text in {
                        "that",
                        "that song",
                        "same",
                        "same song",
                        "it",
                        "play",
                        "song",
                        "music",
                        "track",
                    }:
                        continue
    
                    if action == "open_app" and app == "spotify" and text:
                        return text
                    if action == "open_website" and "youtube.com/results" in url:
                        match = re.search(r"[?&]search_query=([^&]+)", url)
                        if match:
                            return match.group(1).replace("+", " ").strip()
                return None
            except Exception as exc:
                self._mark_not_ready(exc)
                logger.warning("Failed to load last media query: %s", exc)
                return None

        def build_context(self, client: str) -> str:
            if not self._ensure_ready():
                return ""
    
            client_key = (client or "unknown").strip().lower() or "unknown"
    
            try:
                if False and self._backend == "postgres":
                    with self._connect_postgres() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT fact_key, fact_value
                                FROM jarvis_memory_facts
                                WHERE client = %s
                                ORDER BY updated_at DESC
                                LIMIT %s
                                """,
                                (client_key, self.fact_limit),
                            )
                            facts = cur.fetchall()
    
                            cur.execute(
                                """
                                SELECT user_text, action_json::text
                                FROM jarvis_memory_interactions
                                WHERE client = %s
                                ORDER BY created_at DESC
                                LIMIT %s
                                """,
                                (client_key, self.history_limit),
                            )
                            history = cur.fetchall()
                else:
                    with self._connect_sqlite() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            """
                            SELECT fact_key, fact_value
                            FROM jarvis_memory_facts
                            WHERE client = ?
                            ORDER BY datetime(updated_at) DESC
                            LIMIT ?
                            """,
                            (client_key, self.fact_limit),
                        )
                        facts = cur.fetchall()
    
                        cur.execute(
                            """
                            SELECT user_text, action_json
                            FROM jarvis_memory_interactions
                            WHERE client = ?
                            ORDER BY datetime(created_at) DESC
                            LIMIT ?
                            """,
                            (client_key, self.history_limit),
                        )
                        history = cur.fetchall()
    
                self._last_error = None
            except Exception as exc:
                self._mark_not_ready(exc)
                logger.warning("Failed to load memory context: %s", exc)
                return ""
    
            lines: List[str] = []
            if facts:
                lines.append("Known user facts:")
                for fact_key, fact_value in facts:
                    lines.append(f"- {fact_key}: {fact_value}")
    
            if history:
                lines.append("Recent interactions (latest first):")
                for user_text, action_json in history:
                    lines.append(f"- User: {user_text}")
                    lines.append(f"  Action: {action_json}")
    
            return "\n".join(lines).strip()

