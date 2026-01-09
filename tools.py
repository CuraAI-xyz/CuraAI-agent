"""
Archivo de compatibilidad - redirige a los nuevos módulos
"""
from core.tools import (
    create_event_tool,
    get_events_tool,
    send_email,
    update_database,
    show_calendar, 
    search_doctors
)
from core.tools.audio_compat import assistant_response, assistant_response_streaming

__all__ = [
    "create_event_tool",
    "get_events_tool",
    "send_email",
    "update_database",
    "show_calendar",
    "search_doctors",
    "assistant_response",
    "assistant_response_streaming"
]
