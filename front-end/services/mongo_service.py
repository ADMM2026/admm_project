"""
MongoDB service — dettaglio documenti e recensioni via back-end FastAPI.
Sostituisce la connessione diretta a MongoDB.
"""
import requests
from services.api_client import get, post, api_error_message


def get_detail(collection: str, doc_id: str) -> dict | None:
    """Recupera un documento completo da MongoDB tramite il back-end."""
    try:
        return get(f"/detail/{collection}/{doc_id}")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    except Exception:
        return None


def get_distinct_values(collection: str, field: str) -> list[str]:
    """
    Recupera valori distinti per un campo tramite Elasticsearch (field-values).
    Mantenuto per compatibilità; usa il back-end search.
    """
    try:
        data = get("/search/field-values", params={"index": collection, "field": field})
        return data.get("values", [])
    except Exception:
        return []


def add_review(
    collection: str,
    doc_id: str,
    username: str,
    rating: int,
    text: str,
) -> dict:
    """Aggiunge una recensione a un documento tramite il back-end."""
    review = post(f"/reviews/{collection}/{doc_id}", json={
        "username": username,
        "rating": rating,
        "text": text,
    })
    return review


def get_dashboard_stats() -> dict:
    """
    Statistiche aggregate per la dashboard manager.
    Delega al back-end /dashboard/stats.
    """
    return get("/dashboard/stats")


def get_map_data() -> dict:
    """
    Dati proiettati per la mappa Plotly.
    Delega al back-end /dashboard/map-data.
    Ritorna {'accommodations': [...], 'attractions': [...]}.
    """
    return get("/dashboard/map-data")
