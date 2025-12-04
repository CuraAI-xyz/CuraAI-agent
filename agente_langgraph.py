from typing import TypedDict, List, Optional, Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import ToolMessage
from tools import create_event_tool, get_events_tool, send_email 
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
import requests

# Carga las claves de API y configuraciones desde el archivo .env
load_dotenv()

memory = MemorySaver()

# Define la estructura de memoria (State) que compartiran todos los nodos del grafo
class AgentState(TypedDict):
    name: Optional[str]        # Nombre del paciente (opcional)
    surname: str               # Apellido del paciente
    sex: str                   # Sexo biológico
    messages: List[BaseMessage]# Historial completo de la conversación (Human, AI, System, Tool)
    query: str                 # La consulta actual del usuario en texto plano
    med_insurance: str         # Obra social o seguro médico
    birthday: str              # Fecha de nacimiento
    resume: str                # Resumen clínico o de la interacción
    email_sent: bool = False           # Flag para evitar múltiples envíos de email

class RouteDecision(BaseModel):
    decision: Literal["ir_a_mail", "ir_a_calendario", "responder_usuario"] = Field(
        ..., 
        description="La acción que debe tomar el agente basada en la conversación"
    )

# Función auxiliar para filtrar mensajes técnicos (ToolMessage) antes de pasar el historial al LLM
def clean_messages(messages):
    return [
        m for m in messages 
        if not isinstance(m, ToolMessage) # Elimina respuestas de herramientas para limpiar contexto
    ]


@tool("send_email_tool", description="Envia un mail al doctor cuando el paciente se despide")
def send_email_tool(name: str, surname: str, sex: str, birthday: str, resume: str, med_ins: str):
    try:
        send_email(
            name=name,
            surname=surname,
            sex=sex,
            birthday=birthday,
            resume=resume,
            med_ins=med_ins
        )
        # Retorna éxito al LLM para que sepa que la acción se completó
        return "continue"
    except Exception as e:
        # Retorna el error al LLM para que pueda informar al usuario si algo falló
        return f"❌ Error al enviar email: {str(e)}"
    

# Inicializa el modelo GPT-4o y le "enseña" que tiene disponible la herramienta send_email_tool
llm = ChatOpenAI(model="gpt-3.5-turbo").bind_tools([send_email_tool])

# --- NODOS ---
# Nodo principal de conversación: procesa el input y genera respuesta
def conv_node(state: AgentState) -> AgentState:
    # Limpia el historial de mensajes de ejecuciones de herramientas previas
    cleaned = clean_messages(state.get("messages", []))
    
    # Agrega la consulta actual del usuario al historial limpio
    cleaned.append(HumanMessage(content=state["query"]))

    # Define la personalidad y las reglas de negocio (Prompt del Sistema)
    sys_msg = SystemMessage(content="""
    Sos CuraAI, un asistente médico. Responde las consultas del paciente.
    IMPORTANTE: Si el paciente se despide (dice 'gracias', 'chau', 'nos vemos', etc),
    debes responder calurosamente Y LUEGO invocar la herramienta send_email_tool
    con los datos que tengas del paciente. No debes hacer un diagnostico sobre los sintomas del paciente
    ni recomendar medicamentos. Debes tener una charla amigable y empática con el paciente para obtener informacion sobre su situacion
    La respuesta debe tener como maximo tres oraciones
                            """)

    # Invoca al LLM pasando el System Message + el historial de conversación
    response = llm.invoke([sys_msg] + cleaned)
    
    # Agrega la respuesta del LLM (que puede ser texto o una llamada a herramienta) al historial
    cleaned.append(response)
    
    # Actualiza el estado con la nueva lista de mensajes
    state["messages"] = cleaned
    return state

# Nodo placeholder para lógica de calendario (actualmente no hace nada, solo pasa el estado)
def calendar_node(state: AgentState) -> AgentState:
    return state

# Lógica auxiliar simple para verificar si el último mensaje pide usar una herramienta
def decide_for_tools(state: AgentState):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None): # Verifica si el atributo tool_calls tiene contenido
        return "tools"
    return "continue"

# Lógica de enrutamiento condicional después del nodo de conversación
def route_after_conv(state: AgentState):
    last = state["messages"][-1] # Obtiene la última respuesta del LLM

    # ✅ Si ya se envió el email, no volver a tools
    if state.get("email_sent", False):
        return "continue"

    # Prioridad 1: Si el LLM decidió llamar a una herramienta (ej. enviar email), ir al nodo 'tools'
    if getattr(last, "tool_calls", None):
        state["email_sent"] = True  # ✅ Marca que se enviará email
        return "tools"

    # Prioridad 2: Intentar parsear si el LLM devolvió un JSON de decisión (RouteDecision)
    try:
        decision = RouteDecision.model_validate_json(last.content)
        # Si la decisión explícita es fin de conversación, redirigir a 'mail'
        if decision.decision == "fin_conversacion":
            return "mail"
        else:
            return "continue"
    except:
        # Si falla el parseo (es texto normal), terminar el flujo por ahora
        return "continue"


# Nodo preconstruido de LangGraph que ejecuta las herramientas solicitadas por el LLM
tool_node = ToolNode([send_email_tool])

# --- CONSTRUCCIÓN DEL GRAFO ---

# Inicializa el constructor del grafo tipado con AgentState
builder = StateGraph(AgentState)

# Agrega los nodos al grafo (las "estaciones" de trabajo)
builder.add_node("conversational", conv_node) # Nodo principal (LLM)
builder.add_node("tools", tool_node)          # Nodo ejecutor de herramientas

# --- DEFINICIÓN DE FLUJO (ARISTAS) ---

# Punto de entrada: Al iniciar, ir directo al nodo conversacional
builder.add_edge(START, "conversational")
# Después de ejecutar una herramienta, volver siempre al LLM para que interprete el resultado
builder.add_edge("tools", "conversational")

# Aristas condicionales: desde 'conversational', decidir a dónde ir basado en 'route_after_conv'
builder.add_conditional_edges(
    "conversational",      # Nodo origen
    route_after_conv,      # Función evaluadora (router)
    {
        "tools": "tools",  # Si router devuelve 'tools', ir al nodo tools
        "continue": END    # Si router devuelve 'continue', terminar la ejecución
    }
)

# ✅ IMPORTANTE: Después de ejecutar tools, TERMINA (no vuelve a conversational)
builder.add_edge("tools", END)

# Compila el grafo para convertirlo en una aplicación ejecutable
app_graph = builder.compile(checkpointer=memory)


""" while True:
    user_input = input("User: ")
    if user_input.lower() in ["exit", "quit", "salir"]:
        break
    
    config = {"configurable": {"thread_id": "patient_123"}}
    
    response = app_graph.invoke({
        "name": "Carlos",
        "surname": "Lopez",
        "sex": "masculino",
        "messages": [],
        "query": user_input,
        "med_insurance": "Swiss Medical",
        "birthday": "1990-08-25",
        "resume": "Paciente sin antecedentes relevantes.",
        "email_sent": False
    }, config=config)
    print("Assistant:", response["messages"][-1].content) """