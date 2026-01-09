import time
import logging
from langchain_core.messages import HumanMessage
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
    
    config = {"configurable": {"thread_id": patient_id}}
    
    # Recuperar el estado previo del checkpointer de LangGraph
    snapshot = app_graph.get_state(config)
    checkpoint_messages = []
    if snapshot and snapshot.values:
        checkpoint_messages = snapshot.values.get("messages", [])
    
    # Sincronizar: usar el historial más largo entre session_service y checkpointer
    session_messages = current_state.get("messages", [])
    if len(session_messages) > len(checkpoint_messages):
        # Si session_service tiene más mensajes, usamos ese historial
        messages_to_use = session_messages
    else:
        # Si el checkpointer tiene más mensajes (o están iguales), usamos ese
        messages_to_use = checkpoint_messages
    
    # Agregar el nuevo mensaje del usuario al historial
    new_user_message = HumanMessage(content=user_input)
    messages_with_new = messages_to_use + [new_user_message]
    
    graph_input = {
        "query": user_input,
        "messages": messages_with_new,
        "name": current_state.get("name"),
        "surname": current_state.get("surname"),
        "sex": current_state.get("sex"),
        "patient_id": current_state.get("patient_id")
    }
    
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

