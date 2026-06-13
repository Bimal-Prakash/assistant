from client.config import *
from client.ui import StatusHud
from client.audio.device import AudioDeviceMixin
from client.audio.windows.stt import WindowsSTTMixin
from client.audio.stt_dispatcher import STTDispatcherMixin
from client.audio.tts import TTSMixin
from client.nlp.calibration import CalibrationMixin
from client.nlp.wake_word import WakeWordMixin
from client.nlp.gating import STTGatingMixin
from client.nlp.normalization import NormalizationMixin
from client.system.apps_core import AppManagementMixin
from client.system.agentic_core import AgenticControlMixin
from client.system.apps_spotify import SpotifyMixin
from client.system.apps_search import StartMenuSearchMixin
from client.system.apps_startup import StartupMixin
from client.core.main import MainLoopMixin
from client.core.backend import BackendMixin
from client.core.execution_actions import ActionExecutionMixin
from client.core.execution_queries import LocalQueryMixin
from client.core.execution_heuristics import HeuristicsMixin
from client.core.execution_resolver import ResolverMixin
from client.core.rules import RulesMixin
from client.core.confirmation import ConfirmationMixin
from client.core.keyboard import KeyboardMixin
from client.core.window import WindowMixin
from client.core.ui_updater import UIUpdaterMixin
from client.core.aliases import AliasesMixin

class LaptopJarvisClient(
    AudioDeviceMixin,
    WindowsSTTMixin, STTDispatcherMixin,
    TTSMixin,
    CalibrationMixin, WakeWordMixin, STTGatingMixin, NormalizationMixin,
    AppManagementMixin, AgenticControlMixin, SpotifyMixin, StartMenuSearchMixin, StartupMixin,
    MainLoopMixin, BackendMixin,
    ActionExecutionMixin, LocalQueryMixin, HeuristicsMixin, ResolverMixin,
    RulesMixin,
    ConfirmationMixin, KeyboardMixin, WindowMixin, UIUpdaterMixin, AliasesMixin
):
    pass
