import queue
import threading
from typing import Optional, Dict

try:
    import tkinter as tk  # type: ignore
except Exception:
    tk = None

class StatusHud:
    def __init__(self) -> None:
        self.enabled = False
        self._closed = False
        self._queue: "queue.Queue[Dict[str, str]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        if tk is None:
            return

        self._thread = threading.Thread(target=self._run_ui, daemon=True)
        self._thread.start()
        self.enabled = True

    def _run_ui(self) -> None:
        if tk is None:
            return

        root = tk.Tk()
        root.title("Jarvis HUD")
        root.geometry("420x130+20+20")
        root.attributes("-topmost", True)
        root.configure(bg="#111111")

        transcript_var = tk.StringVar(value="Heard: ...")
        intent_var = tk.StringVar(value="Intent: ...")
        action_var = tk.StringVar(value="Action: ...")

        for var in (transcript_var, intent_var, action_var):
            label = tk.Label(root, textvariable=var, anchor="w", justify="left", fg="#f0f0f0", bg="#111111", font=("Consolas", 10))
            label.pack(fill="x", padx=10, pady=3)

        def poll() -> None:
            while True:
                try:
                    payload = self._queue.get_nowait()
                except queue.Empty:
                    break
                if payload.get("__cmd") == "shutdown":
                    root.quit()
                    return
                transcript_var.set(f"Heard: {payload.get('heard', '...')}")
                intent_var.set(f"Intent: {payload.get('intent', '...')}")
                action_var.set(f"Action: {payload.get('action', '...')}")
            root.after(120, poll)

        poll()
        root.mainloop()
        try:
            root.destroy()
        except Exception:
            pass

    def update(self, heard: str = "", intent: str = "", action: str = "") -> None:
        if not self.enabled or self._closed:
            return
        self._queue.put({"heard": heard, "intent": intent, "action": action})

    def close(self) -> None:
        if not self.enabled or self._closed:
            return
        self._closed = True
        try:
            self._queue.put({"__cmd": "shutdown"})
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.enabled = False
