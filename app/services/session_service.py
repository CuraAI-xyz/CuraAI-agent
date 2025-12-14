from typing import Dict, Optional

class SessionService:
    """Servicio para manejar sesiones de usuario"""
    
    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._calendar_state = False
    
    def create_session(self, user_id: str, name: str = "", surname: str = "", sex: str = "") -> dict:
        """Crea una nueva sesión de usuario"""
        self._sessions[user_id] = {
            "patient_id": user_id,
            "name": name,
            "surname": surname,
            "sex": sex,
            "messages": []
        }
        return self._sessions[user_id]
    
    def get_session(self, user_id: str) -> Optional[dict]:
        """Obtiene la sesión de un usuario"""
        return self._sessions.get(user_id)
    
    def update_session(self, user_id: str, **kwargs) -> None:
        """Actualiza campos de una sesión"""
        if user_id in self._sessions:
            self._sessions[user_id].update(kwargs)
    
    def set_calendar_state(self, state: bool) -> None:
        """Establece el estado del calendario"""
        self._calendar_state = state
    
    def get_calendar_state(self) -> bool:
        """Obtiene el estado del calendario"""
        return self._calendar_state
    
    def get_all_sessions(self) -> Dict[str, dict]:
        """Obtiene todas las sesiones (para compatibilidad con código existente)"""
        return self._sessions

# Instancia global del servicio (mantiene compatibilidad con código existente)
session_service = SessionService()

