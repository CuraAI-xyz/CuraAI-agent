import time
import logging
from core.agents import app_graph
from core.tools.audio_compat import assistant_response
from app.services.session_service import session_service

logger = logging.getLogger(__name__)

async def process_chat_message(user_input: str, patient_id: str):
    """
    Procesa un mensaje de chat y retorna el audio de respuesta
    """
    current_state = session_service.get_session(patient_id)
    
    if not current_state:
        raise ValueError("Usuario no inicializado")
    
    graph_input = {
        "query": user_input,
        "messages": current_state.get("messages", []),
        "name": current_state.get("name"),
        "surname": current_state.get("surname"),
        "sex": current_state.get("sex"),
        "patient_id": current_state.get("patient_id")
    }
    
    config = {"configurable": {"thread_id": patient_id}}
    
    t0 = time.perf_counter()
    result = app_graph.invoke(graph_input, config=config)
    t1 = time.perf_counter()
    
    session_service.update_session(
        patient_id,
        messages=result.get("messages", [])
    )
    
    if result.get("name"):
        session_service.update_session(patient_id, name=result["name"])
    if result.get("surname"):
        session_service.update_session(patient_id, surname=result["surname"])
    if result.get("sex"):
        session_service.update_session(patient_id, sex=result["sex"])
    
    audio_bytes = assistant_response(result["messages"][-1].content)
    
    t2 = time.perf_counter()
    logger.info(f"invoke: {t1-t0:.2f}s, tts: {t2-t1:.2f}s, total: {t2-t0:.2f}s")
    print("mensajes:", result["messages"])
    return audio_bytes

