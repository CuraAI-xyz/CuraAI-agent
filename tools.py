from langchain_core.tools import tool
from googleapi import create_event, get_events
import os
import tempfile
from pathlib import Path
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


## Create Event Tool
@tool
def create_event_tool(title: str, description: str, start_time: str, end_time: str) -> str:
    """Create a Google Calendar event.
    
    Args:
        title: Event title
        description: Event description
        start_time: Start time in ISO format (e.g., "2024-01-15T09:00:00Z")
        end_time: End time in ISO format (e.g., "2024-01-15T10:00:00Z")
    
    Returns:
        Confirmation message that event was created successfully
    """
    create_event(title, description, start_time, end_time)
    return "Event created successfully"


client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"

def assistant_response(text, file_path=None):
    """
    Genera audio y RETORNA LOS BYTES (no guarda archivo).
    Versión síncrona para compatibilidad con endpoints HTTP.
    """
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="mp3" # O pcm/opus para menor tamaño
        )
        
        # ✅ CORRECTO: Retornar el contenido binario
        return response.content 

    except Exception as e:
        print(f"❌ Error en TTS: {e}")
        # Retornamos None para que el main sepa que falló
        return None


async def assistant_response_streaming(text: str):
    """
    Genera audio con STREAMING y retorna chunks progresivamente.
    Útil para WebSocket donde se puede enviar audio tan pronto como se genera.
    
    Args:
        text: Texto a convertir a audio
        
    Yields:
        bytes: Chunks de audio MP3
    """
    try:
        # Usar with_streaming_response para obtener el stream
        with client.audio.speech.with_streaming_response.create(
            model="tts-1", 
            voice="alloy",
            input=text,
            response_format="opus" 
        ) as response:
            # Leer chunks del stream en lugar de esperar todo
            chunk_size = 4096
            async for chunk in response.stream.iter_bytes(chunk_size=chunk_size):
                if chunk:
                    yield chunk
                
    except Exception as e:
        print(f"❌ Error en TTS streaming: {e}")
        yield None

@tool
def get_events_tool(time_min: str, time_max: str) -> str:
    """Retrieve upcoming events within a specific date range.
    
    Args:
        time_min: Fecha de inicio de búsqueda en formato ISO (e.g., "2024-01-15T09:00:00Z")
        time_max: Fecha de fin de búsqueda en formato ISO (e.g., "2024-01-15T17:00:00Z")
    
    Returns:
        List of events within the specified date range
    """
    params = {"time_min": time_min, "time_max": time_max}
    events = get_events(params)
    return events

@tool
def send_email(name: str, surname: str, sex: str, birthday: str, resume: str,  med_ins: str) -> str:
    """Envía un correo electrónico al doctor con la información del paciente.
    
    Args:
        name: Nombre del paciente
        surname: Apellido del paciente
        sex: Sexo biológico del paciente
        birthday: Fecha de nacimiento del paciente
        resume: Resumen de la situación clínica del paciente
        med_ins: Cobertura médica u obra social del paciente
    
    Returns:
        Mensaje de confirmación indicando que el correo fue enviado exitosamente
    
    Raises:
        ValueError: Si las credenciales de correo no están configuradas en las variables de entorno
    """
    sender_email = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver_email = os.getenv("EMAIL_RECEIVER")
    
    # Validar que las variables de entorno estén configuradas
    if not all([sender_email, password, receiver_email]):
        raise ValueError("Email credentials not configured. Please set EMAIL_SENDER, EMAIL_PASSWORD, and EMAIL_RECEIVER environment variables.")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Información de paciente - CuraAI 🤖"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    text = "Este correo tiene formato HTML. Si no ves los estilos, abrilo en un cliente compatible."
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: white; margin: 0; padding: 20px;">
        <div style="display: flex; flex-direction: column; align-items: flex-start; max-width: 600px; background: #61A5C2; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h1 style="color: white">CuraAI</h1>
        <h2 style="color: white;">Hola doctor/a, soy Cura, le envío la información del paciente.</h2>
        <p style="color: white;">Nombre: {name}</p>
        <p style="color: white;">Apellido: {surname}</p>
        <p style="color: white;">Fecha de nacimiento: {birthday}</p>
        <p style="color: white;">Cobertura médica: {med_ins}</p>
        <p style="color: white;">Sexo: {sex}</p>
        <p style="color: white;">Resumen de la situación del paciente: {resume}</p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

    return "Correo enviado exitosamente al doctor."    