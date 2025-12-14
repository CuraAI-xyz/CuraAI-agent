from openai import OpenAI
from app.config.settings import settings
from pathlib import Path

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_speech(text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
    """
    Genera audio y retorna los bytes (no guarda archivo).
    Versión síncrona para compatibilidad con endpoints HTTP.
    """
    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3" 
        )
        return response.content
    except Exception as e:
        print(f"❌ Error en TTS: {e}")
        return None

async def generate_speech_streaming(text: str, voice: str = "alloy", model: str = "tts-1"):
    """
    Genera audio con STREAMING y retorna chunks progresivamente.
    Útil para WebSocket donde se puede enviar audio tan pronto como se genera.
    
    Args:
        text: Texto a convertir a audio
        
    Yields:
        bytes: Chunks de audio MP3
    """
    try:
        with client.audio.speech.with_streaming_response.create(
            model=model, 
            voice=voice,
            input=text,
            response_format="opus" 
        ) as response:
            chunk_size = 4096
            async for chunk in response.stream.iter_bytes(chunk_size=chunk_size):
                if chunk:
                    yield chunk
    except Exception as e:
        print(f"❌ Error en TTS streaming: {e}")
        yield None

