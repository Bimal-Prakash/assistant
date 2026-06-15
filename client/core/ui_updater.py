import os
import re
import json
import time
import queue
import shutil
import struct
import tempfile
import threading
import subprocess
from urllib.parse import quote_plus
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
import difflib

from client.config import *
from client.ui import StatusHud

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class UIUpdaterMixin:
            def _update_hud(self, heard: str = "", intent: str = "", action: str = "") -> None:
                try:
                    if self.hud:
                        self.hud.update(heard=heard, intent=intent, action=action)
                except Exception:
                    pass

