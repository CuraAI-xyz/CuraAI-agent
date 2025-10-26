import requests
import os
from typing import List
from langchain.tools import Tool, StructuredTool
import requests
from pubmed import get_medical_articles as fetch_articles
from email_sender import send_email
from googleapi import create_event, get_events

# --- 1. get_medical_articles ---
def get_medical_articles(symptoms: str) -> str:
    print("USING GET MEDICAL ARTICLES TOOL")
    pubmed_articles = fetch_articles(symptoms)
    articles_ids = []
    for article in pubmed_articles:
        articles_ids.append(article["pmid"])
    return articles_ids if articles_ids else "No relevant articles found."

get_medical_articles_tool = Tool(
    name="get_medical_articles_tool",
    func=get_medical_articles,
    description="Use this tool to search medical articles based on the patient's symptoms."
)


# --- 2. search_by_pmid ---
def search_by_pmid(pmid: str) -> str:
    print("USING SEARCH BY PMID TOOL")
    fetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    fetch_params = {
        'db': 'pubmed',
        'id': pmid,
        'retmode': 'json',
        'rettype': 'abstract'
    }
    fetch_response = requests.get(fetch_url, params=fetch_params)
    return fetch_response.text


# --- 3. generate_file ---
def generate_file(diagnosis_summary: str) -> str:
    print("USING GENERATE FILE TOOL")
    file_path = "diagnosis_summary.txt"
    with open(file_path, "w") as f:
        f.write(diagnosis_summary)
    return f"Diagnosis summary saved to {file_path}"

generate_file_tool = Tool(
    name="generate_file",
    func=generate_file,
    description="Use this tool to generate a text file with the diagnosis summary."
)


from pydantic import BaseModel, Field

class CreateEventInput(BaseModel):
    title: str = Field(description="Event title")
    description: str = Field(description="Event description")
    start_time: str = Field(description="Start datetime in ISO 8601, e.g., 2025-10-21T14:00:00Z")
    end_time: str = Field(description="End datetime in ISO 8601, e.g., 2025-10-21T17:00:00Z")

def _create_event_structured(title: str, description: str, start_time: str, end_time: str) -> str:
    create_event(title, description, start_time, end_time)
    return "Event created"

create_event_tool = StructuredTool(
    name="create_event",
    description=(
        "Create a Google Calendar event. Provide a JSON object with keys: "
        "title, description, start_time (ISO 8601), end_time (ISO 8601)."
    ),
    func=_create_event_structured,
    args_schema=CreateEventInput,
)


from pathlib import Path
from openai import OpenAI
client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"
import io
from pathlib import Path
from openai import OpenAI
client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"
import tempfile

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

def format_memory_to_text(memory) -> str:
    msgs = getattr(memory, "chat_memory", None)
    if not msgs:
        return ""
    messages = memory.chat_memory.messages
    if not messages:
        return ""
    lines: List[str] = []
    for m in messages:
        cls = m.__class__.__name__
        if cls == "HumanMessage":
            speaker = "Usuario"
        elif cls == "AIMessage":
            speaker = "Asistente"
        elif cls == "SystemMessage":
            speaker = "Sistema"
        else:
            speaker = cls
        content = getattr(m, "content", "")
        if content:
            lines.append(f"{speaker}: {content.strip()}")
    return "\n".join(lines)

dictionary = {}

def set_info(data: dict):
    """
    Recibe un diccionario con los datos del paciente y los guarda en un diccionario global.
    Compatible con LangChain, que envía un solo argumento tipo dict.
    """

    return data


set_info_tool = Tool(
    name="set_info",
    func=set_info,
    description="Use this tool to save data of a patient. Example input: {'name': 'Mauro'}"
)

send_email_tool = Tool(
    name="send_email",
    func=send_email,
    description="Use this tool to send an email"
)


class CreateEventInput(BaseModel):
    time_min: str = Field(description="Start datetime in ISO 8601, e.g., 2025-10-21T14:00:00Z")
    time_max: str = Field(description="End datetime in ISO 8601, e.g., 2025-10-21T17:00:00Z")

def get_events(params: dict):
    events = get_events(params)
    return events

get_events_tool = Tool(
    name="get_events",
    func=get_events,
    description="Use this tool to get the next 10 events on the calendar"
)