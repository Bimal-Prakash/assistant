import logging
import re
from core.schemas import ActionResponse
from server.parser.normalizer import _normalize_action

logger = logging.getLogger("jarvis.server.api.processor.core")

class CoreProcessorMixin:
    def process(self) -> ActionResponse:
        logger.info("Command after wake-word strip: %s", self.cleaned)

        # Check for pending confirmations first (stateful)
        response = self.handle_pending_confirmations()
        if response:
            return response

        # Check for media controls (broad match to prevent LLM hallucination)
        cleaned_lower = self.cleaned.lower().strip()
        
        play_pause_phrases = ["play", "pause", "play pause", "resume", "stop", "stop music", "pause music", "play music", "pause the music", "play the music", "stop the music", "pause it", "play it", "stop it"]
        next_phrases = ["next", "next track", "skip", "next song", "skip song"]
        prev_phrases = ["previous", "previous track", "go back", "last song", "previous song"]
        volume_up_phrases = ["volume up", "increase volume", "louder"]
        volume_down_phrases = ["volume down", "decrease volume", "quieter"]
        volume_mute_phrases = ["mute", "mute volume"]
        lock_pc_phrases = ["lock pc", "lock computer", "lock screen"]
        take_screenshot_phrases = ["take a screenshot", "screenshot", "print screen"]

        if cleaned_lower in play_pause_phrases:
            return self._finalize(ActionResponse(action="press_shortcut", shortcut="space", target="pc"))
        elif cleaned_lower in next_phrases:
            return self._finalize(ActionResponse(action="media_control", state="next", target="pc"))
        elif cleaned_lower in prev_phrases:
            return self._finalize(ActionResponse(action="media_control", state="previous", target="pc"))
        elif cleaned_lower in volume_up_phrases:
            return self._finalize(ActionResponse(action="volume_control", level="up", target="pc"))
        elif cleaned_lower in volume_down_phrases:
            return self._finalize(ActionResponse(action="volume_control", level="down", target="pc"))
        elif cleaned_lower in volume_mute_phrases:
            return self._finalize(ActionResponse(action="volume_control", level="mute", target="pc"))
        elif cleaned_lower in lock_pc_phrases:
            return self._finalize(ActionResponse(action="lock_pc", target="pc"))
        elif cleaned_lower in take_screenshot_phrases:
            return self._finalize(ActionResponse(action="take_screenshot", target="pc"))

        # Everything else goes through the agent
        response = self.handle_llm_generation()
        if response:
            return response
        
        # Fallback
        return self._finalize(ActionResponse(action="type_text", text="Command could not be processed.", target=self.default_target))
