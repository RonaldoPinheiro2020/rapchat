# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.chat import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from app.core import security

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

# Define de onde o FastAPI vai extrair o token nas rotas protegidas
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login-form-api")

# Função auxiliar para obter o utilizador atual através do Token JWT (Middleware de Proteção)
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    username = security.verify_token(token)
    if username is None:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# ==================== ROTAS DE AUTENTICAÇÃO ====================

# 1. Registo de Novos Utilizadores
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Verificar se o utilizador já existe
    db_user = db.query(User).filter(User.username == user_data.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este nome de utilizador já está em uso.")
        
    db_email = db.query(User).filter(User.email == user_data.email).first()
    if db_email:
        raise HTTPException(status_code=400, detail="Este e-mail já está em uso.")

    # Criptografar a password e salvar no banco
    hashed_password = security.get_password_hash(user_data.password)
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        status="offline"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# 2. Login (Substitui o app.post('/api/auth/login') do Node)
@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    
    # Valida o utilizador e a password com Bcrypt
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador ou password incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Gera o token JWT para o frontend guardar
    access_token = security.create_access_token(subject=user.username)
    
    return {
        "token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        }
    }


# 3. Verificar Token / Obter Perfil Atual (Substitui o app.get('/api/auth/me'))
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# 4. Rota Auxiliar para listagem geral de utilizadores (Substitui o app.get('/api/users'))
@router.get("/users", response_model=List[UserResponse])
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users