"""
API Client helper — configurazione base URL e chiamate HTTP verso il back-end FastAPI.

La variabile d'ambiente BACKEND_URL permette di sovrascrivere l'indirizzo
del back-end (utile in Docker o in produzione).
Default: http://localhost:8000
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# URL base del back-end FastAPI
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

# Timeout di default per le chiamate HTTP (secondi)
DEFAULT_TIMEOUT = 10


def get(endpoint: str, params: dict | None = None) -> dict:
    """
    Effettua una GET verso il back-end.
    Ritorna il JSON decodificato o solleva un'eccezione con il messaggio di errore.
    """
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def post(endpoint: str, json: dict | None = None) -> dict:
    """
    Effettua una POST verso il back-end.
    Ritorna il JSON decodificato o solleva un'eccezione con il messaggio di errore.
    """
    url = f"{BASE_URL}{endpoint}"
    resp = requests.post(url, json=json, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def api_error_message(exc: Exception) -> str:
    """Estrae un messaggio leggibile da un'eccezione requests."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            return exc.response.json().get("detail", str(exc))
        except Exception:
            return exc.response.text or str(exc)
    return str(exc)
