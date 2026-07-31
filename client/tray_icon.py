import threading
# pyrefly: ignore [missing-import]
import pystray
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw
import requests

class JarvisTrayIcon(threading.Thread):
    def __init__(self, backend_url: str, on_manual_trigger, on_exit):
        super().__init__(daemon=True)
        self.backend_url = backend_url
        self.on_manual_trigger = on_manual_trigger
        self.on_exit = on_exit
        self.proactive_enabled = False
        self.icon = None

    def create_image(self):
        # Create a basic J icon with a transparent background
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=(0, 120, 215))
        draw.text((28, 24), "J", fill=(255, 255, 255))
        return image

    def on_trigger(self, icon, item):
        if self.on_manual_trigger:
            self.on_manual_trigger()

    def toggle_proactive(self, icon, item):
        self.proactive_enabled = not self.proactive_enabled
        try:
            requests.post(f"{self.backend_url}/config/proactive", json={"enabled": self.proactive_enabled})
        except Exception as e:
            print(f"Error toggling proactive mode: {e}")

    def on_quit(self, icon, item):
        if self.icon:
            self.icon.stop()
        if self.on_exit:
            self.on_exit()

    def run(self):
        print("[TrayIcon] Starting background thread...")
        # Fetch initial state
        try:
            r = requests.get(f"{self.backend_url}/status", timeout=2)
            if r.status_code == 200:
                self.proactive_enabled = r.json().get("proactive_enabled", False)
        except Exception:
            pass

        menu = pystray.Menu(
            pystray.MenuItem("Listen Now", self.on_trigger, default=True),
            pystray.MenuItem(lambda text: "Disable Proactive Mode" if self.proactive_enabled else "Enable Proactive Mode", self.toggle_proactive),
            pystray.MenuItem("Exit", self.on_quit)
        )

        print("[TrayIcon] Creating icon object...")
        self.icon = pystray.Icon("Jarvis", self.create_image(), "Jarvis Assistant", menu)
        # Note: pystray's icon.run() is a blocking call
        print("[TrayIcon] Running icon message loop...")
        try:
            self.icon.run()
        except Exception as e:
            print(f"[TrayIcon] Error running icon: {e}")

    def stop(self):
        if self.icon:
            self.icon.stop()
