import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.memory")

class MemoryConnectionMixin:
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

