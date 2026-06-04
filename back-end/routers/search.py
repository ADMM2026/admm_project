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

def get_aggregatable_field(es, index: str, field: str) -> str | None:
    """
    Restituisce il nome corretto del campo da usare nelle aggregazioni.
    
    Esempi:
    - category text + keyword -> category.keyword
    - city keyword -> city
    - price float -> price
    - description text senza keyword -> None
    """

    mapping = es.indices.get_mapping(index=index)

    index_mapping = mapping[index]["mappings"]["properties"]

    parts = field.split(".")
    node = index_mapping

    for part in parts:
        if part not in node:
            return None

        field_def = node[part]

        # Se non siamo ancora all'ultimo pezzo, scendiamo nelle properties
        if part != parts[-1]:
            if "properties" in field_def:
                node = field_def["properties"]
            else:
                return None

    field_type = field_def.get("type")

    # Caso 1: campo già aggregabile
    if field_type in ["keyword", "integer", "long", "float", "double", "date", "boolean"]:
        return field

    # Caso 2: campo text con sotto-campo keyword
    if field_type == "text":
        fields = field_def.get("fields", {})
        if "keyword" in fields and fields["keyword"].get("type") == "keyword":
            return f"{field}.keyword"

    # Caso 3: campo non aggregabile
    return None

@router.get("/field-values")
def get_field_values(index: str = Query(...), field: str = Query(...)):

    """Restituisce i valori unici di un campo per popolare i filtri."""

    print(f"Getting field values for index='{index}', field='{field}'")

    try:

        es = _get_es()

        agg_field = get_aggregatable_field(es, index, field)

        if agg_field is None:

            print(f"Field '{field}' is not aggregatable")

            return {"values": []}

        print(f"Using aggregation field: {agg_field}")

        resp = es.search(

            index=index,

            size=0,

            aggs={

                "unique_values": {

                    "terms": {

                        "field": agg_field,

                        "size": 10000

                    }

                }

            }

        )

        buckets = resp["aggregations"]["unique_values"]["buckets"]

        values = [bucket["key"] for bucket in buckets]

        print(f"Found values for field '{field}': {values}")

        return {"values": sorted(values)}

    except Exception as e:

        print("Error while getting field values:", e)

        return {"values": []}


@router.get("/count")
def count_index(index: str = Query(...)):
    """Conta i documenti in un indice Elasticsearch."""
    try:
        return {"count": _get_es().count(index=index)["count"]}
    except Exception:
        return {"count": 0}
