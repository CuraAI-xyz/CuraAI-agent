from langchain_core.tools import tool
from infrastructure.google import create_event, get_events
from app.config.settings import settings
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from supabase import create_client
except ImportError:
    # Si supabase no está instalado, creamos una función stub
    def create_client(*args, **kwargs):
        raise ImportError("Supabase dependencies not installed. Install supabase package.")

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
def send_email(name: str, surname: str, sex: str, birthday: str, resume: str, med_ins: str) -> str:
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
    sender_email = settings.EMAIL_SENDER
    password = settings.EMAIL_PASSWORD
    receiver_email = settings.EMAIL_RECEIVER
    
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

@tool()
def show_calendar(link) -> str:
    """ 
    Muestra el calendario al paciente.
    Returns:
        JSON string con la configuración.
    """
    return f'{{"action": "open_calendar", "date": "today", "url": "{link}"}}'

@tool
def update_database(patient_id: str, field: str, value: str) -> str:
    """Actualiza un campo específico en la base de datos del paciente.
    
    Args:
        patient_id: ID único del paciente
        field: Campo a actualizar (e.g., "med_insurance", "birthday", "resume")
        value: Nuevo valor para el campo
    Returns:
        Mensaje de confirmación indicando que la base de datos fue actualizada exitosamente
    """
    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        data = {field: value}      
        res = client.table("UsersData").update(data).eq("user_id", patient_id).execute()
        return f"Base de datos actualizada: {field} establecido a {value} para paciente {patient_id}."    
    except Exception as e:
        return f"Error al actualizar la base de datos: {e}"

@tool
def search_doctors(speciality: str, location: str) -> str:
    """Busca médicos según la especialidad y ubicación proporcionadas.
    
    Args:
        speciality: Especialidad médica (e.g., "cardiología", "dermatología")
        location: Ubicación geográfica (e.g., "Buenos Aires", "CABA")
    
    Returns:
        Lista de médicos que coinciden con los criterios de búsqueda en formato JSON string
    """
    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        
        # Usar filtros más flexibles en lugar de match exacto
        query = client.table("DoctorsData").select("*")
        
        # Filtrar por especialidad (case-insensitive, búsqueda parcial)
        if speciality:
            query = query.ilike("speciality", f"%{speciality}%")
        
        # Filtrar por ubicación (case-insensitive, búsqueda parcial)
        if location:
            query = query.ilike("location", f"%{location}%")
        
        res = query.execute()
        print(f"Resultados de búsqueda de médicos: {res.data}")
        
        # Convertir a JSON string para que LangChain pueda procesarlo correctamente
        if res.data:
            return json.dumps(res.data, ensure_ascii=False)
        else:
            return json.dumps([])
            
    except Exception as e:
        error_msg = f"Error al buscar médicos: {e}"
        print(error_msg)
        return error_msg