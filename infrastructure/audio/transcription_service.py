import os
from openai import OpenAI
from app.config.settings import settings
import io

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def transcribe_audio(audio_input):
    """
    Transcribe audio recibiendo bytes, io.BytesIO o un path (string).
    """
    audio_file = None
    should_close = False

    try:
        # CASO 1: Ya es un objeto en memoria (io.BytesIO)
        if isinstance(audio_input, io.BytesIO):
            audio_file = audio_input
            audio_file.seek(0)
            audio_file.name = "audio.wav"

        # CASO 2: Son bytes crudos
        elif isinstance(audio_input, bytes):
            audio_file = io.BytesIO(audio_input)
            audio_file.name = "audio.wav"

        # CASO 3: Es una ruta de archivo (String)
        elif isinstance(audio_input, str):
            if os.path.exists(audio_input):
                audio_file = open(audio_input, "rb")
                should_close = True
            else:
                print(f"Archivo no encontrado: {audio_input}")
                return ""
        
        else:
            print(f"Tipo de entrada no soportado: {type(audio_input)}")
            return ""

        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language="es",
            prompt="Paciente médico describiendo síntomas."
        )
        
        return transcript.text if transcript else ""

    except Exception as e:
        print(f"Error transcribiendo audio: {e}")
        return ""
    
    finally:
        if should_close and audio_file:
            audio_file.close()

