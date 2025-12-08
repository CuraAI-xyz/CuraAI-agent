import os
from dotenv import load_dotenv
from openai import OpenAI
import soundfile as sf
import numpy as np
import tempfile
import keyboard
import sounddevice as sd
import io
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def record_audio(frecuency=16000, channels=1):
    print("Mantén presionado ENTER para grabar...")
    # Espera a que ENTER esté presionado
    while not keyboard.is_pressed('enter'):
        pass

    print("Grabando... suelta ENTER para detener la grabación")
    recording = []

    try:
        # Grabar audio mientras ENTER esté presionado
        with sd.InputStream(samplerate=frecuency, channels=channels, dtype='int16') as stream:
            while keyboard.is_pressed('enter'):
                data, overflowed = stream.read(frecuency // 10)  # Leer ~100ms a la vez
                recording.append(data)
    except KeyboardInterrupt:
        pass

    print("Grabación detenida")
    
    if recording:
        # Concatenar todos los frames
        frames = np.concatenate(recording, axis=0)
        return frames, frecuency
    return None, frecuency 

def save_audio(frames, frecuencia):
    """
    Guarda el audio como userInput.wav en el directorio temporal
    y devuelve su ruta completa.
    """
    temp_dir = tempfile.gettempdir()  # obtiene /tmp en Linux o %TEMP% en Windows
    audio_path = os.path.join(temp_dir, "userInput.wav")

    sf.write(audio_path, frames, frecuencia, format='WAV')
    return audio_path

def transcribe_audio(audio_input):
    """
    Transcribe audio recibiendo bytes, io.BytesIO o un path (string).
    """
    audio_file = None
    should_close = False

    try:
        # CASO 1: Ya es un objeto en memoria (io.BytesIO) -> Lo que viene de webm_bytes_to_wav
        if isinstance(audio_input, io.BytesIO):
            audio_file = audio_input
            audio_file.seek(0) # Rebobinar por seguridad
            audio_file.name = "audio.wav" # Asegurar extensión para OpenAI

        # CASO 2: Son bytes crudos -> Creamos el objeto en memoria
        elif isinstance(audio_input, bytes):
            audio_file = io.BytesIO(audio_input)
            audio_file.name = "audio.wav"

        # CASO 3: Es una ruta de archivo (String) -> Legacy support
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

        # --- LLAMADA A OPENAI OPTIMIZADA ---
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language="es",  # Optimización de idioma
            prompt="Paciente médico describiendo síntomas." # Prompt de contexto
        )
        
        return transcript.text if transcript else ""

    except Exception as e:
        print(f"Error transcribiendo audio: {e}")
        return ""
    
    finally:
        # Solo cerramos si nosotros abrimos el archivo físico (Caso 3)
        if should_close and audio_file:
            audio_file.close()

def main():
    transcript = transcribe_audio()
    if transcript:
        user_input = transcript.strip()
        return user_input
    else:
        print("No se pudo transcribir el audio.")
        return ""

