from .system_info import exec_get_system_info
from .apps import exec_open_app, exec_close_app, exec_minimize_app
from .website import exec_open_website
from .web_search import exec_search_web
from .terminal import exec_run_terminal
from .volume import exec_volume_control
from .brightness import exec_brightness_control
from .power import exec_power_control
from .media import exec_media_control, exec_get_current_media_info
from .network import exec_network_control
from .mic import exec_mic_control
from .whatsapp import exec_send_whatsapp, exec_whatsapp_call
from .telegram import exec_telegram_call
from .memory import exec_remember_fact, exec_recall_fact, exec_recall_last_command, exec_semantic_search_chat_history, exec_search_memory
from .audio import exec_switch_audio_output
from .final_answer import exec_final_answer
from .vision import exec_look_at_screen, exec_vision_click
from .chatgpt import exec_ask_chatgpt_visually
from .ui_automation import exec_analyze_ui, exec_click_ui_element, exec_type_ui_element
from .file_system import exec_list_directory, exec_read_file, exec_write_file, exec_search_files
from .system_observe import exec_observe_desktop

from .agentic import (
    exec_maximize_app, exec_restore_app, exec_hide_all_windows, exec_snap_window,
    exec_read_clipboard, exec_write_clipboard, exec_press_shortcut,
    exec_check_performance, exec_lock_pc, exec_empty_recycle_bin, exec_take_screenshot,
    exec_show_notification, exec_set_timer, exec_open_folder, exec_open_file
)

__all__ = [
    "exec_get_system_info",
    "exec_open_app",
    "exec_close_app",
    "exec_minimize_app",
    "exec_open_website",
    "exec_search_web",
    "exec_volume_control",
    "exec_brightness_control",
    "exec_power_control",
    "exec_media_control",
    "exec_get_current_media_info",
    "exec_network_control",
    "exec_mic_control",
    "exec_run_terminal",
    "exec_send_whatsapp",
    "exec_whatsapp_call",
    "exec_telegram_call",
    "exec_remember_fact",
    "exec_recall_fact",
    "exec_recall_last_command",
    "exec_semantic_search_chat_history",
    "exec_search_memory",
    "exec_switch_audio_output",
    "exec_final_answer",
    "exec_write_file", "exec_list_directory", "exec_read_file", "exec_search_files",
    "exec_look_at_screen", "exec_vision_click", "exec_ask_chatgpt_visually",
    "exec_maximize_app", "exec_restore_app", "exec_hide_all_windows", "exec_snap_window",
    "exec_read_clipboard", "exec_write_clipboard", "exec_press_shortcut",
    "exec_check_performance", "exec_lock_pc", "exec_empty_recycle_bin", "exec_take_screenshot",
    "exec_show_notification", "exec_set_timer", "exec_open_folder", "exec_open_file",
    "exec_analyze_ui", "exec_click_ui_element", "exec_type_ui_element", "exec_observe_desktop"
]
