from openai import OpenAI
import os
from dotenv import load_dotenv
import requests
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_audio(input_text: str):
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=input_text,
        instructions="Speak as a doctor in a friendly tone."
    )as response:
        response.stream_to_file("response3.mp3")

    return "response3.mp3"


def transcribe_openai(audio_file_path, model="whisper-1"):
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {os.getenv("OPENAI_API_KEY")}"}
    with open(audio_file_path, "rb") as audio_file:
        files = {
            "file": (audio_file_path, audio_file, "audio/mp3"),
            "model": (None, model),
            "response_format": (None, "text")
        }
        response = requests.post(url, headers=headers, files=files)

        if response.status_code == 200:
            return response.text.strip()
        else:
            raise RuntimeError(f"Error: {response.status_code} {response.text}")