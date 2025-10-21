import requests
from langchain.tools import BaseTool
import pygame, time
from audio_generator import generate_audio
import os
from typing import List
from langchain.tools import Tool
import requests
from pubmed import get_medical_articles as fetch_articles
from email_sender import send_email
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
from pathlib import Path
from openai import OpenAI
client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"
import io
import pyaudio
from pathlib import Path
from openai import OpenAI
import simpleaudio as sa
import tempfile
client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"
import tempfile
import pygame

def assistant_response(ai_response: str):
    """
    Genera TTS usando gpt-4o-mini-tts y lo reproduce inmediatamente.
    Compatible con MP3 en Windows sin errores de permisos.
    """
    # Crear archivo temporal
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_file_path = temp_file.name
    temp_file.close()  # Cerramos para que OpenAI pueda escribir en él

    try:
        # Generar TTS y escribir en el archivo
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="coral",
            input=ai_response,
            instructions="Speak in a happy and positive tone. You have to be professional and serious but close"
        ) as response:
            response.stream_to_file(temp_file_path)

        # Reproducir con pygame
        pygame.mixer.init()
        pygame.mixer.music.load(temp_file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)  # Espera mientras se reproduce

        # Detener y limpiar el mixer antes de eliminar el archivo
        pygame.mixer.music.stop()
        pygame.mixer.quit()

    finally:
        # Eliminar el archivo temporal
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return ai_response

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