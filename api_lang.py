"""
Punto de entrada principal de la aplicación.
Mantiene compatibilidad con el código existente.
"""
from app.api.routes import create_app

app = create_app()
