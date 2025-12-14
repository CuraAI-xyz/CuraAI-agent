from fastapi import FastAPI, UploadFile, File, Body, HTTPException, WebSocket
from agent import conversation_history, agente_memoria
from fastapi.middleware.cors import CORSMiddleware
from audio_processor import transcribe_audio
from tools import assistant_response
from agents import Runner
from ocr import read_image
import asyncio
import wave
import os
import av 
import io


app = FastAPI()
port = int(os.environ.get("PORT", 8080))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"])

def _run_runner_sync_with_loop(agent, conv_history):
    """
    Ejecuta Runner.run_sync en un hilo creando y asignando un event loop
    en ese hilo. Devuelve lo que retorne Runner.run_sync.
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return Runner.run_sync(agent, conv_history)
    finally:
        try:
            # Des-asignar el loop del hilo y cerrarlo
            asyncio.set_event_loop(None)
        except Exception:
            pass
        try:
            if loop is not None:
                loop.close()
        except Exception:
            pass



@app.post("/ocr")
async def ocr(image: UploadFile = File(...)):
    image_bytes = await image.read() 
    result = read_image(image_bytes)
    return result

@app.post("/start_agent")
def start_agent():
    """Inicializa una instancia del agente y la guarda en app.state."""
    app.state.agent = agente_memoria
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

    user_input = transcribe_audio("userInput.wav")
    if not user_input:
        raise HTTPException(status_code=422, detail="Field 'input' is required and must be non-empty.")

    result = app.state.agent.invoke({"input": user_input})
    return {"output": result.get("output", "")}

async def chat_endpoint(user_input: str):
    agente = app.state.agent
    if not agente:
        return {"error": "El agente no está inicializado."}

    try:
        conversation_history.append({"role": "user", "content": user_input})
        res = await asyncio.to_thread(_run_runner_sync_with_loop, app.state.agent, conversation_history)
        conversation_history.append({"role": "assistant", "content": res.final_output})
        output = res.final_output

        if not output:
            return {"error": "No se recibió respuesta del agente."}

        assistant_response(output, "./assistant_response.wav")
        file_path = "./assistant_response.wav"

        if not os.path.exists(file_path):
            return {"error": "El archivo de audio no existe."}

        return file_path
    except Exception as e:
        return {"error": f"Ocurrió un error al procesar la entrada: {e}"}


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
    try:
        await websocket.accept()
        print("WebSocket connection accepted")
    except Exception as e:
        print(f"Error accepting WebSocket: {e}")
        return
    timeout_seconds = 3
    connection_open = True
    try:
        while connection_open:
            audio_buffer = bytearray()
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.receive(), timeout=timeout_seconds)
                        
                        if "bytes" in message:
                            data = message["bytes"]
                            print(f"Received {len(data)} bytes of audio data")
                            audio_buffer.extend(data)
                        elif "text" in message:
                            print(f"Received text message: {message['text']}")
                        elif message.get("type") == "websocket.disconnect":
                            print("Client disconnected")
                            connection_open = False
                            break
                    except asyncio.TimeoutError:
                        print("No bytes received in 3 seconds. Ending recording.")
                        break
                    except Exception as e:
                        print(f"Error receiving data: {e}")
                        connection_open = False
                        break

            except Exception as e:
                print(f"WebSocket error: {e}")
                connection_open = False
                break  

            if audio_buffer and connection_open:
                try:
                    out = webm_bytes_to_wav(bytes(audio_buffer), "userInput.wav", rate=16000)
                    transcription = transcribe_audio(out)
                    audio_file = await chat_endpoint(transcription)
                    if isinstance(audio_file, dict) and "error" in audio_file:
                        await websocket.send_text(f"Error: {audio_file['error']}")
                        continue

                    if isinstance(audio_file, str) and os.path.exists(audio_file):
                        with open(audio_file, "rb") as audio_data:
                            audio_bytes = audio_data.read()
                            await websocket.send_bytes(audio_bytes)
                            print(f"Audio enviado al frontend: {len(audio_bytes)} bytes")
                    else:
                        await websocket.send_text("Error: No se pudo generar el archivo de audio")
                except Exception as e:
                    print("Error decodificando WebM/Opus:", e)
    
    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        print("Closing WebSocket connection")
        try:
            await websocket.close()
        except:
            pass