"""
Módulo de compatibilidad para mantener la función assistant_response
que se usa en api_lang.py. Esta función será deprecada en favor de
infrastructure.audio.generate_speech
"""
from infrastructure.audio import generate_speech

def assistant_response(text, file_path=None):
    """
    Genera audio y RETORNA LOS BYTES (no guarda archivo).
    Versión síncrona para compatibilidad con endpoints HTTP.
    """
    return generate_speech(text)

async def assistant_response_streaming(text: str):
    """
    Genera audio con STREAMING y retorna chunks progresivamente.
    """
    from infrastructure.audio import generate_speech_streaming
    async for chunk in generate_speech_streaming(text):
        yield chunk

