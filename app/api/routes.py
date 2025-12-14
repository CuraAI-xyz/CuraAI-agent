from fastapi import FastAPI, WebSocket, Response, HTTPException, Request
from app.models.requests import UserIdRequest
from app.services.session_service import session_service
from app.services.chat_service import process_chat_message
from app.api.websocket_handler import handle_websocket_connection
import json
import logging

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI"""
    app = FastAPI()
    
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    logging.basicConfig(level=logging.INFO)
    
    @app.post("/userId")
    async def get_user_id(request: Request):
        try:
            body = await request.json()
            
            if "userId" not in body or not body["userId"]:
                raise HTTPException(status_code=422, detail="userId es requerido")
            
            user_id = body["userId"]
            name = body.get("name") or ""
            surname = body.get("surname") or ""
            sex = body.get("sex") or ""
            
            session_service.create_session(user_id, name, surname, sex)
            
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
        current_state = session_service.get_session(patient_id)
        
        if not current_state:
            return Response(content=b"Error: Usuario no inicializado", status_code=400)
        
        try:
            audio_bytes = await process_chat_message(user_input, patient_id)
            return Response(content=audio_bytes, media_type="audio/mp3")
        except Exception as e:
            logger.error(f"Error en chat_endpoint: {e}")
            return Response(content=b"Error procesando mensaje", status_code=500)

    @app.websocket("/audio")
    async def websocket_endpoint(websocket: WebSocket):
        await handle_websocket_connection(websocket)
    
    return app

