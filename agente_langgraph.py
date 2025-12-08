from tools import create_event_tool, get_events_tool, send_email, update_database, show_calendar
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from typing import TypedDict, List, Optional, Literal
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()

username_supabase = os.getenv("SUPABASE_USERNAME")
password_supabase = os.getenv("SUPABASE_PASSWORD")
DB_CONNECTION = f"postgresql://{username_supabase}:{password_supabase}@<host>:<port>/UsersData"

memory = MemorySaver()

class AgentState(TypedDict):
    name: Optional[str]        # Nombre del paciente (opcional)
    surname: str               # Apellido del paciente
    sex: str                   # Sexo biológico
    messages: List[BaseMessage]# Historial completo de la conversación (Human, AI, System, Tool)
    query: str                 # La consulta actual del usuario en texto plano
    patient_id: str            # ID único del paciente
    #med_insurance: str         # Obra social o seguro médico
    #birthday: str              # Fecha de nacimiento
    #resume: str                # Resumen clínico o de la interacción
    #email_sent: bool = False           # Flag para evitar múltiples envíos de email

class RouteDecision(BaseModel):
    decision: Literal["ir_a_mail", "ir_a_calendario", "responder_usuario"] = Field(
        ..., 
        description="La acción que debe tomar el agente basada en la conversación"
    )

# Función auxiliar para filtrar mensajes técnicos antes de pasar el historial al LLM
def clean_messages(messages):
    return [
        m for m in messages 
        if not isinstance(m, ToolMessage) 
    ]

class ExtractedInfo(BaseModel):
    """Información extraída de la conversación del paciente"""
    name: Optional[str] = Field(None, description="Nombre del paciente si se menciona")
    surname: Optional[str] = Field(None, description="Apellido del paciente si se menciona")
    sex: Optional[str] = Field(None, description="Sexo biológico si se menciona")
    birthday: Optional[str] = Field(None, description="Fecha de nacimiento si se menciona")
    med_insurance: Optional[str] = Field(None, description="Obra social o seguro médico si se menciona")
    resume: Optional[str] = Field(None, description="Resumen de síntomas o situación clínica si se menciona")

llm = ChatOpenAI(model="gpt-3.5-turbo").bind_tools([send_email, update_database, show_calendar])
llm_extractor = ChatOpenAI(model="gpt-4o-mini").with_structured_output(ExtractedInfo)

# --- NODOS ---
# Nodo principal de conversación: procesa el input y genera respuesta
def conv_node(state: AgentState) -> AgentState:
    # Limpia el historial de mensajes de ejecuciones de herramientas previas
    cleaned = clean_messages(state.get("messages", []))
    
    # Agrega la consulta actual del usuario al historial limpio
    cleaned.append(HumanMessage(content=state["query"]))

    nombre_paciente = state.get("name", "")
    apellido_paciente = state.get("surname", "")
    sexo_paciente = state.get("sex", "")
    id_paciente = state.get("patient_id","")
    print("ID PACIENTE EN CONV NODE:", id_paciente, nombre_paciente)
    #fecha_nacimiento = state.get("birthday", "")
    #obra_social = state.get("med_insurance", "")
    #resumen_clinico = state.get("resume", "")

    sys_msg = SystemMessage(content=f"""
    Sos CuraAI, un asistente médico. Responde las consultas del paciente. Debes tener una charla amigable y empática con el paciente para obtener informacion sobre su situacion
    La respuesta debe tener como maximo tres oraciones.

    Informacion del paciente:
    - Nombre: {nombre_paciente}
    - Apellido: {apellido_paciente}
    - Sexo biológico: {sexo_paciente}
    - ID del paciente: {id_paciente}

    IMPORTANTE: Si el paciente se despide (dice 'gracias', 'chau', 'nos vemos', etc),
    debes responder calurosamente Y LUEGO invocar la herramienta send_email_tool
    con los datos que tengas del paciente. No debes hacer un diagnostico sobre los sintomas del paciente
    ni recomendar medicamentos. 
    
    si el paciente te lo pide podes utilizar la herramienta 'update_database' para actualizar su informacion en la base de datos. Le tenes que pasar como argumentos
    el id del paciente, el campo a actualizar y el nuevo valor. Utiliza los siguientes nombres de campos: nombre, apellido, sexo, obra_social, fecha_de_nacimiento

    Si el paciente menciona alguno de estos datos, extráelos:
    - name: Nombre del paciente
    - surname: Apellido del paciente
    - sex: Sexo biológico (masculino/femenino/otro)
    - birthday: Fecha de nacimiento (formato YYYY-MM-DD)
    - med_insurance: Obra social o seguro médico
    - resume: Resumen de síntomas o situación clínica
    """)

    response = llm.invoke([sys_msg] + cleaned)
    state["messages"] = cleaned

    extracting_prompt = SystemMessage(content=f"""
    Eres un extractor de información de pacientes. Tenes que leer la conversacion y extraer los siguientes datos si estan presentes:
    - name: Nombre del paciente
    - surname: Apellido del paciente
    - sex: Sexo biológico (masculino/femenino/otro)
    - birthday: Fecha de nacimiento (formato YYYY-MM-DD)
    - med_insurance: Obra social o seguro médico
    - resume: Resumen de síntomas o situación clínica
    Conversación: {state['messages']} """)

    extracted = llm_extractor.invoke([extracting_prompt])
        
    if extracted.name and not state.get("name"):
        state["name"] = extracted.name
    if extracted.surname and not state.get("surname"):
        state["surname"] = extracted.surname
    if extracted.sex and not state.get("sex"):
        state["sex"] = extracted.sex
    if extracted.birthday and not state.get("birthday"):
        state["birthday"] = extracted.birthday
    if extracted.med_insurance and not state.get("med_insurance"):
        state["med_insurance"] = extracted.med_insurance
    if extracted.resume:
        if state.get("resume"):
            state["resume"] += " " + extracted.resume
        else:
            state["resume"] = extracted.resume

    cleaned.append(response)
    return state

