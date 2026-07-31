import os
import json
from typing import Dict

from client.config import *

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class AliasesMixin:
            def _load_dynamic_aliases(self) -> Dict[str, str]:
                if not os.path.exists(self._alias_file_path):
                    return {}
                try:
                    with open(self._alias_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        return {}
                    aliases: Dict[str, str] = {}
                    for k, v in data.items():
                        if not isinstance(k, str) or not isinstance(v, str):
                            continue
                        key = self._normalize_text_command(k)
                        value = self._normalize_text_command(v)
                        if key and value:
                            aliases[key] = value
                    return aliases
                except Exception:
                    return {}

            def _save_dynamic_aliases(self) -> None:
                try:
                    with open(self._alias_file_path, "w", encoding="utf-8") as f:
                        json.dump(self.dynamic_aliases, f, indent=2)
                except Exception:
                    pass

