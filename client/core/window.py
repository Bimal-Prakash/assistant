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

class WindowMixin:
            def _activate_wake_window(self) -> None:
                self.wake_active_until = time.time() + WAKE_ACTIVE_SECONDS

            def _wake_window_active(self) -> bool:
                return time.time() < self.wake_active_until

