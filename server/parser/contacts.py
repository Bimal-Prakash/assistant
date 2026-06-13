import re
import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from core.config import CONTACTS_FILE

logger = logging.getLogger("jarvis.parser.contacts")

def _normalize_contact_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())

def _normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    return re.sub(r"\D", "", phone)

def _load_contacts(path: Path) -> Dict[str, str]:
    if not path.exists():
        logger.warning("Contacts file not found at %s; continuing with empty contacts", path)
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("contacts.json must contain a JSON object map of name->phone")

    contacts: Dict[str, str] = {}
    for raw_name, raw_phone in data.items():
        if not isinstance(raw_name, str) or not isinstance(raw_phone, str):
            continue
        key = _normalize_contact_key(raw_name)
        if key:
            contacts[key] = _normalize_phone(raw_phone)

    return contacts

CONTACTS = _load_contacts(CONTACTS_FILE)

def _resolve_contact_phone(contact_name: str) -> Optional[str]:
    key = _normalize_contact_key(contact_name)
    if key in CONTACTS:
        return CONTACTS[key]

    for contact_key, phone in CONTACTS.items():
        if key in contact_key or contact_key in key:
            return phone
    return None
