from core.tools.agent_tools import create_event_tool, get_events_tool, send_email, update_database, show_calendar, search_doctors
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage, ToolMessage
from typing import TypedDict, List, Optional, Literal, Annotated
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from app.config.settings import settings

memory = MemorySaver()

class AgentState(TypedDict):
    name: Optional[str]
    surname: str
    sex: str
    # Usamos add_messages para mantener el historial completo (necesario para el loop de herramientas)
    messages: Annotated[List[BaseMessage], add_messages]
    query: str
    patient_id: str
    # Campos opcionales para evitar errores de KeyError si no existen
    email_sent: Optional[bool]
    resume: Optional[str]
    birthday: Optional[str]
    med_insurance: Optional[str]
    med_calendly: Optional[str]

class RouteDecision(BaseModel):
    decision: Literal["ir_a_mail", "ir_a_calendario", "responder_usuario"] = Field(
        ..., 
        description="La acción que debe tomar el agente basada en la conversación"
    )

def clean_messages(messages):
    # Ya no filtramos ToolMessage, el agente necesita ver el resultado de las herramientas
    return messages

class ExtractedInfo(BaseModel):
    """Información extraída de la conversación del paciente"""
    name: Optional[str] = Field(None, description="Nombre del paciente si se menciona")
    surname: Optional[str] = Field(None, description="Apellido del paciente si se menciona")
    sex: Optional[str] = Field(None, description="Sexo biológico si se menciona")
    birthday: Optional[str] = Field(None, description="Fecha de nacimiento si se menciona")
    med_insurance: Optional[str] = Field(None, description="Obra social o seguro médico si se menciona")
    resume: Optional[str] = Field(None, description="Resumen de síntomas o situación clínica si se menciona")
    med_calendly: Optional[str] = Field(None, description="Enlace del calendly del medico deseado")
llm = ChatOpenAI(model="gpt-3.5-turbo").bind_tools([send_email, update_database, show_calendar, search_doctors])
llm_extractor = ChatOpenAI(model="gpt-4o-mini").with_structured_output(ExtractedInfo)

def conv_node(state: AgentState) -> AgentState:
    current_messages = state.get("messages", [])
    query = state.get("query", "")
    
    # Si no hay mensajes, crear el primer mensaje
    if not current_messages:
        messages_for_llm = [HumanMessage(content=query)]
    else:
        # Verificar si el último mensaje es el nuevo mensaje del usuario
        # Si no lo es, agregarlo al historial
        last_msg = current_messages[-1]
        if isinstance(last_msg, HumanMessage) and last_msg.content == query:
            # El mensaje ya está en el historial, usar todos los mensajes
            messages_for_llm = current_messages
        else:
            # El mensaje no está en el historial, agregarlo
            messages_for_llm = current_messages + [HumanMessage(content=query)]

    nombre_paciente = state.get("name", "")
    apellido_paciente = state.get("surname", "")
    sexo_paciente = state.get("sex", "")
    id_paciente = state.get("patient_id","")
    print("ID PACIENTE EN CONV NODE:", id_paciente, nombre_paciente)
    print(f"Total mensajes en historial: {len(messages_for_llm)}")
    print(f"Últimos 3 mensajes antes de LLM: {[type(m).__name__ for m in messages_for_llm[-3:]]}")

    sys_msg = SystemMessage(content=f"""
    Sos CuraAI, un asistente médico. Responde las consultas del paciente. Debes tener una charla amigable y empática con el paciente para obtener informacion sobre su situacion
    La respuesta debe tener como maximo tres oraciones.

    El objetivo de la charla es obtener informacion relevante sobre la salud del paciente y su situación clínica. Tenes que ir consultando cosas al paciente y repreguntar para profundizar
    en los temas que el paciente menciona. No debes ofrecer un diagnóstico ni recomendar medicamentos. No debes ofrecer enviar un mail al medico a menos que el paciente se despida.

    Informacion del paciente:
    - Nombre: {nombre_paciente}
    - Apellido: {apellido_paciente}
    - Sexo biológico: {sexo_paciente}
    - ID del paciente: {id_paciente}

    IMPORTANTE: Si el paciente se despide (dice 'gracias', 'chau', 'nos vemos', etc),
    debes responder calurosamente Y LUEGO invocar la herramienta send_email_tool
    con los datos que tengas del paciente. No debes hacer un diagnostico sobre los sintomas del paciente
    ni recomendar medicamentos. 

    
    Si el paciente quiere buscar medicos, utiliza la herramienta 'search_doctors' pasandole como argumentos la especialidad y la ubicacion. Ejemplo: search_doctors('Cardiologo', 'Mendoza, Argentina')
    Con la informacion que devuelve la herramienta 'search_doctors' tenes que generar una respuesta para ofrecerle al paciente los distintos medicos. NO debes responder con el json que devuelve la herramienta ni ofrecer enlaces
    IMPORTANTE: SOLO debes ofrecer los médicos que devuelve la herramienta search_doctors. NUNCA inventes médicos. Si ya ejecutaste la herramienta y recibiste resultados, úsalos. NO debes inventar nombres de médicos ni especialidades que no vinieron de la herramienta.
    Cuando la herramienta responda tenes que tomar del json el atributo 'calendly_url' del medico que quiere contactar el paciente y guardarlo en el estado como med_calendly
    NO debes ofrecer medicos sin usar la herramienta 'search_doctors'. No debes responder sin usar los medicos que te da la herramienta.

    si el paciente te lo pide podes utilizar la herramienta 'update_database' para actualizar su informacion en la base de datos. Le tenes que pasar como argumentos
    el id del paciente, el campo a actualizar y el nuevo valor. Utiliza los siguientes nombres de campos: nombre, apellido, sexo, obra_social, fecha_de_nacimiento

    Si el paciente menciona que quiere agendar una cita, utiliza la herramienta 'show_calendar' utilizando el enlace 'med_calendly' del medico seleccionado para mostrarle las fechas disponibles.

    Si el paciente menciona alguno de estos datos, extráelos:
    - name: Nombre del paciente
    - surname: Apellido del paciente
    - sex: Sexo biológico (masculino/femenino/otro)
    - birthday: Fecha de nacimiento (formato YYYY-MM-DD)
    - med_insurance: Obra social o seguro médico
    - resume: Resumen de síntomas o situación clínica
    - med_calendly: Enlace del calendly del medico deseado
    """)

    response = llm.invoke([sys_msg] + messages_for_llm)
    
    # Extraemos info (usamos los mensajes actuales para contexto)
    extracting_prompt = SystemMessage(content=f"""
    Eres un extractor de información de pacientes. Tenes que leer la conversacion y extraer los siguientes datos si estan presentes:
    - name: Nombre del paciente
    - surname: Apellido del paciente
    - sex: Sexo biológico (masculino/femenino/otro)
    - birthday: Fecha de nacimiento (formato YYYY-MM-DD)
    - med_insurance: Obra social o seguro médico
    - resume: Resumen de síntomas o situación clínica
    - med_calendly: Enlace del calendly del medico deseado
    Conversación: {messages_for_llm} """)

    extracted = llm_extractor.invoke([extracting_prompt])
    
    updates = {}
    if extracted.name and not state.get("name"): updates["name"] = extracted.name
    if extracted.surname and not state.get("surname"): updates["surname"] = extracted.surname
    if extracted.sex and not state.get("sex"): updates["sex"] = extracted.sex
    if extracted.med_calendly and not state.get("med_calendly"): updates["med_calendly"] = extracted.med_calendly
    if extracted.birthday and not state.get("birthday"): updates["birthday"] = extracted.birthday
    if extracted.med_insurance and not state.get("med_insurance"): updates["med_insurance"] = extracted.med_insurance
    if extracted.resume:
        if state.get("resume"):
            updates["resume"] = state["resume"] + " " + extracted.resume
        else:
            updates["resume"] = extracted.resume

    # Solo devolver la respuesta del asistente, el historial completo ya está en el estado
    # LangGraph con add_messages se encargará de agregar la respuesta al historial
    updates["messages"] = [response]
        
    return updates

