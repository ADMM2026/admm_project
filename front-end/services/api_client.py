import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEFAULT_TIMEOUT = 10


def get(endpoint: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def post(endpoint: str, json: dict | None = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    resp = requests.post(url, json=json, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def api_error_message(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            return exc.response.json().get("detail", str(exc))
        except Exception:
            return exc.response.text or str(exc)
    return str(exc)
