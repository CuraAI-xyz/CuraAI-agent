from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from agent import create_agent
from ocr import read_image

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ocr")
async def ocr(image: UploadFile = File(...)):
    image_bytes = await image.read() 
    result = read_image(image_bytes)
    return result

@app.get("/start_agent")
def start_agent():
    """Inicializa una instancia del agente y la guarda en app.state."""
    app.state.agent = create_agent()
    return {"status": "agent_started"}

@app.get("/stop_agent")
def stop_agent():
    """Detiene el agente."""
    app.state.agent = None
    return {"status": "agent_stopped"}

@app.post("/conversation")
async def conversation(payload: dict = Body(...)):
    """Usa el agente ya inicializado para responder un mensaje del usuario.

    Espera JSON: { "input": "mensaje del usuario" }
    """
    if not hasattr(app.state, "agent") or app.state.agent is None:
        raise HTTPException(status_code=400, detail="Agent not started. Call /start_agent first.")

    user_input = payload.get("input", "")
    if not user_input:
        raise HTTPException(status_code=422, detail="Field 'input' is required and must be non-empty.")

    result = app.state.agent.invoke({"input": user_input})
    return {"output": result.get("output", "")}


#tidal    