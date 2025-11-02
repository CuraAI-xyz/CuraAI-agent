from agents import function_tool
from googleapi import create_event, get_events
from email_sender import send_email
import os
import tempfile
from pathlib import Path
from openai import OpenAI

## Create Event Tool
@function_tool
def create_event_tool(title: str, description: str, start_time: str, end_time: str) -> str:
    """Create a Google Calendar event."""
    create_event(title, description, start_time, end_time)
    return "Event created successfully"

client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"

def assistant_response(ai_response: str, output_path: str = "audios/output.wav"):
    """
    Genera TTS usando gpt-4o-mini-tts y guarda el resultado en un archivo WAV o MP3.
    No lo reproduce.
    """
    # Asegurar carpeta
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Crear archivo temporal (por compatibilidad en Windows)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_file_path = temp_file.name
    temp_file.close()

    try:
        # Generar TTS y escribir en el archivo temporal
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="alloy",
            input=ai_response
        ) as response:
            response.stream_to_file(temp_file_path)

        # Mover el archivo temporal al destino
        os.replace(temp_file_path, output_path)

    except Exception as e:
        print(f"Error al generar audio: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return output_path


@function_tool
def send_email_tool(name: str, surname: str, sex: str, birthday: str, resume: str, med_ins: str) -> str:
    """Send an email to the doctor with patient information."""
    send_email(
        name=name,
        surname=surname,
        sex=sex,
        birthday=birthday,
        resume=resume,
        med_ins=med_ins)
    return "Email sent to the doctor."



@function_tool
def get_events_tool(time_min: str, time_max: str) -> str:
    """Retrieve upcoming events within a specific date range."""
    params={"time_min": time_min, "time_max": time_max}
    events = get_events(params)
    return events