"""
Router Search — ricerca attrazioni e alloggi via Elasticsearch.
Endpoints:
    GET /search/attractions?text=...&provinces=...&categories=...&limit=100
    GET /search/accommodations?text=...&provinces=...&structure_types=...&stars_min=1&stars_max=5&limit=100
    GET /search/field-values?index=...&field=...
    GET /search/count?index=...
"""
import os
import urllib3
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()

# ── ES client ─────────────────────────────────────────────────────────────────
_es: Optional[Elasticsearch] = None


def _get_es() -> Elasticsearch:
    global _es
    if _es is None:
        _es = Elasticsearch(
            os.getenv("ES_HOST", "http://localhost:9200"),
            basic_auth=(
                os.getenv("ES_USER", "elastic"),
                os.getenv("ES_PASSWORD", "changeme"),
            ),
            verify_certs=False,
        )
    return _es


# ── Helpers ───────────────────────────────────────────────────────────────────
def _province_filter(provinces: list[str]) -> dict:
    return {
        "bool": {
            "should": [{"match": {"location.province": p}} for p in provinces],
            "minimum_should_match": 1,
        }
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/attractions")
def search_attractions(
    text: str = Query(""),
    provinces: list[str] = Query(default=[]),
    categories: list[str] = Query(default=[]),
    limit: int = Query(100, ge=1, le=1000),
):
    """Ricerca nel indice 'attractions' di Elasticsearch."""
    must: list[dict] = []
    filters: list[dict] = []

    if text.strip():
        must.append({
            "multi_match": {
                "query": text.strip(),
                "fields": ["name^4", "category^3", "location.municipality^2",
                           "location.province", "description"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        })
    else:
        must.append({"match_all": {}})

    if provinces:
        filters.append(_province_filter(provinces))

    if categories:
        filters.append({
            "bool": {
                "should": [{"match": {"category": c}} for c in categories],
                "minimum_should_match": 1,
            }
        })

    try:
        resp = _get_es().search(
            index="attractions",
            size=limit,
            track_total_hits=True,
            query={"bool": {"must": must, "filter": filters}},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Elasticsearch error: {e}")

    hits = [h["_source"] | {"_id": h["_id"]} for h in resp["hits"]["hits"]]
    return {"hits": hits, "total": resp["hits"]["total"]["value"]}


@router.get("/accommodations")
def search_accommodations(
    text: str = Query(""),
    provinces: list[str] = Query(default=[]),
    structure_types: list[str] = Query(default=[]),
    stars_min: int = Query(1, ge=1, le=5),
    stars_max: int = Query(5, ge=1, le=5),
    limit: int = Query(100, ge=1, le=1000),
):
    """Ricerca nel indice 'accommodations' di Elasticsearch."""
    must: list[dict] = []
    filters: list[dict] = []

    if text.strip():
        must.append({
            "multi_match": {
                "query": text.strip(),
                "fields": ["name^4", "structure_type^3", "sector^2",
                           "location.municipality^2", "location.province"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        })
    else:
        must.append({"match_all": {}})

    if provinces:
        filters.append(_province_filter(provinces))

    if structure_types:
        filters.append({
            "bool": {
                "should": [{"match": {"structure_type": s}} for s in structure_types],
                "minimum_should_match": 1,
            }
        })

    if (stars_min, stars_max) != (1, 5):
        filters.append({"range": {"stars": {"gte": stars_min, "lte": stars_max}}})

    try:
        resp = _get_es().search(
            index="accommodations",
            size=limit,
            track_total_hits=True,
            query={"bool": {"must": must, "filter": filters}},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Elasticsearch error: {e}")

    hits = [h["_source"] | {"_id": h["_id"]} for h in resp["hits"]["hits"]]
    return {"hits": hits, "total": resp["hits"]["total"]["value"]}


@router.get("/field-values")
def get_field_values(index: str = Query(...), field: str = Query(...)):
    """Restituisce i valori unici di un campo (per popolare i filtri)."""
    try:
        resp = _get_es().search(
            index=index,
            size=1000,
            query={"match_all": {}},
            source=[field],
        )
        values: set[str] = set()
        parts = field.split(".")
        for hit in resp["hits"]["hits"]:
            node = hit["_source"]
            for part in parts:
                if isinstance(node, dict):
                    node = node.get(part, "")
                else:
                    node = ""
                    break
            if node:
                values.add(str(node))
        return {"values": sorted(values)}
    except Exception:
        return {"values": []}


@router.get("/count")
def count_index(index: str = Query(...)):
    """Conta i documenti in un indice Elasticsearch."""
    try:
        return {"count": _get_es().count(index=index)["count"]}
    except Exception:
        return {"count": 0}
