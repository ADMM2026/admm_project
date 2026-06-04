"""
Router Auth — login e registrazione utenti via MongoDB.
Endpoints:
    POST /auth/login
    POST /auth/register
"""
import os
import bcrypt
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# ── DB helper ─────────────────────────────────────────────────────────────────
_client = None


def _get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        _client = MongoClient(uri)
    return _client[os.getenv("MONGO_DB_NAME", "Tourism")]


# ── Modelli Pydantic ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern="^(tourist|manager)$")
    email: str = ""


class UserResponse(BaseModel):
    username: str
    role: str
    email: str


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest):
    """Autentica un utente. Ritorna i dati utente serializzabili."""
    db = _get_db()
    user = db["users"].find_one({"username": body.username})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Username non trovato.")
    if not bcrypt.checkpw(body.password.encode("utf-8"), user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Password errata.")
    return UserResponse(
        username=user["username"],
        role=user["role"],
        email=user.get("email", ""),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    """Crea un nuovo account. Ritorna un messaggio di conferma."""
    db = _get_db()
    if db["users"].find_one({"username": body.username}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Username già in uso.")
    pw_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt())
    db["users"].insert_one({
        "username": body.username,
        "password_hash": pw_hash,
        "role": body.role,
        "email": body.email,
        "created_at": datetime.now(timezone.utc),
    })
    return {"message": "Account creato con successo!"}
