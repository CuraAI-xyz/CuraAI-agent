import datetime as dt
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import json

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Variable global para el servicio (inicialización lazy)
_service = None

def get_authenticated_service():
    """Obtiene el servicio autenticado de Google Calendar con manejo mejorado de credenciales"""
    global _service
    
    # Si ya existe el servicio y las credenciales son válidas, reutilizarlo
    if _service is not None:
        return _service
    
    credentials_json = os.getenv("CREDENTIALS_JSON")
    if not credentials_json:
        raise ValueError("CREDENTIALS_JSON environment variable is not set")
    
    # Eliminar espacios en blanco que puedan estar en el .env
    credentials_json = credentials_json.strip()
    
    try:
        # Parsear el JSON completo
        full_credentials = json.loads(credentials_json)
        
        # Acceder al objeto "web" si existe, sino usar el JSON directamente
        if 'web' in full_credentials:
            credentials_dict = full_credentials['web']
        else:
            credentials_dict = full_credentials
        
        # Validar campos básicos del cliente OAuth
        required_fields = ['token_uri', 'client_id', 'client_secret']
        missing_fields = [field for field in required_fields if not credentials_dict.get(field)]
        
        if missing_fields:
            raise ValueError(
                f"Missing required credential fields: {', '.join(missing_fields)}. "
                f"Please ensure your CREDENTIALS_JSON contains: {', '.join(required_fields)}"
            )
        
        # Obtener refresh_token y access_token (pueden estar en el nivel superior o en web)
        refresh_token = credentials_dict.get('refresh_token') or full_credentials.get('refresh_token')
        access_token = credentials_dict.get('access_token') or full_credentials.get('access_token')
        
        # Si no hay refresh_token ni access_token, ejecutar el flujo OAuth
        if not refresh_token and not access_token:
            print("No tokens found. Starting OAuth flow...")
            print("A browser window will open for you to authenticate.")
            
            # Para aplicaciones "web", necesitamos convertir a formato "installed" para InstalledAppFlow
            # O usar el formato web directamente
            if 'web' in full_credentials:
                # Convertir web a installed para InstalledAppFlow
                client_config = {'installed': credentials_dict}
            else:
                client_config = full_credentials
            
            # Crear el flujo OAuth desde la configuración del cliente
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            
            # Ejecutar el flujo local para obtener credenciales
            creds = flow.run_local_server(port=4000)
            
            print("OAuth authentication completed successfully!")
            print(f"Access Token: {creds.token[:20]}...")
            print(f"Refresh Token: {'Present' if creds.refresh_token else 'Not present'}")
            print("\nIMPORTANT: Save these tokens in your CREDENTIALS_JSON:")
            print(f'Add to your .env: "refresh_token":"{creds.refresh_token}","access_token":"{creds.token}"')
            
        else:
            # Crear credenciales con los tokens existentes
            creds = Credentials(
                token=access_token,  # Puede ser None si expiró
                refresh_token=refresh_token,
                token_uri=credentials_dict['token_uri'],
                client_id=credentials_dict['client_id'],
                client_secret=credentials_dict['client_secret'],
                scopes=SCOPES
            )
            
            # Refrescar el token si es necesario
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    print("Refreshing expired credentials...")
                    creds.refresh(Request())
                    print("Credentials refreshed successfully")
                else:
                    raise ValueError("Credentials are invalid and cannot be refreshed")
        
        _service = build('calendar', 'v3', credentials=creds)
        return _service
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in CREDENTIALS_JSON: {e}")
    except Exception as e:
        raise ValueError(f"Error loading credentials: {e}")

def create_event(title, description, start_time, end_time):
    service = get_authenticated_service()
    event = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": start_time
        },
        "end": {
            "dateTime": end_time
        }
    }
    event = service.events().insert(calendarId="primary", body=event).execute()
    return event

def get_events(params: dict):
    service = get_authenticated_service()
    print("PARAMS: ", params)
    time_min = params.get("time_min")
    time_max = params.get("time_max")
    events_result = service.events().list(
        calendarId='primary', timeMin=time_min, timeMax=time_max,
        maxResults=10, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    else:
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'],event['id'])
    
    return events    