import os
from dotenv import load_dotenv
from openai import OpenAI
import pyaudio
import wave
import keyboard
import tempfile

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def record_audio(frecuency=16000, channels=1, fragment=512):
    """
    Grabación push-to-talk: comienza al presionar ENTER y termina al soltar ENTER.
    """
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=channels,
                    rate=frecuency,
                    input=True,
                    frames_per_buffer=fragment)

    print("Mantén presionado ENTER para grabar...")
    # Espera a que ENTER esté presionado
    while not keyboard.is_pressed('enter'):
        pass

    print("Grabando... suelta ENTER para detener la grabación")
    frames = []

    try:
        while keyboard.is_pressed('enter'):
            data = stream.read(fragment, exception_on_overflow=False)
            frames.append(data)
    except KeyboardInterrupt:
        pass

    print("Grabación detenida")
    stream.stop_stream()
    stream.close()
    p.terminate()

    return frames, frecuency

def save_audio(frames, frecuency):
    """
    Guarda el audio en un archivo WAV temporal y devuelve su path
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio_file:
        with wave.open(temp_audio_file.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
            wf.setframerate(frecuency)
            wf.writeframes(b''.join(frames))
        return temp_audio_file.name

def transcribe_audio(frames, frecuency):
    """
    Graba audio, lo guarda y lo transcribe usando OpenAI
    """
    audio_file_path = save_audio(frames, frecuency)
    transcript_text = ""

    with open(audio_file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )
        transcript_text = transcript.text if transcript and hasattr(transcript, "text") else ""

    os.remove(audio_file_path)
    return transcript_text

def main():
    frames, frecuency = record_audio()
    if not frames:
        print("No se detectó audio.")
        return

    transcript = transcribe_audio(frames, frecuency)
    if transcript:
        # Devuelve un string válido para LangChain
        user_input = transcript.strip()
        return user_input
    else:
        print("No se pudo transcribir el audio.")
        return ""

if __name__ == "__main__":
    main()
