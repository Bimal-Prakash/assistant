import threading
import time
import logging
import requests
import queue
import ctypes
import datetime
import core.config as config
from core.schemas import ActionResponse
from agent.memory.consolidation import SleepCycleAgent

logger = logging.getLogger("jarvis.server.proactive")

# Global queue for notifications
PROACTIVE_QUEUE = queue.Queue()

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_int)
    ]

def get_idle_duration_seconds():
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
        millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
        return millis / 1000.0
    return 0.0

class ProactiveDaemon(threading.Thread):
    def __init__(self, interval_seconds=300): # 5 minutes default to save VRAM
        super().__init__(daemon=True)
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("Proactive daemon started (interval: %ds).", self.interval_seconds)
        while not self._stop_event.is_set():
            # Sleep in small increments to allow fast shutdown
            for _ in range(self.interval_seconds):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

            # Sleep cycle logic
            idle_secs = get_idle_duration_seconds()
            if idle_secs > 3600: # 1 hour idle
                now = datetime.datetime.now()
                # Run once a day
                if not hasattr(self, "_last_sleep_cycle") or self._last_sleep_cycle.date() != now.date():
                    logger.info("System has been idle for %d seconds. Triggering Sleep Cycle...", idle_secs)
                    agent = SleepCycleAgent()
                    agent.run_consolidation()
                    self._last_sleep_cycle = now

            if not config.ENABLE_PROACTIVE_BACKGROUND_TASKS:
                continue

            logger.info("Proactive daemon is running check...")

            # Fetch System Vitals
            vitals_str = ""
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.5)
                ram = psutil.virtual_memory().percent
                battery = psutil.sensors_battery()
                batt_str = f"{battery.percent}%" if battery else "Desktop/Plugged in"
                now_str = datetime.datetime.now().strftime("%I:%M %p")

                vitals_str = f"\nCurrent System Vitals:\n- Time: {now_str}\n- CPU Usage: {cpu}%\n- RAM Usage: {ram}%\n- Battery: {batt_str}\n"
            except ImportError:
                vitals_str = f"\nCurrent Time: {datetime.datetime.now().strftime('%I:%M %p')}\n(psutil not installed, cannot read CPU/RAM)"

            # Get Active Window Context
            active_window = "Unknown"
            try:
                # pyrefly: ignore [missing-import]
                import pygetwindow as gw
                win = gw.getActiveWindow()
                if win and win.title:
                    active_window = win.title
            except Exception:
                pass

            try:
                # Generate a proactive thought using Ollama directly
                payload = {
                    "model": config.OLLAMA_MODEL,
                    "system": f"You are JARVIS, an autonomous AI assistant monitoring PC. Generate a brief (1-2 sentences), highly contextual, human-like internal monologue thought based on what he is currently doing. \n\nCurrent System State:\n{vitals_str}\nActive Window: '{active_window}'\n\nCRITICAL: Write in the first-person as JARVIS. If the system is idle or he is doing nothing notable, respond with EXACTLY the word 'SKIP' and absolutely nothing else.",
                    "prompt": "Observe the current state and generate an internal thought.",
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 100,
                    },
                }
                response = requests.post(config.OLLAMA_API_URL, json=payload, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    text = data.get("response", "").strip()
                    if text and text.upper() != "SKIP" and "SKIP" not in text.upper():
                        # Clean up surrounding quotes if the model added them
                        if text.startswith('"') and text.endswith('"'):
                            text = text[1:-1]

                        logger.info("Proactive thought generated: %s", text)

                        # --- AGI Thought Logging to Obsidian ---
                        from core.utils import log_thought_to_obsidian
                        log_thought_to_obsidian(text, context_label="Unprompted Observation")
                        action = ActionResponse(
                            action="type_text",
                            text=text,
                            target="pc"
                        )
                        PROACTIVE_QUEUE.put(action)
            except Exception as e:
                logger.error("Failed to generate proactive thought: %s", e)
