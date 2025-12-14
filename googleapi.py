"""
Archivo de compatibilidad - redirige a los nuevos servicios de Google
"""
from infrastructure.google import create_event, get_events

__all__ = ["create_event", "get_events"]
