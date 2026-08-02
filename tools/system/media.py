import os
import time
try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

PREVIOUS_TRACK_PRESS_COUNT = max(2, int(os.getenv("JARVIS_PREVIOUS_TRACK_PRESS_COUNT", "2")))
PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS = float(os.getenv("JARVIS_PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS", "0.18"))

def media_control(command: str) -> str:
    if pyautogui is None:
        raise RuntimeError("pyautogui is not installed")

    cmd = command.lower().strip()
    if cmd in {"play", "pause", "play_pause", "toggle"}:
        pyautogui.press("playpause")
        return "Toggling play/pause"
    if cmd in {"next", "next_track"}:
        pyautogui.press("nexttrack")
        return "Skipping to next track"
    if cmd in {"previous", "prev", "previous_track"}:
        for idx in range(PREVIOUS_TRACK_PRESS_COUNT):
            pyautogui.press("prevtrack")
            if idx < PREVIOUS_TRACK_PRESS_COUNT - 1:
                time.sleep(max(0.05, PREVIOUS_TRACK_PRESS_INTERVAL_SECONDS))
        return "Going to previous track"
    raise ValueError("Unsupported media command")

def get_current_media_info() -> str:
    import asyncio
    
    async def _get_info():
        try:
            from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        except ImportError:
            return "Error: winsdk is not installed."
            
        try:
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            if not manager:
                return "Error: Could not access Windows Media Controls."
                
            session = manager.get_current_session()
            
            if session:
                app_id = session.source_app_user_model_id or ""
                # If the assistant's own TTS overtook the media session, try to find the real one
                if "python" in app_id.lower() or "windowsterminal" in app_id.lower() or "code" in app_id.lower():
                    sessions = manager.get_sessions()
                    valid_sessions = [s for s in sessions if s.source_app_user_model_id and not any(x in s.source_app_user_model_id.lower() for x in ["python", "windowsterminal", "code"])]
                    if valid_sessions:
                        # Prioritize playing media
                        playing = [s for s in valid_sessions if s.get_playback_info().playback_status == 4]
                        session = playing[0] if playing else valid_sessions[0]

            if not session:
                return "There is no media currently playing or paused."
                
            app_id = session.source_app_user_model_id
            info = await session.try_get_media_properties_async()
            title = info.title if info.title else "Unknown Title"
            artist = info.artist if info.artist else "Unknown Artist"
            
            playback_info = session.get_playback_info()
            
            # 4 is Playing, 5 is Paused
            status_map = {0: "Closed", 1: "Opened", 2: "Changing", 3: "Stopped", 4: "Playing", 5: "Paused"}
            status = status_map.get(playback_info.playback_status, str(playback_info.playback_status))
            
            return f"Currently {status.lower()}: '{title}' by {artist} (App: {app_id})"
        except Exception as e:
            return f"Error retrieving media info: {e}"

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                return pool.submit(asyncio.run, _get_info()).result()
    except RuntimeError:
        pass
        
    return asyncio.run(_get_info())
