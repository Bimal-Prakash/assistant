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
import webbrowser
import winreg
from urllib.parse import quote_plus
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
import difflib

from client.config import *
from client.ui import StatusHud

class StartupMixin:
            def install_startup(self) -> str:
                startup_dir = os.path.join(
                    os.environ.get("APPDATA", ""),
                    r"Microsoft\Windows\Start Menu\Programs\Startup",
                )
                if not startup_dir or not os.path.isdir(startup_dir):
                    return "Could not find Windows Startup folder."
        
                project_dir = os.path.dirname(os.path.abspath(__file__))
                python_exe = os.path.join(project_dir, ".venv", "Scripts", "pythonw.exe")
                if not os.path.isfile(python_exe):
                    python_exe = "pythonw"
        
                backend_script = os.path.join(project_dir, "main.py")
                assistant_script = os.path.join(project_dir, "laptop_assistant.py")
                vbs_path = os.path.join(startup_dir, "jarvis_startup.vbs")
                legacy_bat_path = os.path.join(startup_dir, "jarvis_startup.bat")
        
                script = (
                    'Set WshShell = CreateObject("WScript.Shell")\n'
                    f'WshShell.CurrentDirectory = "{project_dir}"\n'
                    f'WshShell.Run chr(34) & "{python_exe}" & chr(34) & " " & chr(34) & "{backend_script}" & chr(34), 0, False\n'
                    "WScript.Sleep 4000\n"
                    f'WshShell.Run chr(34) & "{python_exe}" & chr(34) & " " & chr(34) & "{assistant_script}" & chr(34) & " --background", 0, False\n'
                )
        
                with open(vbs_path, "w", encoding="utf-8") as f:
                    f.write(script)
        
                if os.path.isfile(legacy_bat_path):
                    os.remove(legacy_bat_path)
        
                return f"Startup installed: {vbs_path}"

            def uninstall_startup(self) -> str:
                startup_dir = os.path.join(
                    os.environ.get("APPDATA", ""),
                    r"Microsoft\Windows\Start Menu\Programs\Startup",
                )
                bat_path = os.path.join(startup_dir, "jarvis_startup.bat")
                vbs_path = os.path.join(startup_dir, "jarvis_startup.vbs")
        
                removed_any = False
                for launcher_path in (bat_path, vbs_path):
                    if os.path.isfile(launcher_path):
                        os.remove(launcher_path)
                        removed_any = True
        
                return "Startup removed." if removed_any else "Startup entry not found."