def decide_for_tools(state: AgentState):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "continue"

def route_after_conv(state: AgentState):
    last = state["messages"][-1] 

    if state.get("email_sent", False):
        return "continue"

    if getattr(last, "tool_calls", None):
        return "tools"

    try:
        # Intentamos parsear decisión si es texto, pero priorizamos tool_calls
        decision = RouteDecision.model_validate_json(last.content)
        if decision.decision == "fin_conversacion":
            return "mail"
        else:
            return "continue"
    except:
        return "continue"

tool_node = ToolNode([send_email, update_database, show_calendar, search_doctors])

builder = StateGraph(AgentState)

builder.add_node("conversational", conv_node) 
builder.add_node("tools", tool_node)        

builder.add_edge(START, "conversational")

builder.add_conditional_edges(
    "conversational",
    route_after_conv,
    {
        "tools": "tools",
        "continue": END
    }
)

# CAMBIO CLAVE: De "tools" volvemos a "conversational" para que el LLM lea el output
builder.add_edge("tools", "conversational")

app_graph = builder.compile(checkpointer=memory)

def test():
    import pprint 

    print("Iniciando chat (escribe 'salir' para terminar)...")
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ["exit", "quit", "salir"]:
            break
        
        # ⚠️ Asegúrate de usar siempre el mismo thread_id para mantener la memoria
        config = {"configurable": {"thread_id": "patient_123"}}
        
        state_to_use = {
            "query": user_input,
            # Si es la primera vez, podrías necesitar pasar patient_id si no se extrae solo
            # "patient_id": "12345" 
        }
        
        print("\n--- ⚙️ Ejecutando grafo ---")
        
        # Ejecutamos el stream (esto hace que el agente piense y actúe)
        for event in app_graph.stream(state_to_use, config=config):
            pass # Solo dejamos que corra, no necesitamos capturar el evento parcial aquí
        
        # --- AQUÍ ESTÁ LA SOLUCIÓN ---
        # Pedimos a la memoria el estado ACTUAL COMPLETO después de toda la ejecución
        snapshot = app_graph.get_state(config)
        estado_completo = snapshot.values # .values tiene el diccionario AgentState completo
        
        if estado_completo:
            # 1. Imprimir la última respuesta del Asistente
            if "messages" in estado_completo and estado_completo["messages"]:
                last_msg = estado_completo["messages"][-1]
                print("\n💬 Assistant:", last_msg.content)
            
            # 2. Imprimir las variables del estado (Filtrando messages para que no moleste)
            print("\n🔍 [DEBUG] Variables en Memoria (AgentState):")
            
            # Creamos una copia para imprimir solo lo que nos interesa
            debug_view = estado_completo.copy()
            
            # Opcional: Quitamos los mensajes del print para ver bien las variables
            if 'messages' in debug_view:
                del debug_view['messages'] 
            
            pprint.pprint(debug_view)
            print("-" * 50)

if __name__ == "__main__":
    test()