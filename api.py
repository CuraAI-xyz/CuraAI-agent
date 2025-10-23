from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, Body, HTTPException, WebSocket
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import create_agent
from ocr import read_image
import asyncio
import wave
from tools import assistant_response
import av 
from audio_processor import transcribe_audio
import io 
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ocr")
async def ocr(image: UploadFile = File(...)):
    image_bytes = await image.read() 
    result = read_image(image_bytes)
    return result

@app.post("/start_agent")
def start_agent():
    """Inicializa una instancia del agente y la guarda en app.state."""
    app.state.agent = create_agent()
    return {"status": "agent_started"}

@app.post("/stop_agent")
def start_agent():
    """Inicializa una instancia del agente y la guarda en app.state."""
    app.state.agent = None
    return {"status": "agent_stopped"}

@app.post("/conversation")
async def conversation(payload: dict = Body(...)):
    """Usa el agente ya inicializado para responder un mensaje del usuario.

    Espera JSON: { "input": "mensaje del usuario" }
    """
    if not hasattr(app.state, "agent") or app.state.agent is None:
        raise HTTPException(status_code=400, detail="Agent not started. Call /start_agent first.")

    user_input = transcribe_audio()
    if not user_input:
        raise HTTPException(status_code=422, detail="Field 'input' is required and must be non-empty.")

    result = app.state.agent.invoke({"input": user_input})
    return {"output": result.get("output", "")}


def chat_endpoint(user_input: str):
       #user_input = audio_main()
        agente = app.state.agent
        res = agente.invoke({"input": user_input})
        #print(res["output"])
        assistant_response(res["output"], "./assistant_response.wav")
        file_path = "./assistant_response.wav"
        if not os.path.exists(file_path):
            return {"error": "El archivo no existe"}
    
        return file_path
        


def webm_bytes_to_wav(webm_bytes: bytes, wav_path: str, rate=16000):
    container = av.open(io.BytesIO(webm_bytes), mode="r", format="webm")
    audio_stream = next((s for s in container.streams if s.type == "audio"), None)
    if audio_stream is None:
        raise RuntimeError("No se encontró stream de audio en el WebM.")

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=rate)

    pcm_chunks = []

    for packet in container.demux(audio_stream):
        for frame in packet.decode():
            out = resampler.resample(frame)
            if not out:
                continue
            frames = out if isinstance(out, list) else [out]
            for f in frames:
                arr = f.to_ndarray()  
                if arr.ndim == 2:
                    arr = arr[0]       
                pcm_chunks.append(arr.tobytes())

    
    out = resampler.resample(None)
    if out:
        frames = out if isinstance(out, list) else [out]
        for f in frames:
            arr = f.to_ndarray()
            if arr.ndim == 2:
                arr = arr[0]
            pcm_chunks.append(arr.tobytes())

    container.close()

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   
        wf.setframerate(rate)
        wf.writeframes(b"".join(pcm_chunks))

    return wav_path



@app.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    timeout_seconds = 3

    while True:
        audio_buffer = bytearray()
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_bytes(), timeout=timeout_seconds)
                    print(f"Received {len(data)} bytes of audio data")
                    audio_buffer.extend(data)
                except asyncio.TimeoutError:
                    print("No bytes received in 3 seconds. Ending recording.")
                    break

        except Exception as e:
            print(f"WebSocket error: {e}")
            break  

        if audio_buffer:
            try:
                out = webm_bytes_to_wav(bytes(audio_buffer), "userInput.wav", rate=16000)
                print(f"Audio convertido a {out}")
                transcription = transcribe_audio()
                audio_file = chat_endpoint(transcription)
                
                # Leer el archivo de audio generado y enviarlo por WebSocket
                if os.path.exists(audio_file):
                    with open(audio_file, "rb") as audio_data:
                        audio_bytes = audio_data.read()
                        # Enviar el audio como bytes
                        await websocket.send_bytes(audio_bytes)
                        print(f"Audio enviado al frontend: {len(audio_bytes)} bytes")
                else:
                    await websocket.send_text("Error: No se pudo generar el archivo de audio")
            except Exception as e:
                print("Error decodificando WebM/Opus:", e)