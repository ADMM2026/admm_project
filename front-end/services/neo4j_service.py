import streamlit as st
from services.api_client import get


@st.cache_data(ttl=60, show_spinner="Interrogazione relazioni geospaziali...")
def fetch_graph_relations(collection_type: str, document_id: str):
    try:
        if collection_type == "accommodations":
            data = get(f"/geo/accommodations/{document_id}/nearby-attractions")
            return data.get("nearby_attractions", [])
        data = get(f"/geo/attractions/{document_id}/cluster-analysis")
        return data.get("accommodation_hubs", [])
    except Exception:
        return "__TIMEOUT_OR_ERROR__"
