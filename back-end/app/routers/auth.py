from datetime import datetime, timezone
import bcrypt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from app.database import get_mongo

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6, description="La password deve essere di almeno 6 caratteri")
    email: EmailStr = Field("", description="Email opzionale del turista")


class UserResponse(BaseModel):
    username: str
    role: str
    email: str


@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest):
    db = get_mongo()
    user = db["users"].find_one({"username": body.username})
    
    if not user or not bcrypt.checkpw(body.password.encode("utf-8"), user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali errate."
        )
        
    return UserResponse(
        username=user["username"],
        role=user["role"],  
        email=user.get("email", ""),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    db = get_mongo()
    
    if db["users"].find_one({"username": body.username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username già in uso."
        )
        
    pw_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt())
    db["users"].insert_one({
        "username": body.username,
        "password_hash": pw_hash,
        "role": "tourist",  
        "email": body.email,
        "created_at": datetime.now(timezone.utc),
    })
    
    return {"message": "Account creato con successo!"}