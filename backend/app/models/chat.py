# app/models/chat.py
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Table, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

# Tabela de associação para o relacionamento Muitos-para-Muitos entre Usuários e Conversas (Grupos)
conversation_members = Table(
    "conversation_members",
    Base.metadata,
    Column("conversation_id", String, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.datetime.utcnow)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    avatar = Column(String, nullable=True)
    status = Column(String, default="offline")  # online, offline
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    is_admin = Column(Boolean, default=False)

    # Relacionamentos
    messages_sent = relationship("Message", back_populates="sender")
    conversations = relationship("Conversation", secondary=conversation_members, back_populates="participants")
    reactions = relationship("Reaction", back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)  # UUID gerado no backend
    name = Column(String, nullable=True)  # Nulo se for chat privado (DM)
    type = Column(String, nullable=False)  # 'private' ou 'group'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relacionamentos
    participants = relationship("User", secondary=conversation_members, back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    
    # Suporte a Anexos/Arquivos
    file_path = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String, nullable=True)
    
    # Funcionalidades Avançadas do server.js
    reply_to = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)  # Resposta
    is_edited = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relacionamentos
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="messages_sent")
    reactions = relationship("Reaction", back_populates="message", cascade="all, delete-orphan")


class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String, nullable=False)  # O caractere do emoji

    # Relacionamentos
    message = relationship("Message", back_populates="reactions")
    user = relationship("User", back_populates="reactions")