import requests
from services.api_client import post, api_error_message


def login_user(username: str, password: str) -> tuple[dict | None, str]:
    try:
        user = post("/auth/login", json={"username": username, "password": password})
        return user, "Login effettuato."
    except requests.HTTPError as e:
        return None, api_error_message(e)
    except Exception as e:
        return None, f"Errore di connessione al server: {e}"


def register_user(
    username: str, password: str, email: str = ""
) -> tuple[bool, str]:
    try:
        payload = {
            "username": username,
            "password": password,
        }
        if email.strip():
            payload["email"] = email.strip()
            
        resp = post("/auth/register", json=payload)
        return True, resp.get("message", "Account creato con successo!")
    except requests.HTTPError as e:
        return False, api_error_message(e)
    except Exception as e:
        return False, f"Errore di connessione al server: {e}"
