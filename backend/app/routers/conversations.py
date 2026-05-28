# app/routers/conversations.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.chat import Conversation, Message, User
from app.routers.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/conversations", tags=["Conversas e Mensagens"])

# ==================== SCHEMAS PYDANTIC ====================
class ConversationCreate(BaseModel):
    name: Optional[str] = None  # Opcional se for chat privado ('private')
    type: str  # 'private' ou 'group'
    participants: List[int]  # Lista de IDs dos usuários participantes

class ConversationResponse(BaseModel):
    id: str
    name: Optional[str]
    type: str
    
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    sender_id: int
    content: Optional[str]
    file_path: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    file_type: Optional[str]
    reply_to: Optional[int]
    is_edited: bool
    timestamp: str

    class Config:
        from_attributes = True


# ==================== ROTAS DE CONVERSAS ====================

# 1. Listar todas as conversas que o usuário logado participa
@router.get("", response_model=List[ConversationResponse])
def get_user_conversations(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # O SQLAlchemy busca automaticamente na tabela associativa 'conversation_members'
    return current_user.conversations


# 2. Criar uma nova conversa (Grupo ou Chat Privado)
@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Garantir que o criador está na lista de participantes
    participant_ids = list(set(payload.participants + [current_user.id]))
    
    # Buscar os objetos User correspondentes no banco
    users = db.query(User).filter(User.id.in_(participant_ids)).all()
    if len(users) != len(participant_ids):
        raise HTTPException(status_code=400, detail="Um ou mais participantes informados não existem.")

    # Se for chat privado, validar se já existe uma conversa desse tipo entre os dois participantes
    if payload.type == "private" and len(participant_ids) == 2:
        # Busca se já existe conversa privada compartilhada por ambos
        existing_conv = db.query(Conversation).filter(
            Conversation.type == "private",
            Conversation.participants.contains(users[0]),
            Conversation.participants.contains(users[1])
        ).first()
        if existing_conv:
            return existing_conv

    # Criar nova conversa gerando um UUID como ID igual ao Node.js
    new_conversation = Conversation(
        id=str(uuid.uuid4()),
        name=payload.name if payload.type == "group" else None,
        type=payload.type,
        participants=users
    )
    
    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)
    return new_conversation


# 3. Buscar os detalhes de uma conversa específica por ID
@router.get("/{conversationId}", response_model=ConversationResponse)
def get_conversation_by_id(
    conversationId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(Conversation.id == conversationId).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        
    # Verificar se o usuário faz parte da conversa (ou se é admin)
    if current_user not in conversation.participants and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Você não tem permissão para acessar esta conversa.")
        
    return conversation


# ==================== ROTAS DE MENSAGENS / HISTÓRICO ====================

# 4. Listar o histórico de mensagens de uma conversa com paginação
@router.get("/{conversationId}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversationId: str,
    limit: int = Query(50, description="Quantidade de mensagens a retornar"),
    offset: int = Query(0, description="Ponto de partida para a paginação"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(Conversation.id == conversationId).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        
    # Validar acesso
    if current_user not in conversation.participants and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Você não tem acesso ao histórico desta conversa.")
        
    # Buscar mensagens ordenadas das mais antigas para as mais recentes (ou vice-versa dependendo do layout)
    messages = db.query(Message)\
        .filter(Message.conversation_id == conversationId)\
        .order_by(Message.timestamp.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
        
    # Inverter a ordem para o frontend receber em ordem cronológica de leitura
    messages.reverse()
    
    # Tratamento simples do formato de data para o JSON string esperado pelo frontend
    response = []
    for msg in messages:
        response.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "sender_id": msg.sender_id,
            "content": msg.content,
            "file_path": msg.file_path,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "file_type": msg.file_type,
            "reply_to": msg.reply_to,
            "is_edited": msg.is_edited,
            "timestamp": msg.timestamp.isoformat()
        })
        
    return response