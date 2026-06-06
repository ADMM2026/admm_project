import streamlit as st
import requests
from services.api_client import get, post


def get_details(collection: str, doc_id: str) -> dict | None:
    try:
        return get(f"/details/{collection}/{doc_id}")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_field_values(index: str, field: str) -> list[str]:
    try:
        data = get("/search/field-values", params={"index": index, "field": field})
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
    review = post(f"/reviews/{collection}/{doc_id}", json={
        "username": username,
        "rating": rating,
        "text": text,
    })
    return review


def get_raw_data() -> dict:
    return get("/dashboard/raw-data")
