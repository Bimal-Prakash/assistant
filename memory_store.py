import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.memory")


class PostgresMemoryStore:
    def __init__(self, database_url: str, history_limit: int = 12, fact_limit: int = 20) -> None:
        self.database_url = (database_url or "").strip()
        self.history_limit = max(1, history_limit)
        self.fact_limit = max(1, fact_limit)

        self.sqlite_path = os.getenv(
            "JARVIS_MEMORY_SQLITE_PATH",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.sqlite3"),
        )

        self._ready = False
        self._last_error: Optional[str] = None
        self._last_connect_attempt_ts = 0.0
        self._retry_interval_seconds = 5.0
        self._backend = "none"

        if self._ensure_sqlite_ready(force=True):
            self._backend = "sqlite"
        else:
            logger.warning("SQLite memory initialization failed; memory is disabled")

    @property
    def configured(self) -> bool:
        # Memory is considered configured if either backend is usable.
        return self._backend == "sqlite" or bool(self.sqlite_path)

    @property
    def enabled(self) -> bool:
        return self._ready

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def _mark_not_ready(self, exc: Exception) -> None:
        self._ready = False
        self._last_error = str(exc)

    def _connect_postgres(self):
        raise RuntimeError("Postgres backend has been removed; use SQLite memory backend")

    def _connect_sqlite(self):
        return sqlite3.connect(self.sqlite_path, timeout=5)

    def _ensure_postgres_ready(self, force: bool = False) -> bool:
        return False

    def _ensure_sqlite_ready(self, force: bool = False) -> bool:
        now = time.time()
        if not force and (now - self._last_connect_attempt_ts) < self._retry_interval_seconds:
            return False
        self._last_connect_attempt_ts = now

        try:
            with self._connect_sqlite() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jarvis_memory_interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client TEXT NOT NULL,
                        user_text TEXT NOT NULL,
                        action_json TEXT NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jarvis_memory_facts (
                        client TEXT NOT NULL,
                        fact_key TEXT NOT NULL,
                        fact_value TEXT NOT NULL,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (client, fact_key)
                    )
                    """
                )
                conn.commit()
            self._ready = True
            self._last_error = None
            self._backend = "sqlite"
            logger.info("SQLite memory initialized at %s", self.sqlite_path)
            return True
        except Exception as exc:
            self._mark_not_ready(exc)
            return False

    def _ensure_ready(self) -> bool:
        if self._backend == "sqlite":
            if self._ready:
                return True
            return self._ensure_sqlite_ready(force=False)

        return self._ensure_sqlite_ready(force=False)

    def _extract_facts(self, text: str) -> Dict[str, str]:
        msg = (text or "").strip()
        if not msg:
            return {}

        lowered = msg.lower()
        facts: Dict[str, str] = {}

        name_match = re.search(r"\bmy name is\s+([a-zA-Z][a-zA-Z\s\-']{1,60})", msg, flags=re.IGNORECASE)
        if name_match:
            facts["name"] = name_match.group(1).strip()

        city_match = re.search(r"\bi (?:live in|am from)\s+([a-zA-Z][a-zA-Z\s\-']{1,60})", msg, flags=re.IGNORECASE)
        if city_match:
            facts["location"] = city_match.group(1).strip()

        likes_match = re.search(r"\bi like\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
        if likes_match and " not " not in lowered:
            facts["likes"] = likes_match.group(1).strip()

        dislikes_match = re.search(r"\bi (?:do not|don't) like\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
        if dislikes_match:
            facts["dislikes"] = dislikes_match.group(1).strip()

        work_match = re.search(r"\bi work as\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
        if work_match:
            facts["profession"] = work_match.group(1).strip()

        preference_match = re.search(r"\bi prefer\s+([a-zA-Z0-9][a-zA-Z0-9\s\-']{1,80})", msg, flags=re.IGNORECASE)
        if preference_match:
            facts["preference"] = preference_match.group(1).strip()

        return facts

    def remember_interaction(self, client: str, user_text: str, action: Dict[str, Any]) -> None:
        if not self._ensure_ready():
            return

        client_key = (client or "unknown").strip().lower() or "unknown"
        cleaned_text = (user_text or "").strip()
        if not cleaned_text:
            return

        action_json = json.dumps(action)

        try:
            if False and self._backend == "postgres":
                with self._connect_postgres() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO jarvis_memory_interactions (client, user_text, action_json)
                            VALUES (%s, %s, %s::jsonb)
                            """,
                            (client_key, cleaned_text, action_json),
                        )
                        cur.execute(
                            """
                            DELETE FROM jarvis_memory_interactions
                            WHERE client = %s
                              AND id NOT IN (
                                  SELECT id
                                  FROM jarvis_memory_interactions
                                  WHERE client = %s
                                  ORDER BY created_at DESC
                                  LIMIT 400
                              )
                            """,
                            (client_key, client_key),
                        )
                        for fact_key, fact_value in self._extract_facts(cleaned_text).items():
                            cur.execute(
                                """
                                INSERT INTO jarvis_memory_facts (client, fact_key, fact_value, updated_at)
                                VALUES (%s, %s, %s, NOW())
                                ON CONFLICT (client, fact_key)
                                DO UPDATE SET fact_value = EXCLUDED.fact_value, updated_at = NOW()
                                """,
                                (client_key, fact_key, fact_value),
                            )
                    conn.commit()
            else:
                with self._connect_sqlite() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO jarvis_memory_interactions (client, user_text, action_json)
                        VALUES (?, ?, ?)
                        """,
                        (client_key, cleaned_text, action_json),
                    )
                    cur.execute(
                        """
                        DELETE FROM jarvis_memory_interactions
                        WHERE client = ?
                          AND id NOT IN (
                              SELECT id
                              FROM jarvis_memory_interactions
                              WHERE client = ?
                              ORDER BY datetime(created_at) DESC
                              LIMIT 400
                          )
                        """,
                        (client_key, client_key),
                    )
                    for fact_key, fact_value in self._extract_facts(cleaned_text).items():
                        cur.execute(
                            """
                            INSERT INTO jarvis_memory_facts (client, fact_key, fact_value, updated_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(client, fact_key)
                            DO UPDATE SET fact_value=excluded.fact_value, updated_at=CURRENT_TIMESTAMP
                            """,
                            (client_key, fact_key, fact_value),
                        )
                    conn.commit()
            self._last_error = None
        except Exception as exc:
            self._mark_not_ready(exc)
            logger.warning("Failed to persist memory: %s", exc)

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

    def set_fact(self, client: str, fact_key: str, fact_value: str) -> bool:
        """Set or update a fact in memory."""
        if not self._ensure_ready():
            return False

        client_key = (client or "unknown").strip().lower() or "unknown"
        key = (fact_key or "").strip().lower()
        value = (fact_value or "").strip()

        if not key or not value:
            return False

        try:
            with self._connect_sqlite() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO jarvis_memory_facts (client, fact_key, fact_value, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(client, fact_key)
                    DO UPDATE SET fact_value=excluded.fact_value, updated_at=CURRENT_TIMESTAMP
                    """,
                    (client_key, key, value),
                )
                conn.commit()
            self._last_error = None
            return True
        except Exception as exc:
            self._mark_not_ready(exc)
            logger.warning("Failed to set fact %s: %s", key, exc)
            return False

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
