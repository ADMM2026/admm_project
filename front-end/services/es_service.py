"""
Elasticsearch service — ricerca attrazioni e alloggi via back-end FastAPI.
Sostituisce la connessione diretta a Elasticsearch.
"""
import streamlit as st
from services.api_client import get


@st.cache_data(ttl=300)
def get_field_values(index: str, field: str) -> list[str]:
    """Valori unici di un campo (per popolare i filtri sidebar)."""
    try:
        data = get("/search/field-values", params={"index": index, "field": field})
        return data.get("values", [])
    except Exception:
        return []


def search_attractions(
    text: str,
    provinces: list[str],
    categories: list[str],
    limit: int = 100,
) -> tuple[list[dict], int]:
    """Ricerca attrazioni. Ritorna (hits, total)."""
    params: dict = {"text": text, "limit": limit}
    # requests supporta liste come parametri multipli
    for p in provinces:
        params.setdefault("provinces", []).append(p)  # type: ignore[arg-type]
    for c in categories:
        params.setdefault("categories", []).append(c)  # type: ignore[arg-type]

    data = get("/search/attractions", params=params)
    return data.get("hits", []), data.get("total", 0)


def search_accommodations(
    text: str,
    provinces: list[str],
    structure_types: list[str],
    stars_range: tuple[int, int] | None,
    limit: int = 100,
) -> tuple[list[dict], int]:
    """Ricerca alloggi. Ritorna (hits, total)."""
    params: dict = {"text": text, "limit": limit}
    for p in provinces:
        params.setdefault("provinces", []).append(p)  # type: ignore[arg-type]
    for s in structure_types:
        params.setdefault("structure_types", []).append(s)  # type: ignore[arg-type]
    if stars_range:
        params["stars_min"] = stars_range[0]
        params["stars_max"] = stars_range[1]

    data = get("/search/accommodations", params=params)
    return data.get("hits", []), data.get("total", 0)


def count_index(index: str) -> int:
    """Conta i documenti in un indice Elasticsearch."""
    try:
        return get("/search/count", params={"index": index}).get("count", 0)
    except Exception:
        return 0
