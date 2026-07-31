import sqlite3
import os
import json
import logging
import requests
from core.config import OLLAMA_API_URL, OLLAMA_MODEL

logger = logging.getLogger("jarvis.memory.consolidation")

class SleepCycleAgent:
    def __init__(self):
        self.sqlite_path = os.getenv(
            "JARVIS_MEMORY_SQLITE_PATH",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.sqlite3"),
        )
        self.api_url = OLLAMA_API_URL
        self.model = OLLAMA_MODEL

    def _get_recent_interactions(self, limit=400):
        try:
            with sqlite3.connect(self.sqlite_path, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT user_text, action_json, created_at
                    FROM jarvis_memory_interactions
                    ORDER BY datetime(created_at) DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch interactions for consolidation: {e}")
            return []

    def _save_new_facts(self, facts):
        try:
            with sqlite3.connect(self.sqlite_path, timeout=5) as conn:
                cur = conn.cursor()
                for key, value in facts.items():
                    cur.execute(
                        """
                        INSERT INTO jarvis_memory_facts (client, fact_key, fact_value, updated_at)
                        VALUES ('pc', ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(client, fact_key)
                        DO UPDATE SET fact_value=excluded.fact_value, updated_at=CURRENT_TIMESTAMP
                        """,
                        (key.strip().lower(), str(value).strip()),
                    )
                conn.commit()
                logger.info(f"Consolidated {len(facts)} new facts into memory.")
        except Exception as e:
            logger.error(f"Failed to save consolidated facts: {e}")

    def run_consolidation(self):
        logger.info("Starting Memory Consolidation Sleep Cycle...")
        interactions = self._get_recent_interactions()
        if not interactions:
            logger.info("No recent interactions to consolidate.")
            return

        # Prepare log string
        log_lines = []
        for text, action, ts in reversed(interactions): # chronological
            log_lines.append(f"[{ts}] User: {text}")

        logs = "\n".join(log_lines)

        system_prompt = (
            "You are an AI processing logs of user interactions from the past day. "
            "Your task is to extract implicit facts, habits, and preferences about the user. "
            "Output ONLY a valid JSON object where keys are the fact names (e.g. 'likes_music', 'sleep_schedule', 'preferred_app') "
            "and values are brief strings describing the fact. If you find no facts, output {}. Do not include markdown."
        )

        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": f"Logs:\n{logs}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2
            }
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                result = data.get("response", "").strip()
                if result:
                    facts = json.loads(result)
                    if facts and isinstance(facts, dict):
                        self._save_new_facts(facts)
        except Exception as e:
            logger.error(f"Failed during LLM memory consolidation: {e}")