# Lógica auxiliar simple para verificar si el último mensaje pide usar una herramienta
def decide_for_tools(state: AgentState):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None): # Verifica si el atributo tool_calls tiene contenido
        return "tools"
    return "continue"

# Lógica de enrutamiento condicional después del nodo de conversación
def route_after_conv(state: AgentState):
    last = state["messages"][-1] 

    if state.get("email_sent", False):
        return "continue"

    # Si el LLM decidió llamar a una herramienta (ej. enviar email), ir al nodo 'tools'
    if getattr(last, "tool_calls", None):
        state["email_sent"] = True  # ✅ Marca que se enviará email
        return "tools"

    # Intentar parsear si el LLM devolvió un JSON de decisión (RouteDecision)
    try:
        decision = RouteDecision.model_validate_json(last.content)
        if decision.decision == "fin_conversacion":
            return "mail"
        else:
            return "continue"
    except:
        # Si falla el parseo, terminar el flujo por ahora
        return "continue"


# Nodo preconstruido de LangGraph que ejecuta las herramientas solicitadas por el LLM
tool_node = ToolNode([send_email, update_database, show_calendar])

# --- CONSTRUCCIÓN DEL GRAFO ---
builder = StateGraph(AgentState)

builder.add_node("conversational", conv_node) 
builder.add_node("tools", tool_node)         

# --- DEFINICIÓN DE FLUJO (ARISTAS) ---
builder.add_edge(START, "conversational")

# Aristas condicionales: desde 'conversational', decidir a dónde ir basado en 'route_after_conv'
builder.add_conditional_edges(
    "conversational",      # Nodo origen
    route_after_conv,      # Función evaluadora (router)
    {
        "tools": "tools",  # Si router devuelve 'tools', ir al nodo tools
        "continue": END    # Si router devuelve 'continue', terminar la ejecución
    }
)

builder.add_edge("tools", END)

app_graph = builder.compile(checkpointer=memory)

def test():
    while True:
        user_input = input("User: ")
        if user_input.lower() in ["exit", "quit", "salir"]:
            break
        
        config = {"configurable": {"thread_id": "patient_123"}}
        
        state_to_use = {
            "messages": [],
            "query": user_input,
            "email_sent": False
        }
        
        print("\n--- Ejecutando grafo ---")
        final_state = None
        for event in app_graph.stream(state_to_use, config=config):
            for node_name, node_state in event.items():
                final_state = node_state  
        
        if final_state:
            print("Assistant:", final_state["messages"][-1].content)

if __name__ == "__main__":
    test()            