import asyncio
import json
from fastapi import WebSocket
from langchain_core.messages import ToolMessage
from infrastructure.audio import transcribe_audio, webm_bytes_to_wav
from app.services.chat_service import process_chat_message
from app.services.session_service import session_service

async def handle_websocket_connection(websocket: WebSocket):
    """Maneja la conexión WebSocket para audio"""
    patient_id = None
    try:
        await websocket.accept()
        if websocket.query_params.get("patient_id"):
            patient_id = websocket.query_params.get("patient_id")
        print(f"WebSocket connection accepted for patient {patient_id}")

        calendar_state = session_service.get_calendar_state()
        if calendar_state:
            await websocket.send_json({"calendar_state": True})
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
                            if not patient_id:
                                try:
                                    msg_data = json.loads(text_msg)
                                    if "patient_id" in msg_data:
                                        patient_id = msg_data["patient_id"]
                                        print(f"Patient ID received: {patient_id}")
                                except:
                                    all_sessions = session_service.get_all_sessions()
                                    if text_msg in all_sessions:
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
                        # Obtener todas las sesiones disponibles
                        all_sessions = session_service.get_all_sessions()
                        if all_sessions:
                            patient_id = list(all_sessions.keys())[-1]
                        else:
                            await websocket.send_text("Error: No se encontró sesión de usuario")
                            continue
                    
                    # Validar que patient_id sea válido
                    if not patient_id or (isinstance(patient_id, str) and patient_id.strip() == ""):
                        await websocket.send_text("Error: patient_id inválido")
                        continue
                    
                    # Verificar si la sesión existe, si no, crearla automáticamente
                    if not session_service.get_session(patient_id):
                        print(f"Creando sesión automáticamente para patient_id: {patient_id}")
                        session_service.create_session(patient_id)
                    
                    audio_bytes = await process_chat_message(transcription, patient_id=patient_id)
                    current_result = session_service.get_session(patient_id)
                    
                    if current_result and "messages" in current_result:
                        messages = current_result["messages"]
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

