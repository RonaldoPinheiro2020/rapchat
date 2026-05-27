# main.py
import os
import shutil
import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="RAPchat Pro Python API", version="0.1.0")

# Permitir CORS igual ao Node.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mudar para a origem do config em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Criar pasta de upload se não existir
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==================== SCHEMAS PYDANTIC ====================
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class CreateConversationRequest(BaseModel):
    name: Optional[str] = None
    type: str  # 'private' ou 'group'
    participants: List[int]

class SendMessageRequest(BaseModel):
    content: str
    replyTo: Optional[int] = None

# ==================== GERENCIADOR DE WEBSOCKETS (SOCKET.IO EQUIVALENT) ====================
class ConnectionManager:
    def __init__(self):
        # Mapeia userId para a conexão ativa do WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # Mapeia room_id (conversationId) para uma lista de WebSockets presentes nela
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def join_room(self, conversation_id: str, websocket: WebSocket):
        if conversation_id not in self.rooms:
            self.rooms[conversation_id] = []
        if websocket not in self.rooms[conversation_id]:
            self.rooms[conversation_id].append(websocket)

    async def leave_room(self, conversation_id: str, websocket: WebSocket):
        if conversation_id in self.rooms and websocket in self.rooms[conversation_id]:
            self.rooms[conversation_id].remove(websocket)

    async def send_to_room(self, conversation_id: str, message: dict):
        if conversation_id in self.rooms:
            for connection in self.rooms[conversation_id]:
                await connection.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

# ==================== ROTAS DE AUTENTICAÇÃO ====================
@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    # TODO: Integrar com a tabela de usuários
    return {"token": "mock-jwt-token-python", "user": {"id": 1, "username": payload.username}}

@app.post("/api/auth/register", status_code=201)
async def register(payload: RegisterRequest):
    return {"message": "Usuário registrado com sucesso"}

@app.get("/api/users")
async def list_users():
    # Retorna os usuários do banco igual à query SQL do Node
    return [{"id": 1, "username": "admin", "status": "online", "avatar": None}]

# ==================== ROTAS DE CONVERSAS ====================
@app.get("/api/conversations")
async def get_conversations():
    return []

@app.post("/api/conversations", status_code=201)
async def create_conversation(payload: CreateConversationRequest):
    return {"id": "conv-123", "type": payload.type, "name": payload.name}

# ==================== ROTAS DE MENSAGENS ====================
@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = 50, offset: int = 0):
    return []

@app.post("/api/conversations/{conversation_id}/messages", status_code=201)
async def send_message(conversation_id: str, payload: SendMessageRequest):
    message_data = {
        "id": 999,
        "conversationId": conversation_id,
        "sender_id": 1,
        "content": payload.content,
        "replyTo": payload.replyTo,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    # Emite em tempo real para a sala igual ao io.to().emit()
    await manager.send_to_room(conversation_id, {"event": "new_message", "data": message_data})
    return message_data

# ==================== ARQUIVOS E UPLOAD ====================
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    import uuid
    unique_filename = f"{uuid.uuid4()}-{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "file_path": f"/uploads/{unique_filename}",
        "file_name": file.filename,
        "file_size": os.path.getsize(file_path),
        "file_type": file.content_type
    }

# Servir os arquivos carregados e a pasta do frontend
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

# ==================== PROTOCOLO WEBSOCKET REAL-TIME ====================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_id = None
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            payload = data.get("payload", {})

            # Evento 1: Autenticação do Socket
            if event == "authenticate":
                token = payload.get("token")
                # Validação de token simulada (Pegaremos o user_id do token)
                user_id = 1  
                await manager.connect(websocket, user_id)
                await manager.broadcast({"event": "user_status_changed", "data": {"userId": user_id, "status": "online"}})
                await websocket.send_json({"event": "authenticated", "payload": {"user": {"id": user_id, "username": "Ronaldo"}}})

            # Evento 2: Entrar na Sala (Canal/Conversa)
            elif event == "join_conversation":
                conv_id = payload.get("conversationId")
                await manager.join_room(conv_id, websocket)
                await manager.send_to_room(conv_id, {"event": "user_joined", "data": {"userId": user_id}})

            # Evento 3: Indicador de Digitação
            elif event == "typing":
                conv_id = payload.get("conversationId")
                await manager.send_to_room(conv_id, {"event": "user_typing", "data": {"userId": user_id, "conversationId": conv_id}})

            # Evento 4: Parar de Digitar
            elif event == "stop_typing":
                conv_id = payload.get("conversationId")
                await manager.send_to_room(conv_id, {"event": "user_stop_typing", "data": {"userId": user_id, "conversationId": conv_id}})

    except WebSocketDisconnect:
        if user_id:
            manager.disconnect(user_id)
            await manager.broadcast({"event": "user_status_changed", "data": {"userId": user_id, "status": "offline"}})