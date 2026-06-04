"""
Neo4j service — ricerca luoghi vicini via back-end FastAPI (stub).
Sostituisce lo stub locale. Ritornerà dati reali quando Neo4j sarà attivo.
"""
from services.api_client import get


def is_available() -> bool:
    """Ritorna True quando Neo4j è connesso e pronto."""
    try:
        data = get("/nearby/health")
        return data.get("available", False)
    except Exception:
        return False


def find_nearby(
    doc_id: str,
    source_type: str,   # 'attraction' | 'accommodation'
    target_type: str,   # 'attraction' | 'accommodation'
    radius_km: float = 5.0,
    limit: int = 10,
) -> list[dict]:
    """
    Ritorna i POI vicini entro radius_km.
    STUB: ritorna sempre lista vuota finché Neo4j non è attivo.
    """
    try:
        data = get(f"/nearby/{doc_id}", params={
            "source_type": source_type,
            "target_type": target_type,
            "radius_km": radius_km,
            "limit": limit,
        })
        return data.get("results", [])
    except Exception:
        return []
