import time

from client.config import *

snapshot_download = WhisperModel = Model = KaldiRecognizer = SetLogLevel = pvrecorder = None

class WindowMixin:
            def _activate_wake_window(self) -> None:
                self.wake_active_until = time.time() + WAKE_ACTIVE_SECONDS

            def _wake_window_active(self) -> bool:
                return time.time() < self.wake_active_until

