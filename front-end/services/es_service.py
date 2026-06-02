"""
Elasticsearch service — search queries for attractions and accommodations.
"""
import os
import urllib3
import streamlit as st
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@st.cache_resource
def get_es() -> Elasticsearch:
    return Elasticsearch(
        [os.getenv("ES_HOST", "http://localhost:9200")],
        basic_auth=(
            os.getenv("ES_USER", "elastic"),
            os.getenv("ES_PASSWORD", "changeme"),
        ),
        verify_certs=False,
    )


@st.cache_data(ttl=300)
def get_field_values(index: str, field: str) -> list[str]:
    """
    Return sorted unique string values for a given field.
    Works for plain 'text' fields (no .keyword needed) by scanning up to 1000 docs.
    Supports nested fields via dot notation (e.g. 'location.province').
    """
    es = get_es()
    try:
        resp = es.search(
            index=index,
            body={"size": 1000, "query": {"match_all": {}}, "_source": [field]},
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
        return sorted(values)
    except Exception:
        return []


def _province_filter(provinces: list[str]) -> dict:
    return {
        "bool": {
            "should": [{"match": {"location.province": p}} for p in provinces],
            "minimum_should_match": 1,
        }
    }


def search_attractions(
    text: str,
    provinces: list[str],
    categories: list[str],
    limit: int = 100,
) -> tuple[list[dict], int]:
    """Search attractions index. Returns (hits, total)."""
    es = get_es()

    must: list[dict] = []
    filters: list[dict] = []

    if text.strip():
        must.append(
            {
                "multi_match": {
                    "query": text.strip(),
                    "fields": [
                        "name^4",
                        "category^3",
                        "location.municipality^2",
                        "location.province",
                        "description"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
        )
    else:
        must.append({"match_all": {}})

    if provinces:
        filters.append(_province_filter(provinces))

    if categories:
        filters.append(
            {
                "bool": {
                    "should": [{"match": {"category": c}} for c in categories],
                    "minimum_should_match": 1,
                }
            }
        )

    body = {
        "size": limit,
        "track_total_hits": True,
        "query": {"bool": {"must": must, "filter": filters}}
    }
    resp = es.search(index="attractions", body=body)
    hits = [h["_source"] | {"_id": h["_id"]} for h in resp["hits"]["hits"]]
    return hits, resp["hits"]["total"]["value"]


def search_accommodations(
    text: str,
    provinces: list[str],
    structure_types: list[str],
    stars_range: tuple[int, int] | None,
    limit: int = 100,
) -> tuple[list[dict], int]:
    """Search accommodations index. Returns (hits, total)."""
    es = get_es()

    must: list[dict] = []
    filters: list[dict] = []

    if text.strip():
        must.append(
            {
                "multi_match": {
                    "query": text.strip(),
                    "fields": [
                        "name^4",
                        "structure_type^3",
                        "sector^2",
                        "location.municipality^2",
                        "location.province"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        )
    else:
        must.append({"match_all": {}})

    if provinces:
        filters.append(_province_filter(provinces))

    if structure_types:
        filters.append(
            {
                "bool": {
                    "should": [{"match": {"structure_type": s}} for s in structure_types],
                    "minimum_should_match": 1,
                }
            }
        )

    if stars_range:
        min_s, max_s = stars_range
        if (min_s, max_s) != (1, 5):  # skip if full range (no filter needed)
            filters.append({"range": {"stars": {"gte": min_s, "lte": max_s}}})

    body = {
        "size": limit,
        "track_total_hits": True,
        "query": {"bool": {"must": must, "filter": filters}}
    }
    resp = es.search(index="accommodations", body=body)
    hits = [h["_source"] | {"_id": h["_id"]} for h in resp["hits"]["hits"]]
    return hits, resp["hits"]["total"]["value"]


def count_index(index: str) -> int:
    try:
        return get_es().count(index=index)["count"]
    except Exception:
        return 0
