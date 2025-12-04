from fastapi import FastAPI, WebSocket, Response
from agente_langgraph import app_graph
from fastapi.middleware.cors import CORSMiddleware
from tools import assistant_response, assistant_response_streaming
from audio_processor import transcribe_audio
import asyncio
import wave
import av
import os
import io
import time
import logging

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"])

# ✅ ESTADO GLOBAL PERSISTENTE por paciente
patients_state = {}

logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def warmup_agent():
    # ... (Tu código de warmup está bien, no cambia) ...
    def _warm():
        try:
            cfg = {"configurable": {"thread_id": "warmup_thread"}}
            state = {
                "name": "warmup", "surname": "warmup", "sex": "N/A", "messages": [],
                "query": "Hola", "med_insurance": "", "birthday": "", "resume": "", "email_sent": False
            }
            start = time.perf_counter()
            app_graph.invoke(state, config=cfg)
            logging.info(f"Agent warmup completed in {time.perf_counter()-start:.2f}s")
        except Exception as e:
            logging.exception("Warmup failed: %s", e)
    asyncio.get_event_loop().run_in_executor(None, _warm)


def get_or_create_patient_state(patient_id: str = "patient_123"):
    if patient_id not in patients_state:
        patients_state[patient_id] = {
            "name": "Juan", "surname": "Perez", "sex": "masculino", "messages": [],
            "query": "", "med_insurance": "OSDE", "birthday": "1985-05-15",
            "resume": "Paciente con antecedentes de hipertensión.", "email_sent": False
        }
    return patients_state[patient_id]

@app.get("/")
async def chat_endpoint(user_input: str, patient_id: str = "patient_123"):
    # ✅ Obtener estado persistente
    state = get_or_create_patient_state(patient_id)
    state["query"] = user_input
    
    config = {"configurable": {"thread_id": patient_id}}
    
    t0 = time.perf_counter()
    # ✅ Invocar con ESTADO COMPLETO
    result = app_graph.invoke(state, config=config)
    t1 = time.perf_counter()
    patients_state[patient_id] = result
    
    # ---------------------------------------------------------
    # CORRECCIÓN: In-Memory Output
    # ---------------------------------------------------------
    # Eliminamos el path "./assistant_response.wav"
    # Asumimos que assistant_response ahora devuelve bytes (recuerda cambiar tools.py)
    audio_bytes = assistant_response(result["messages"][-1].content)
    
    t2 = time.perf_counter()
    logging.info(f"invoke: {t1-t0:.2f}s, tts: {t2-t1:.2f}s, total: {t2-t0:.2f}s")
    
    # Devolvemos bytes directamente. 
    # Si llamas esto por HTTP (Navegador), FastAPI necesita 'Response'
    return Response(content=audio_bytes, media_type="audio/mp3")


@app.websocket("/audio")
async def websocket_endpoint(websocket: WebSocket, patient_id: str = "patient_123"):
    try:
        await websocket.accept()
        print(f"WebSocket connection accepted for patient {patient_id}")
    except Exception as e:
        print(f"Error accepting WebSocket: {e}")
        return
    
    # Optimización: Timeout adaptativo con detección de silencio
    SILENCE_THRESHOLD = 0.5  # segundos de silencio para terminar
    CHUNK_TIMEOUT = 0.5  # timeout para recibir cada chunk
    connection_open = True
    
    try:
        while connection_open:
            audio_buffer = bytearray()
            last_audio_time = time.time()
            
            try:
                # Recibir audio en chunks
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.receive(), timeout=CHUNK_TIMEOUT)
                        if "bytes" in message:
                            data = message["bytes"]
                            print(f"Received {len(data)} bytes of audio data")
                            audio_buffer.extend(data)
                            last_audio_time = time.time()  # Actualizar tiempo de último audio
                        elif "text" in message:
                            print(f"Received text message: {message['text']}")
                        elif message.get("type") == "websocket.disconnect":
                            print("Client disconnected")
                            connection_open = False
                            break
                    except asyncio.TimeoutError:
                        # Si pasó mucho tiempo sin audio, terminar la grabación
                        if time.time() - last_audio_time > SILENCE_THRESHOLD:
                            print("Silencio detectado. Ending recording.")
                            break
                        # Si no hay audio todavía, continuar esperando
                        continue
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
                    t_start = time.perf_counter()
                    
                    # Optimización: Procesar conversión y preparar estado en paralelo
                    wav_task = asyncio.create_task(
                        asyncio.to_thread(webm_bytes_to_wav, bytes(audio_buffer), 16000)
                    )
                    state_task = asyncio.create_task(
                        asyncio.to_thread(get_or_create_patient_state, patient_id)
                    )
                    
                    wav_in_memory, state = await asyncio.gather(wav_task, state_task)
                    
                    t_webm = time.perf_counter()
                    logging.info(f"WebM conversion: {t_webm - t_start:.2f}s")
                    
                    # Transcripción
                    transcription = await asyncio.to_thread(transcribe_audio, wav_in_memory)
                    print(f"Transcription: {transcription}")
                    t_transcription = time.perf_counter()
                    logging.info(f"Transcription: {t_transcription - t_webm:.2f}s")
                    
                    if not transcription or not transcription.strip():
                        await websocket.send_text("Error: No se pudo transcribir el audio")
                        continue
                    
                    # Procesar con el agente
                    state["query"] = transcription
                    config = {"configurable": {"thread_id": patient_id}}
                    
                    result = await asyncio.to_thread(app_graph.invoke, state, config)
                    patients_state[patient_id] = result
                    
                    t_agent = time.perf_counter()
                    logging.info(f"Agent processing: {t_agent - t_transcription:.2f}s")
                    
                    # ---------------------------------------------------------
                    # OPTIMIZACIÓN CRÍTICA: Streaming de TTS
                    # ---------------------------------------------------------
                    # En lugar de esperar todo el audio, enviar chunks progresivamente
                    response_text = result["messages"][-1].content
                    
                    t_tts_start = time.perf_counter()
                    chunk_count = 0
                    total_bytes = 0
                    
                    async for audio_chunk in assistant_response_streaming(response_text):
                        if audio_chunk:
                            await websocket.send_bytes(audio_chunk)
                            chunk_count += 1
                            total_bytes += len(audio_chunk)
                    
                    t_tts_end = time.perf_counter()
                    logging.info(f"TTS streaming: {t_tts_end - t_tts_start:.2f}s ({chunk_count} chunks, {total_bytes} bytes)")
                    logging.info(f"TOTAL: {t_tts_end - t_start:.2f}s")
                    print(f"Audio enviado al frontend: {total_bytes} bytes en {chunk_count} chunks")
                        
                except Exception as e:
                    print(f"Error procesando audio ciclo completo: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_text(f"Error: {str(e)}")
    
    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        print("Closing WebSocket connection")
        try:
            await websocket.close()
        except:
            pass

# ... (Tu función webm_bytes_to_wav se mantiene igual, ya está optimizada) ...
def webm_bytes_to_wav(webm_bytes: bytes, rate=16000):
    container = av.open(io.BytesIO(webm_bytes), mode="r", format="webm")
    # ... (resto de tu función webm_bytes_to_wav) ...
    # Asegurate de incluir el código completo de esta función que ya tenías bien
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