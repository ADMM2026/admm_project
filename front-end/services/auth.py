"""
Auth service — MongoDB Users collection.
Handles registration and login with bcrypt password hashing.
"""
import os
import bcrypt
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        _client = MongoClient(uri)
    return _client[os.getenv("MONGO_DB_NAME", "Tourism")]


def register_user(username: str, password: str, role: str, email: str = "") -> tuple[bool, str]:
    """
    Create a new user. Returns (success, message).
    role must be 'tourist' or 'manager'.
    """
    db = _get_db()
    users = db["users"]

    if users.find_one({"username": username}):
        return False, "Username già in uso."

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    users.insert_one(
        {
            "username": username,
            "password_hash": pw_hash,
            "role": role,
            "email": email,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return True, "Account creato con successo!"


def login_user(username: str, password: str) -> tuple[dict | None, str]:
    """
    Authenticate a user. Returns (user_doc, message).
    Returns (None, error_message) on failure.
    """
    db = _get_db()
    users = db["users"]

    user = users.find_one({"username": username})
    if not user:
        return None, "Username non trovato."

    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"]):
        # Return a serialisable dict (no binary password hash)
        return {
            "username": user["username"],
            "role": user["role"],
            "email": user.get("email", ""),
        }, "Login effettuato."

    return None, "Password errata."
