
from client.config import *

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class UIUpdaterMixin:
            def _update_hud(self, heard: str = "", intent: str = "", action: str = "") -> None:
                try:
                    if self.hud:
                        self.hud.update(heard=heard, intent=intent, action=action)
                except Exception:
                    pass

