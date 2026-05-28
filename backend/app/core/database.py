import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define o caminho do banco SQLite local na raiz do backend
DATABASE_URL = "sqlite:///./rapchat.db"

# Cria o motor do banco de dados
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Cria a fábrica de sessões para as rotas do FastAPI
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe base que os nossos modelos (User, Message) vão herdar
Base = declarative_base()

# Função utilitária (Dependency Injection) para abrir e fechar conexões nas rotas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()