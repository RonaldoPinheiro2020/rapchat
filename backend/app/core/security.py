# app/core/security.py
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext

# Configuração do contexto de criptografia para as senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configurações de segurança chaves (Em produção, carregar via variáveis de ambiente .env)
SECRET_KEY = os.getenv("SECRET_KEY", "SUA_CHAVE_SECRETA_SUPER_SECRETA_DO_RAPCHAT_PRO_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # O token expirará em 24 horas

def get_password_hash(password: str) -> str:
    """
    Gera o hash seguro da senha usando bcrypt.
    Substitui o bcrypt.hash() do Node.js.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha em texto plano coincide com o hash do banco de dados.
    Substitui o bcrypt.compare() do Node.js.
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    Gera um Token JWT assinado para o usuário autenticado.
    Substitui o jwt.sign() do Node.js.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # O payload carrega o ID ou o username do usuário ('sub') e a expiração ('exp')
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Union[str, None]:
    """
    Decodifica e valida o token JWT recebido no cabeçalho ou no WebSocket.
    Substitui a lógica de verificação do middleware do Node.js.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = payload.get("sub")
        if token_data is None:
            return None
        return token_data
    except Exception:
        return None