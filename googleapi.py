import datetime as dt
import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Cargar credenciales desde variable de entorno
credentials_json = os.getenv("CREDENTIALS_JSON")
if not credentials_json:
    raise ValueError("CREDENTIALS_JSON environment variable is not set")

try:
    credentials_dict = json.loads(credentials_json)
    creds = Credentials.from_authorized_user_info(credentials_dict, SCOPES)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON in CREDENTIALS_JSON: {e}")
except Exception as e:
    raise ValueError(f"Error loading credentials: {e}")

# Para Render, usar las credenciales directamente
# No necesitamos el flujo de autenticación local ni archivos token.json
try:
    service = build("calendar", "v3", credentials=creds)
except HttpError as error:
    print(f"ERROR: {error}")
    service = None


def create_event(title, description, start_time, end_time):
    if not service:
        raise Exception("Google Calendar service not available")
    
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
    if not service:
        raise Exception("Google Calendar service not available")
    
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