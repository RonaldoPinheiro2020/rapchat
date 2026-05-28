# app/main.py
import os
import sys
import json
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import datetime

# Garante que o Python conheça a pasta 'backend' e a pasta 'app' não importa de onde o comando seja rodado
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import engine, Base, get_db
from app.core import security
from app.models.chat import User, Message, Conversation
from app.routers import auth, conversations


# 1. Inicializa o banco de dados criando as tabelas estruturadas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RAPchat Pro Backend", version="0.1.1")

# 2. Configuração de CORS (Alinhado com as permissões do Node.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, apontar para o domínio correto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Inclusão dos Roteadores HTTP criados nas etapas anteriores
app.include_router(auth.router)
app.include_router(conversations.router)

# 4. Gerenciador de Conexões WebSocket (Substitui o Socket.IO)
class ConnectionManager:
    def __init__(self):
        # Mapeia user_id para a conexão WebSocket ativa
        self.active_connections: Dict[int, WebSocket] = {}
        # Mapeia conversation_id para uma lista de WebSockets conectados na sala
        self.room_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def join_room(self, conversation_id: str, websocket: WebSocket):
        if conversation_id not in self.room_connections:
            self.room_connections[conversation_id] = []
        if websocket not in self.room_connections[conversation_id]:
            self.room_connections[conversation_id].append(websocket)

    async def leave_room(self, conversation_id: str, websocket: WebSocket):
        if conversation_id in self.room_connections and websocket in self.room_connections[conversation_id]:
            self.room_connections[conversation_id].remove(websocket)

    async def send_to_room(self, conversation_id: str, message: dict):
        """Envia uma mensagem para todos os membros ativos na sala (Equivalente ao io.to().emit())"""
        if conversation_id in self.room_connections:
            for connection in self.room_connections[conversation_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Remove conexões fantasmas/caídas que não dispararam o desconectar
                    self.room_connections[conversation_id].remove(connection)

    async def broadcast(self, message: dict):
        """Envia para todos os usuários globais do sistema (Equivalente ao io.emit())"""
        for user_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(user_id)

manager = ConnectionManager()


# ==================== CANAL DE COMUNICAÇÃO WEBSOCKET ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    current_user_id = None
    current_rooms: List[str] = []
    
    try:
        # Loop infinito mantendo o canal aberto para escutar o frontend
        while True:
            # O frontend enviará dados estruturados em JSON
            data = await websocket.receive_json()
            event = data.get("event")
            payload = data.get("payload", {})

            # EVENTO 1: Autenticação do Socket (Substitui socket.on('authenticate'))
            if event == "authenticate":
                token = payload.get("token")
                username = security.verify_token(token)
                
                if username:
                    user = db.query(User).filter(User.username == username).first()
                    if user:
                        current_user_id = user.id
                        await manager.connect(websocket, current_user_id)
                        
                        # Atualiza o status do usuário para online no banco
                        user.status = "online"
                        user.last_seen = datetime.datetime.utcnow()
                        db.commit()
                        
                        # Notifica a rede inteira que o usuário entrou
                        await manager.broadcast({
                            "event": "user_status_changed",
                            "data": {"userId": user.id, "status": "online"}
                        })
                        
                        # Confirma a autenticação com sucesso para a tela do usuário
                        await websocket.send_json({
                            "event": "authenticated",
                            "payload": {"user": {"id": user.id, "username": user.username}}
                        })
                else:
                    await websocket.send_json({"event": "authentication_error", "data": "Token Inválido"})
                    await websocket.close()
                    break

            # EVENTO 2: Entrar em uma Conversa/Sala (Substitui socket.on('join_conversation'))
            elif event == "join_conversation" and current_user_id:
                conversation_id = payload.get("conversationId")
                await manager.join_room(conversation_id, websocket)
                if conversation_id not in current_rooms:
                    current_rooms.append(conversation_id)
                
                # Avisa os outros membros da sala
                await manager.send_to_room(conversation_id, {
                    "event": "user_joined",
                    "data": {"userId": current_user_id, "conversationId": conversation_id}
                })

            # EVENTO 3: Usuário Digitando (Substitui socket.on('typing'))
            elif event == "typing" and current_user_id:
                conversation_id = payload.get("conversationId")
                await manager.send_to_room(conversation_id, {
                    "event": "user_typing",
                    "data": {"userId": current_user_id, "conversationId": conversation_id}
                })

            # EVENTO 4: Usuário Parou de Digitar (Substitui socket.on('stop_typing'))
            elif event == "stop_typing" and current_user_id:
                conversation_id = payload.get("conversationId")
                await manager.send_to_room(conversation_id, {
                    "event": "user_stop_typing",
                    "data": {"userId": current_user_id, "conversationId": conversation_id}
                })

    except WebSocketDisconnect:
        # Se o canal fechar (fechou aba, deslogou ou caiu a internet), limpa a memória
        if current_user_id:
            manager.disconnect(current_user_id)
            for room_id in current_rooms:
                await manager.leave_room(room_id, websocket)
            
            # Altera status do banco de dados para offline
            user = db.query(User).filter(User.id == current_user_id).first()
            if user:
                user.status = "offline"
                user.last_seen = datetime.datetime.utcnow()
                db.commit()
            
            # Notifica a rede da saída
            await manager.broadcast({
                "event": "user_status_changed",
                "data": {"userId": current_user_id, "status": "offline"}
            })

# ==================== MAPEAMENTO DE PASTA ESTÁTICA ====================

# Cria o mapeamento para uploads locais de arquivos/mídias
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Serve a pasta do frontend atual para renderizar o layout idêntico do cliente
# Certifique-se de mover a pasta frontend para o diretório correto correspondente
if os.path.exists("../frontend"):
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")