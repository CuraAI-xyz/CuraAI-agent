try:
    from .calendar_service import create_event, get_events
    __all__ = ["create_event", "get_events"]
except ImportError as e:
    # Si las dependencias de Google no están instaladas, creamos funciones stub
    def create_event(*args, **kwargs):
        raise ImportError("Google Calendar dependencies not installed. Install google-api-python-client and google-auth-oauthlib")
    
    def get_events(*args, **kwargs):
        raise ImportError("Google Calendar dependencies not installed. Install google-api-python-client and google-auth-oauthlib")
    
    __all__ = ["create_event", "get_events"]

