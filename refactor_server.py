import os
import re

base_dir = r"C:\Bimal\Project\assistant"
server_dir = os.path.join(base_dir, "server")
parser_dir = os.path.join(server_dir, "parser")
api_dir = os.path.join(server_dir, "api")

os.makedirs(parser_dir, exist_ok=True)
os.makedirs(api_dir, exist_ok=True)

with open(os.path.join(server_dir, "app.py"), "r", encoding="utf-8") as f:
    app_code = f.read()

# Define the boundaries
# We can find functions by their `def ` keyword
import ast

tree = ast.parse(app_code)

def get_source_segment(node):
    lines = app_code.splitlines()
    if not hasattr(node, 'end_lineno'):
        # For python < 3.8
        return ""
    start = node.lineno - 1
    end = node.end_lineno
    return "\n".join(lines[start:end])

functions = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        functions[node.name] = get_source_segment(node)

# Dependencies
dependencies_code = """from core.config import JARVIS_MEMORY_DATABASE_URL, JARVIS_MEMORY_HISTORY_LIMIT, JARVIS_MEMORY_FACT_LIMIT
from agent.memory import PostgresMemoryStore
from agent.llm import OllamaCommandModel
import threading

MEMORY_STORE = PostgresMemoryStore(
    database_url=JARVIS_MEMORY_DATABASE_URL,
    history_limit=JARVIS_MEMORY_HISTORY_LIMIT,
    fact_limit=JARVIS_MEMORY_FACT_LIMIT,
)
model_client = OllamaCommandModel()

_CONFIRMATION_LOCK = threading.Lock()
PENDING_POWER_CONFIRMATIONS = {}
PENDING_SYSTEM_CONTROL_CLARIFICATIONS = {}
SYSTEM_CONTROL_CLARIFY_TTL_SECONDS = 15.0
"""

# Parser: Contacts
contacts_code = f"""import re
import os
import json
import logging
from core.config import CONTACTS_FILE

logger = logging.getLogger("jarvis.parser.contacts")

{functions.get('_normalize_contact_key', '')}

{functions.get('_normalize_phone', '')}

{functions.get('_load_contacts', '')}

CONTACTS = _load_contacts(CONTACTS_FILE)

{functions.get('_resolve_contact_phone', '')}
"""

# Parser: Media
media_code = f"""import re
from typing import Optional

{functions.get('_normalize_spotify_query', '')}

{functions.get('_normalize_media_query', '')}

{functions.get('_youtube_search_action', '')}

{functions.get('_extract_spotify_query', '')}
"""

# Parser: System
system_code = f"""import re
from typing import Optional, Dict, Any
from core.schemas import ActionResponse

{functions.get('_extract_volume_brightness_scope', '')}

{functions.get('_extract_on_off_direction', '')}

{functions.get('_extract_adjust_direction', '')}

{functions.get('_build_system_control_action', '')}

{functions.get('_should_prompt_for_volume_brightness', '')}

{functions.get('_parse_percentage_level', '')}

{functions.get('_clean_response_text', '')}

{functions.get('_clean_slot_text', '')}
"""

# Parser: Rules
rules_code = f"""import re
from core.schemas import ActionResponse
from server.dependencies import MEMORY_STORE
from .media import _extract_spotify_query, _youtube_search_action
from .system import _extract_on_off_direction

{functions.get('_is_close_command', '')}

{functions.get('_is_close_like_command', '')}

{functions.get('_is_power_confirmation', '')}

{functions.get('_is_conversational_query', '')}

{functions.get('_rule_based_action', '')}
"""

# Parser: Normalizer
normalizer_code = f"""import re
from typing import Dict, Any
from core.config import ALLOWED_ACTIONS
from core.schemas import ActionResponse
from .system import _parse_percentage_level, _clean_response_text, _clean_slot_text
from .contacts import _normalize_phone, _resolve_contact_phone

{functions.get('_extract_target', '')}

{functions.get('_normalize_action', '')}
"""

# API Routes
api_code = f"""import time
import logging
import re
from fastapi import APIRouter
from core.config import HOST, PORT, JARVIS_MEMORY_HISTORY_LIMIT, JARVIS_MEMORY_FACT_LIMIT, WAKE_WORDS
from core.schemas import CommandRequest, ActionResponse
from server.dependencies import MEMORY_STORE, model_client, _CONFIRMATION_LOCK, PENDING_POWER_CONFIRMATIONS, PENDING_SYSTEM_CONTROL_CLARIFICATIONS, SYSTEM_CONTROL_CLARIFY_TTL_SECONDS
from server.parser.contacts import CONTACTS
from server.parser.rules import _is_power_confirmation, _is_close_command, _is_conversational_query, _rule_based_action
from server.parser.system import _extract_volume_brightness_scope, _extract_adjust_direction, _build_system_control_action, _should_prompt_for_volume_brightness
from server.parser.media import _extract_spotify_query
from server.parser.normalizer import _normalize_action
from agent.llm import ModelError
from tools.dispatch import execute_pc_system_action

logger = logging.getLogger("jarvis.server.api")

router = APIRouter()

{functions.get('_strip_wake_word', '')}

{functions.get('_confirmation_key', '')}

{functions.get('_maybe_execute_pc_control', '')}

{functions.get('_remember_and_return', '')}

{functions.get('health', '')}

{functions.get('status', '')}

{functions.get('command', '')}
"""

# New App.py
new_app_code = """import logging
from fastapi import FastAPI
from server.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

app = FastAPI(title="Jarvis Assistant API", version="1.0.0")

app.include_router(router)
"""

with open(os.path.join(server_dir, "dependencies.py"), "w", encoding="utf-8") as f: f.write(dependencies_code)
with open(os.path.join(parser_dir, "__init__.py"), "w", encoding="utf-8") as f: f.write("")
with open(os.path.join(parser_dir, "contacts.py"), "w", encoding="utf-8") as f: f.write(contacts_code)
with open(os.path.join(parser_dir, "media.py"), "w", encoding="utf-8") as f: f.write(media_code)
with open(os.path.join(parser_dir, "system.py"), "w", encoding="utf-8") as f: f.write(system_code)
with open(os.path.join(parser_dir, "rules.py"), "w", encoding="utf-8") as f: f.write(rules_code)
with open(os.path.join(parser_dir, "normalizer.py"), "w", encoding="utf-8") as f: f.write(normalizer_code)

with open(os.path.join(api_dir, "__init__.py"), "w", encoding="utf-8") as f: f.write("")
with open(os.path.join(api_dir, "routes.py"), "w", encoding="utf-8") as f: f.write(api_code)

with open(os.path.join(server_dir, "app.py"), "w", encoding="utf-8") as f: f.write(new_app_code)

print("Server refactoring completed!")
