import os
from dotenv import load_dotenv
from openai import OpenAI
import soundfile as sf
import numpy as np
import tempfile

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

""" def record_audio(frecuency=16000, channels=1):
    Grabación push-to-talk: comienza al presionar ENTER y termina al soltar ENTER.
    Usa sounddevice en lugar de pyaudio (compatible con Render)
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
    return None, frecuency """

def save_audio(frames, frecuencia):
    """
    Guarda el audio como userInput.wav en el directorio temporal
    y devuelve su ruta completa.
    """
    temp_dir = tempfile.gettempdir()  # obtiene /tmp en Linux o %TEMP% en Windows
    audio_path = os.path.join(temp_dir, "userInput.wav")

    sf.write(audio_path, frames, frecuencia, format='WAV')
    return audio_path

def transcribe_audio(audio_path=None):
    """
    Transcribe audio usando OpenAI
    """
    if audio_path is None:
        audio_path = "userInput.wav"
    
    transcript_text = ""
    
    if not os.path.exists(audio_path):
        print(f"Archivo de audio no encontrado: {audio_path}")
        return ""
    
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            transcript_text = transcript.text if transcript and hasattr(transcript, "text") else ""
    except Exception as e:
        print(f"Error transcribiendo audio: {e}")
    
    return transcript_text

def main():
    transcript = transcribe_audio()
    if transcript:
        user_input = transcript.strip()
        return user_input
    else:
        print("No se pudo transcribir el audio.")
        return ""

