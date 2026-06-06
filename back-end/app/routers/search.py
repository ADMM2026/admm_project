from fastapi import APIRouter, Query, HTTPException, status
from app.database import get_mongo, get_es

router = APIRouter()


def _province_filter(provinces: list[str]) -> dict:
    return {
        "bool": {
            "should": [{"match": {"location.province": p}} for p in provinces],
            "minimum_should_match": 1,
        }
    }


@router.get("/attractions")
def search_attractions(
    text: str = Query(""),
    provinces: list[str] = Query(default=[]),
    categories: list[str] = Query(default=[]),
    limit: int = Query(100, ge=1, le=1000),
):
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
        resp = get_es().search(
            index="attractions",
            size=limit,
            track_total_hits=True,
            query={"bool": {"must": must, "filter": filters}},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, 
            detail=f"Elasticsearch error: {e}"
        )

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
        resp = get_es().search(
            index="accommodations",
            size=limit,
            track_total_hits=True,
            query={"bool": {"must": must, "filter": filters}},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, 
            detail=f"Elasticsearch error: {e}"
        )

    hits = [h["_source"] | {"_id": h["_id"]} for h in resp["hits"]["hits"]]
    return {"hits": hits, "total": resp["hits"]["total"]["value"]}


@router.get("/field-values")
def get_field_values(index: str = Query(...), field: str = Query(...)):
    collection_map = {
        "accommodations": "accommodations",
        "attractions": "attractions"
    }
    collection_name = collection_map.get(index)
    if not collection_name:
        return {"values": []}
    try:
        db = get_mongo()
        distinct_values = db[collection_name].distinct(field)
        cleaned_values = [v for v in distinct_values if v is not None and str(v).strip() != ""]
        return {"values": sorted(cleaned_values)}
    except Exception as e:
        print(f"Error while getting field values from MongoDB for {index}.{field}: {e}")
        return {"values": []}


@router.get("/count")
def count_index(index: str = Query(...)):
    """Restituisce il numero totale di documenti indicizzati su Elasticsearch."""
    try:
        return {"count": get_es().count(index=index)["count"]}
    except Exception:
        return {"count": 0}