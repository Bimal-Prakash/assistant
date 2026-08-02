import sys
import os
import subprocess
import threading
import winreg
import ctypes
import asyncio
try:
    # pyrefly: ignore [missing-import]
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False
# pyrefly: ignore [missing-import]
from PyQt6.QtWidgets import QApplication, QWidget
# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QPropertyAnimation, QRect, QPoint, QEasingCurve
# pyrefly: ignore [missing-import]
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFontMetrics, QFont, QCursor, QPolygon
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [UI Wrapper] %(message)s")
log = logging.getLogger("ui_wrapper")

class DynamicIsland(QWidget):
    state_changed_signal = pyqtSignal(str)
    update_media_signal = pyqtSignal(str, str, str, bool, float, float, object)

    def __init__(self):
        super().__init__()
        # Window settings for transparent, frameless, always-on-top pill
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.current_state = "idle"
        
        # Dimensions
        self.idle_width = 120
        self.active_width = 220
        self.height_ = 40
        self.display_text = ""
        self.is_playing = False
        self.media_app_name = ""
        self.media_title = ""
        self.media_artist = ""
        self.media_pos = 0.0
        self.media_end = 0.0
        
        self.update_media_signal.connect(self.on_media_update)
        if WINSDK_AVAILABLE:
            threading.Thread(target=self.start_media_poller, daemon=True).start()
        
        self.accent_color = QColor(0, 255, 204) # fallback cyan
        self.update_accent_color()
        
        # Initial geometry (centered horizontally, top of screen)
        screen = QApplication.primaryScreen().geometry()
        self.center_x = screen.width() // 2
        self.y_pos = 10
        self.setGeometry(self.center_x - (self.idle_width // 2), self.y_pos, self.idle_width, self.height_)

        # Animation state for waves/spinner
        self.anim_step = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50) # 20fps for drawing updates
        
        self.state_changed_signal.connect(self.animate_state_change)
        
        # Start backend
        self.backend_process = None
        self.start_backend()

    def update_accent_color(self):
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\DWM")
            value, _ = winreg.QueryValueEx(key, "ColorizationColor")
            r = (value >> 16) & 0xFF
            g = (value >> 8) & 0xFF
            b = value & 0xFF
            self.accent_color = QColor(r, g, b)
        except Exception:
            pass

    def on_media_update(self, app, title, artist, playing, pos, end, thumb_bytes):
        import time
        self.media_app_name = app
        self.media_title = title
        self.media_artist = artist
        
        # Debounce the playing state for 1.5 seconds after a manual toggle
        if hasattr(self, 'last_toggle_time') and time.time() - self.last_toggle_time < 1.5:
            playing = self.is_playing
            
        # Debounce the media position for 3.0 seconds after seeking to prevent rubber-banding
        if hasattr(self, 'last_seek_time') and time.time() - self.last_seek_time < 3.0:
            pos = getattr(self, 'seek_target_pos', self.media_pos)
        else:
            # Sync with real time by using time.time() extrapolation
            if not hasattr(self, 'media_pos'):
                self.media_pos = pos
            elif abs(self.media_pos - pos) > 3.0:
                self.media_pos = pos # Major jump (e.g. user skipped track)
            elif pos > self.media_pos:
                self.media_pos = pos # Sync if backend is slightly ahead
            else:
                pos = self.media_pos # Ignore stale backend data that would snap us backward
            
        self.is_playing = playing
        if not (hasattr(self, 'last_seek_time') and time.time() - self.last_seek_time < 3.0):
            self.media_pos = pos
        self.media_end = end
        
        if not hasattr(self, 'media_thumb_bytes'):
            self.media_thumb_bytes = b""
        if thumb_bytes and thumb_bytes != self.media_thumb_bytes:
            self.media_thumb_bytes = thumb_bytes
            # pyrefly: ignore [missing-import]
            from PyQt6.QtGui import QImage, QPixmap
            img = QImage.fromData(thumb_bytes)
            self.media_thumb_pixmap = QPixmap.fromImage(img)
        elif not thumb_bytes:
            self.media_thumb_bytes = b""
            self.media_thumb_pixmap = None

        if self.current_state == "mini_player":
            self.update()

    def start_media_poller(self):
        asyncio.run(self.poll_media())
        
    async def poll_media(self):
        current_title_for_thumb = ""
        current_thumbnail_bytes = b""
        try:
            import ctypes
            try:
                ctypes.windll.combase.RoInitialize(1) # RO_INIT_MULTITHREADED
            except Exception:
                try:
                    ctypes.windll.ole32.CoInitialize(None)
                except Exception:
                    pass
                    
            manager = await MediaManager.request_async()
            while True:
                try:
                    session = manager.get_current_session()
                    # Fallback: if get_current_session is None, try grabbing the first available session
                    if not session:
                        sessions = manager.get_sessions()
                        if sessions and len(sessions) > 0:
                            session = sessions[0]
                            
                    if session:
                        info = await session.try_get_media_properties_async()
                        app_id = session.source_app_user_model_id
                        
                        # Clean up common App IDs (e.g. Spotify.exe -> Spotify)
                        app_name = app_id.split("!")[-1].split(".exe")[0].capitalize()
                        
                        playback_info = session.get_playback_info()
                        playing = (playback_info.playback_status == 4) if playback_info else False
                        
                        timeline = session.get_timeline_properties()
                        pos = timeline.position.total_seconds() if timeline else 0.0
                        end = timeline.end_time.total_seconds() if timeline else 0.0
                        
                        try:
                            if info.title != current_title_for_thumb:
                                current_title_for_thumb = info.title
                                if info.thumbnail:
                                    # pyrefly: ignore [missing-import]
                                    from winsdk.windows.storage.streams import DataReader, Buffer
                                    stream = await info.thumbnail.open_read_async()
                                    buffer = Buffer(stream.size)
                                    await stream.read_async(buffer, stream.size, 0)
                                    reader = DataReader.from_buffer(buffer)
                                    current_thumbnail_bytes = bytes(reader.read_buffer(buffer.length))
                                else:
                                    current_thumbnail_bytes = b""
                        except Exception as thumb_e:
                            current_thumbnail_bytes = b""
                        self.update_media_signal.emit(app_name, info.title, info.artist, playing, pos, end, current_thumbnail_bytes)
                    else:
                        self.update_media_signal.emit("", "", "", False, 0.0, 0.0, b"")
                        
                except Exception as loop_e:
                    import traceback
                    with open("debug_log.txt", "a") as f:
                        f.write(f"Loop error: {loop_e}\n{traceback.format_exc()}\n")
                    print(f"Loop error: {loop_e}")
                    
                await asyncio.sleep(1.0)
        except Exception as e:
            import traceback
            with open("debug_log.txt", "a") as f:
                f.write(f"Fatal error: {e}\n{traceback.format_exc()}\n")
            print(f"Media poller error: {e}", flush=True)
            log.error(f"Media poller error: {e}")

    def update_animation(self):
        import time
        self.anim_step += 1
        if self.anim_step % 50 == 0:
            self.update_accent_color()
            
        # Real-time progress bar extrapolation using time delta
        now = time.time()
        if getattr(self, 'is_playing', False) and getattr(self, 'media_end', 0) > 0 and not getattr(self, 'dragging_progress', False):
            if hasattr(self, 'last_anim_time'):
                dt = now - self.last_anim_time
                self.media_pos = min(self.media_end, getattr(self, 'media_pos', 0) + dt)
        self.last_anim_time = now
            
        # Global click detection to dismiss displaying/mini_player states
        if self.current_state in ["displaying", "mini_player"]:
            import ctypes
            # VK_LBUTTON is 0x01
            state = ctypes.windll.user32.GetAsyncKeyState(0x01)
            if state & 0x8000:
                # Left mouse pressed. Check if it's outside our window.
                cursor_pos = QCursor.pos()
                if not self.geometry().contains(cursor_pos):
                    self.state_changed_signal.emit("idle")
                    
        self.update() # triggers paintEvent

    def animate_state_change(self, new_state):
        if new_state == "ready":
            self.show()
            new_state = "idle"

        display_text = ""
        if new_state.startswith("displaying:"):
            display_text = new_state.split(":", 1)[1]
            new_state = "displaying"
            
        if new_state == "idle_requested":
            if self.current_state in ["displaying", "mini_player"]:
                return
            new_state = "idle"

        if new_state != "displaying" and hasattr(self, 'display_timer'):
            self.display_timer.stop()

        if self.current_state == new_state and self.display_text == display_text:
            return
        
        self.current_state = new_state
        self.display_text = display_text
        
        if new_state == "displaying":
            if not hasattr(self, 'display_timer'):
                self.display_timer = QTimer(self)
                self.display_timer.setSingleShot(True)
                self.display_timer.timeout.connect(lambda: self.state_changed_signal.emit("idle"))
            duration = 5000 + (len(display_text) * 50)
            self.display_timer.start(duration)
        
        target_width = self.idle_width
        target_height = 40
        
        if new_state in ["listening", "processing"]:
            target_width = self.active_width
        elif new_state == "mini_player":
            target_width = 360
            target_height = 160
        elif new_state == "displaying":
            font = QFont('Segoe UI', 11)
            fm = QFontMetrics(font)
            rect = fm.boundingRect(QRect(0, 0, 400, 1000), Qt.TextFlag.TextWordWrap, self.display_text)
            target_width = min(rect.width() + 60, 460)
            target_height = rect.height() + 40
        
        # Ensure target geometry stays inside screen bounds
        screen_geo = self.screen().availableGeometry()
        target_x = max(screen_geo.left(), min(self.center_x - (target_width // 2), screen_geo.right() - target_width + 1))
        target_y = max(screen_geo.top(), min(self.y_pos, screen_geo.bottom() - target_height + 1))
        
        # Animate window geometry smoothly
        self.geom_anim = QPropertyAnimation(self, b"geometry")
        self.geom_anim.setDuration(400)
        self.geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.geom_anim.setStartValue(self.geometry())
        self.geom_anim.setEndValue(QRect(target_x, target_y, target_width, target_height))
        self.geom_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Liquid glass background (0 VRAM blur alternative)
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(255, 255, 255, 40))   # Top highlight
        gradient.setColorAt(0.1, QColor(20, 20, 25, 180))    # Dark body
        gradient.setColorAt(0.9, QColor(5, 5, 10, 210))      # Darker bottom
        gradient.setColorAt(1.0, QColor(255, 255, 255, 20))   # Bottom reflection
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))    # Glass border
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 19, 19)

        # Draw content based on state
        if self.current_state == "idle":
            # Tiny dot, using the wallpaper accent color
            painter.setBrush(QBrush(self.accent_color))
            painter.setPen(Qt.PenStyle.NoPen)
            center = rect.center()
            painter.drawEllipse(center, 4, 4)
            
        elif self.current_state == "listening":
            # Audio waves colored by wallpaper accent
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self.accent_color))
            wave_count = 6
            wave_width = 4
            spacing = 8
            total_width = (wave_count * wave_width) + ((wave_count - 1) * spacing)
            start_x = rect.center().x() - (total_width // 2)
            
            import math
            for i in range(wave_count):
                # Calculate wave height based on time (anim_step) and position
                h = 4 + 10 * abs(math.sin((self.anim_step * 0.1) + i))
                x = start_x + (i * (wave_width + spacing))
                y = rect.center().y() - (h / 2)
                painter.drawRoundedRect(int(x), int(y), wave_width, int(h), 2, 2)
                
        elif self.current_state == "processing":
            # Processing waves colored by wallpaper accent
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self.accent_color))
            wave_count = 6
            wave_width = 4
            spacing = 8
            total_width = (wave_count * wave_width) + ((wave_count - 1) * spacing)
            start_x = rect.center().x() - (total_width // 2)
            
            import math
            for i in range(wave_count):
                # Faster, rippling wave effect for processing
                h = 4 + 10 * abs(math.cos((self.anim_step * 0.15) + (i * 0.8)))
                x = start_x + (i * (wave_width + spacing))
                y = 20 - (h / 2) # Since processing height is 40 always initially
                painter.drawRoundedRect(int(x), int(y), wave_width, int(h), 2, 2)
                
        elif self.current_state == "displaying":
            # Display text
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont('Segoe UI', 11))
            text_rect = rect.adjusted(30, 20, -30, -20)
            painter.drawText(text_rect, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, self.display_text)
            
        elif self.current_state == "mini_player":
            painter.setPen(QColor(255, 255, 255))
            
            # --- TOP ROW ---
            # Album Art Placeholder / Image
            art_x, art_y, art_size = 20, 20, 50
            if hasattr(self, 'media_thumb_pixmap') and self.media_thumb_pixmap:
                brush = QBrush(self.media_thumb_pixmap.scaled(art_size, art_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
                painter.setBrush(brush)
            else:
                painter.setBrush(QColor(200, 200, 200, 200)) # Light gray placeholder
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(art_x, art_y, art_size, art_size, 12, 12)
            
            # Title & Artist Text
            text_x = art_x + art_size + 15
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
            
            raw_title = self.media_title.strip() if self.media_title else ""
            title = raw_title if raw_title and raw_title != "Live Activity" else self.media_app_name
            if not title:
                title = "Media Player"
                
            raw_artist = self.media_artist.strip() if self.media_artist else ""
            if not raw_artist or raw_artist.lower() == "unknown artist":
                painter.drawText(QRect(text_x, 32, 200, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
            else:
                painter.drawText(QRect(text_x, 22, 200, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
                painter.setPen(QColor(180, 180, 180))
                painter.setFont(QFont('Segoe UI', 10))
                painter.drawText(QRect(text_x, 42, 200, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, raw_artist)
            
            # Visualizer (Top Right)
            if self.is_playing:
                painter.setBrush(QColor(150, 150, 150))
                import math
                vis_x = rect.width() - 40
                for i in range(4):
                    h = 4 + 8 * abs(math.cos((self.anim_step * 0.15) + (i * 0.8)))
                    y = 35 - (h / 2)
                    painter.drawRoundedRect(int(vis_x + (i*6)), int(y), 3, int(h), 1, 1)

            # --- MIDDLE ROW (Progress Bar) ---
            bar_y = 80
            bar_w = rect.width() - 40
            
            def fmt(s): return f"{int(s//60)}:{int(s%60):02d}"
            t_curr = fmt(self.media_pos)
            rem = max(0, self.media_end - self.media_pos)
            t_rem = f"-{fmt(rem)}" if rem > 0 else "0:00"
            
            painter.setFont(QFont('Segoe UI', 8))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(QRect(20, bar_y - 8, 40, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t_curr)
            painter.drawText(QRect(rect.width() - 60, bar_y - 8, 40, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, t_rem)
            
            line_x = 55
            line_w = bar_w - 70
            painter.setBrush(QColor(80, 80, 80))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(line_x, bar_y - 4, line_w, 12, 6, 6)
            
            if self.media_end > 0:
                if getattr(self, 'dragging_progress', False) and hasattr(self, 'drag_pct'):
                    pct = self.drag_pct
                else:
                    pct = min(1.0, max(0.0, self.media_pos / self.media_end))
                fill_w = int(line_w * pct)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawRoundedRect(line_x, bar_y - 4, fill_w, 12, 6, 6)

            # --- BOTTOM ROW (Controls) ---
            button_y = 125
            center_x = rect.width() // 2
            # Set up pen for smooth, bold corners
            pen = QPen(QColor(255, 255, 255))
            pen.setWidth(3)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255))
            
            # Prev
            px = center_x - 95
            py = button_y - 15
            painter.drawPolygon(QPolygon([QPoint(px - 16, py + 15), QPoint(px, py), QPoint(px, py + 30)]))
            painter.drawPolygon(QPolygon([QPoint(px + 2, py + 15), QPoint(px + 18, py), QPoint(px + 18, py + 30)]))
            
            # Play/Pause
            px = center_x
            py = button_y - 15
            if self.is_playing:
                # Show Pause icon (||) when playing
                painter.drawRoundedRect(px - 14, py, 10, 30, 2, 2)
                painter.drawRoundedRect(px + 4, py, 10, 30, 2, 2)
            else:
                # Show Play icon (|>) when paused
                painter.drawPolygon(QPolygon([QPoint(px - 12, py), QPoint(px + 18, py + 15), QPoint(px - 12, py + 30)]))
                
            # Next
            px = center_x + 100
            py = button_y - 15
            painter.drawPolygon(QPolygon([QPoint(px - 18, py), QPoint(px - 2, py + 15), QPoint(px - 18, py + 30)]))
            painter.drawPolygon(QPolygon([QPoint(px, py), QPoint(px + 16, py + 15), QPoint(px, py + 30)]))

    def start_backend(self):
        def monitor():
            python_exe = sys.executable
            backend_script = os.path.join(os.path.dirname(__file__), "run.py")
            log.info(f"Starting backend: {python_exe} {backend_script}")
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            self.backend_process = subprocess.Popen(
                [python_exe, backend_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )

            while True:
                line = self.backend_process.stdout.readline()
                if not line and self.backend_process.poll() is not None:
                    break
                
                if line:
                    line_stripped = line.strip()
                    print(f"[Backend] {line_stripped}", flush=True)

                    if "[UI_SIGNAL] READY" in line_stripped:
                        self.state_changed_signal.emit("ready")
                    elif "[UI_SIGNAL] WAKE_WORD_DETECTED" in line_stripped:
                        self.state_changed_signal.emit("listening")
                    elif "[UI_SIGNAL] RESPONSE:" in line_stripped:
                        text = line_stripped.split("[UI_SIGNAL] RESPONSE:", 1)[1].strip()
                        self.state_changed_signal.emit(f"displaying:{text}")
                    elif "[UI_SIGNAL] PROCESSING" in line_stripped or "Heard:" in line_stripped:
                        self.state_changed_signal.emit("processing")
                    elif "[UI_SIGNAL] IDLE" in line_stripped or "Microphone listener is ready" in line_stripped:
                        self.state_changed_signal.emit("idle_requested")
                        
        threading.Thread(target=monitor, daemon=True).start()

    def closeEvent(self, event):
        if self.backend_process:
            self.backend_process.terminate()
        super().closeEvent(event)

    def seek_media(self, pct):
        def _seek():
            try:
                import asyncio
                # pyrefly: ignore [missing-import]
                from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
                async def _do_seek():
                    manager = await MediaManager.request_async()
                    session = manager.get_current_session()
                    if session:
                        target = int(pct * self.media_end * 10_000_000)
                        await session.try_change_playback_position_async(target)
                asyncio.run(_do_seek())
            except Exception:
                pass
        threading.Thread(target=_seek, daemon=True).start()

    def mousePressEvent(self, event):
        if self.current_state == "idle":
            self.state_changed_signal.emit("mini_player")
        elif self.current_state == "mini_player":
            x = event.position().x()
            y = event.position().y()
            center_x = self.width() // 2
            
            # Layout Constants
            PROG_Y_MIN, PROG_Y_MAX = 74, 94
            BTN_Y_MIN, BTN_Y_MAX = 100, 150
            PREV_X_MIN, PREV_X_MAX = center_x - 120, center_x - 70
            PLAY_X_MIN, PLAY_X_MAX = center_x - 20, center_x + 25
            NEXT_X_MIN, NEXT_X_MAX = center_x + 75, center_x + 125
            FOCUS_Y_MIN, FOCUS_Y_MAX = 20, 80
            FOCUS_X_MIN, FOCUS_X_MAX = 20, 300
            
            # Progress Bar Click
            if PROG_Y_MIN <= y <= PROG_Y_MAX and getattr(self, 'media_end', 0) > 0:
                bar_w = self.width() - 110 # 55 padding on each side
                click_x = x - 55
                pct = max(0.0, min(1.0, click_x / bar_w))
                self.drag_pct = pct
                self.dragging_progress = True
                return
                
            # Check button areas
            if BTN_Y_MIN <= y <= BTN_Y_MAX:
                # VK_MEDIA_NEXT_TRACK = 0xB0, PREV = 0xB1, PLAY_PAUSE = 0xB3
                if PREV_X_MIN <= x <= PREV_X_MAX:
                    ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0) # Prev
                    return
                elif PLAY_X_MIN <= x <= PLAY_X_MAX:
                    import time
                    self.last_toggle_time = time.time()
                    ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0) # Play/Pause
                    self.is_playing = not self.is_playing  # Toggle UI state
                    self.update() # Force repaint to show new icon immediately
                    return
                elif NEXT_X_MIN <= x <= NEXT_X_MAX:
                    ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0) # Next
                    return
            # Title & Artist & Image click area (Focus App)
            if FOCUS_Y_MIN <= y <= FOCUS_Y_MAX and FOCUS_X_MIN <= x <= FOCUS_X_MAX and self.media_app_name:
                import threading
                def focus_app():
                    try:
                        # pyrefly: ignore [missing-import]
                        import pygetwindow as gw
                        import ctypes
                        app_query = self.media_app_name.lower()
                        
                        target_win = None
                        for win in gw.getAllWindows():
                            if win.title and win.title != "Program Manager":
                                if app_query in win.title.lower():
                                    target_win = win
                                    break
                                # Special fallback for browsers
                                if app_query == "chrome" and "chrome" in win.title.lower():
                                    target_win = win
                                    break
                                if app_query == "msedge" and "edge" in win.title.lower():
                                    target_win = win
                                    break
                        
                        if target_win:
                            try:
                                # Send Alt to drop any menu/focus lock
                                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
                                if target_win.isMinimized:
                                    target_win.restore()
                                ctypes.windll.user32.ShowWindow(target_win._hWnd, 9)
                                ctypes.windll.user32.SetForegroundWindow(target_win._hWnd)
                            except Exception as e:
                                pass
                    except Exception as e:
                        print(f"Focus error: {e}")
                threading.Thread(target=focus_app, daemon=True).start()
                return
            
            # Clicked anywhere else inside the widget -> dismiss
            self.state_changed_signal.emit("idle")
            return
        
        # Allow dragging the widget if you click and hold it
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if getattr(self, 'dragging_progress', False) and self.current_state == "mini_player" and getattr(self, 'media_end', 0) > 0:
            x = event.position().x()
            bar_w = self.width() - 110
            click_x = x - 55
            self.drag_pct = max(0.0, min(1.0, click_x / bar_w))
            self.update()
            return

        if hasattr(self, 'oldPos'):
            delta = QPoint(event.globalPosition().toPoint() - getattr(self, 'oldPos', event.globalPosition().toPoint()))
            
            new_x = self.x() + delta.x()
            new_y = self.y() + delta.y()
            
            # Keep widget within the screen bounds (respecting the taskbar)
            screen_geo = self.screen().availableGeometry()
            new_x = max(screen_geo.left(), min(new_x, screen_geo.right() - self.width() + 1))
            new_y = max(screen_geo.top(), min(new_y, screen_geo.bottom() - self.height() + 1))
            
            self.move(new_x, new_y)
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if getattr(self, 'dragging_progress', False):
            if hasattr(self, 'drag_pct'):
                import time
                self.last_seek_time = time.time()
                self.seek_target_pos = self.drag_pct * getattr(self, 'media_end', 0)
                self.media_pos = self.seek_target_pos
                self.seek_media(self.drag_pct)
            self.dragging_progress = False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    island = DynamicIsland()
    # We will show the island when the READY signal is received
    sys.exit(app.exec())
