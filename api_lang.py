from fastapi import FastAPI, WebSocket, Response, HTTPException, Request
from agente_langgraph import app_graph
from langchain_core.messages import ToolMessage
from fastapi.middleware.cors import CORSMiddleware
from tools import assistant_response
from audio_processor import transcribe_audio
from pydantic import BaseModel
import asyncio
import wave
import av
import os
import io
import time
import logging
import json
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"])


logging.basicConfig(level=logging.INFO)

user_sessions = {}
calendar_state = False

class UserIdRequest(BaseModel):
    userId: str
    name: str
    surname: str
    sex: str
    patient_id: str

@app.post("/userId")
async def get_user_id(request: Request):
    try:
        # Leer el body crudo para debug
        body = await request.json()
        
        # Validar que userId existe 
        if "userId" not in body or not body["userId"]:
            raise HTTPException(status_code=422, detail="userId es requerido")
        
        # Usar valores por defecto si son null/None
        user_id = body["userId"]
        name = body.get("name") or ""
        surname = body.get("surname") or ""
        sex = body.get("sex") or ""
        
        user_sessions[user_id] = {
            "patient_id": user_id,
            "name": name,
            "surname": surname,
            "sex": sex,
        }
        
        print(f"User session created for: {user_id}")
        return {"status": "recibido", "patient_id": user_id}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Body debe ser JSON válido")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en get_user_id: {e}")
        raise HTTPException(status_code=400, detail=f"Error procesando request: {str(e)}")

@app.get("/")
async def chat_endpoint(user_input: str, patient_id: str):
    # Recuperamos los datos de este paciente específico
    current_state = user_sessions.get(patient_id)
    
    if not current_state:
        return Response(content=b"Error: Usuario no inicializado", status_code=400)

    # Preparamos el input para el grafo
    graph_input = {
        "query": user_input,
        "messages": current_state.get("messages", []),
        "name": current_state.get("name"),
        "surname": current_state.get("surname"),
        "sex": current_state.get("sex"),
        "patient_id": current_state.get("patient_id")
    }

    config = {"configurable": {"thread_id": patient_id}}
    
    # Invocamos pasando el input específico
    t0 = time.perf_counter()
    result = app_graph.invoke(graph_input, config=config)
    t1 = time.perf_counter()
    
    # Actualizar el estado del paciente con el resultado
    user_sessions[patient_id]["messages"] = result.get("messages", [])
    if result.get("name"):
        user_sessions[patient_id]["name"] = result["name"]
    if result.get("surname"):
        user_sessions[patient_id]["surname"] = result["surname"]
    if result.get("sex"):
        user_sessions[patient_id]["sex"] = result["sex"]
    
    audio_bytes = assistant_response(result["messages"][-1].content)
    
    t2 = time.perf_counter()
    logging.info(f"invoke: {t1-t0:.2f}s, tts: {t2-t1:.2f}s, total: {t2-t0:.2f}s")
    
    # Devolvemos bytes directamente
    return Response(content=audio_bytes, media_type="audio/mp3")


@app.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket):
    patient_id = None
    try:
        await websocket.accept()
        # Intentar obtener patient_id del query string
        if websocket.query_params.get("patient_id"):
            patient_id = websocket.query_params.get("patient_id")
        print(f"WebSocket connection accepted for patient {patient_id}")

        if calendar_state:
            websocket.send_json({calendar_state: True})
            print("MUESTRO CALENDARIO")
    except Exception as e:
        print(f"Error accepting WebSocket: {e}")
        return
    
    timeout_seconds = 1
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
                            text_msg = message['text']
                            print(f"Received text message: {text_msg}")
                            # Si el primer mensaje es texto y contiene patient_id, guardarlo
                            if not patient_id:
                                try:
                                    msg_data = json.loads(text_msg)
                                    if "patient_id" in msg_data:
                                        patient_id = msg_data["patient_id"]
                                        print(f"Patient ID received: {patient_id}")
                                except:
                                    # Si no es JSON, intentar usarlo directamente como patient_id
                                    if text_msg in user_sessions:
                                        patient_id = text_msg
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
                    wav_in_memory = webm_bytes_to_wav(bytes(audio_buffer), rate=16000)
                    transcription = transcribe_audio(wav_in_memory)
                    print(f"Transcription: {transcription}")
                    
                    if not patient_id:
                        if user_sessions:
                            patient_id = list(user_sessions.keys())[-1]
                        else:
                            await websocket.send_text("Error: No se encontró sesión de usuario")
                            continue
                    
                    response_obj = await chat_endpoint(transcription, patient_id=patient_id)
                    
                    current_result = user_sessions.get(patient_id)
                    if current_result and "messages" in current_result:
                        messages = current_result["messages"]
                        
                    # Buscar el último ToolMessage de show_calendar
                    for msg in reversed(messages):
                        if isinstance(msg, ToolMessage) and msg.name == "show_calendar":
                            try:
                                calendar_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                                
                                ui_command = {
                                    "type": "ui_update",
                                    "action": "show_calendar",
                                    "data": calendar_data
                                }
                                await websocket.send_json(ui_command)
                                break 
                            except Exception as e:
                                print(f"Error parseando: {e}")

                    # Extraemos los bytes del audio 
                    if isinstance(response_obj, Response):
                        audio_bytes = response_obj.body
                    else:
                        audio_bytes = response_obj

                    if audio_bytes and len(audio_bytes) > 0:
                        await websocket.send_bytes(audio_bytes)
                        print(f"Audio enviado al frontend: {len(audio_bytes)} bytes")
                    else:
                        await websocket.send_text("Error: No se generó audio válido")
                        
                except Exception as e:
                    print(f"Error procesando audio ciclo completo: {e}")
                    import traceback
                    traceback.print_exc()
    
    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        print("Closing WebSocket connection")
        try:
            await websocket.close()
        except:
            pass

def webm_bytes_to_wav(webm_bytes: bytes, rate=16000):
    container = av.open(io.BytesIO(webm_bytes), mode="r", format="webm")
    audio_stream = next((s for s in container.streams if s.type == "audio"), None)
    if audio_stream is None:
        raise RuntimeError("No se encontró stream de audio en el WebM.")

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=rate)
    pcm_chunks = []

    for packet in container.demux(audio_stream):
        for frame in packet.decode():
            out = resampler.resample(frame)
            if not out: continue
            frames = out if isinstance(out, list) else [out]
            for f in frames:
                arr = f.to_ndarray() 
                if arr.ndim == 2: arr = arr[0]      
                pcm_chunks.append(arr.tobytes())

    out = resampler.resample(None)
    if out:
        frames = out if isinstance(out, list) else [out]
        for f in frames:
            arr = f.to_ndarray()
            if arr.ndim == 2: arr = arr[0]
            pcm_chunks.append(arr.tobytes())

    container.close()

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   
        wf.setframerate(rate)
        wf.writeframes(b"".join(pcm_chunks))
    
    wav_buffer.seek(0)
    wav_buffer.name = "audio.wav" 
    return wav_buffer

