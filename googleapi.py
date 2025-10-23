import datetime as dt
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = None
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json")

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    else:
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)        

    with open("token.json", "w") as token:
        token.write(creds.to_json())

try:
    service = build("calendar", "v3", credentials=creds)
       
except HttpError as error:
    print(f"ERROR: {error}")


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