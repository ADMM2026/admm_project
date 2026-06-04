"""
Auth service — Login e registrazione via back-end FastAPI.
Sostituisce la connessione diretta a MongoDB.
"""
import requests
from services.api_client import get, post, api_error_message


def login_user(username: str, password: str) -> tuple[dict | None, str]:
    """
    Autentica un utente tramite il back-end.
    Ritorna (user_dict, messaggio) in caso di successo,
    oppure (None, messaggio_errore) in caso di fallimento.
    """
    try:
        user = post("/auth/login", json={"username": username, "password": password})
        return user, "Login effettuato."
    except requests.HTTPError as e:
        return None, api_error_message(e)
    except Exception as e:
        return None, f"Errore di connessione al server: {e}"


def register_user(
    username: str, password: str, role: str, email: str = ""
) -> tuple[bool, str]:
    """
    Crea un nuovo account tramite il back-end.
    Ritorna (True, messaggio) in caso di successo,
    oppure (False, messaggio_errore) in caso di fallimento.
    """
    try:
        resp = post("/auth/register", json={
            "username": username,
            "password": password,
            "role": role,
            "email": email,
        })
        return True, resp.get("message", "Account creato con successo!")
    except requests.HTTPError as e:
        return False, api_error_message(e)
    except Exception as e:
        return False, f"Errore di connessione al server: {e}"
