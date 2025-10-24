import datetime as dt
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import os
import json

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_authenticated_service():
    """Obtiene el servicio autenticado de Google Calendar"""
    creds = None
    # El archivo token.json almacena los tokens de acceso y actualización del usuario
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si no hay credenciales válidas disponibles, permite al usuario hacer login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Cargar credenciales desde variable de entorno
            credentials_json = os.getenv("CREDENTIALS_JSON")
            if not credentials_json:
                raise ValueError("CREDENTIALS_JSON environment variable is not set")
            
            try:
                credentials_dict = json.loads(credentials_json)
                flow = InstalledAppFlow.from_client_config(credentials_dict, SCOPES)
                creds = flow.run_local_server(port=0)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in CREDENTIALS_JSON: {e}")
            except Exception as e:
                raise ValueError(f"Error loading credentials: {e}")
        
        # Guardar las credenciales para la próxima ejecución
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('calendar', 'v3', credentials=creds)

# Inicializar el servicio
service = get_authenticated_service()

def create_event(title, description, start_time, end_time):
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