import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.memory")

class MemoryWriteMixin:
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

