# app/schemas/auth.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    status: str
    avatar: Optional[str] = None
    is_admin: bool
    last_seen: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    token: str
    user: dict