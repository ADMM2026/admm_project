"""
Filtri sidebar per attrazioni e alloggi.
"""
import streamlit as st
from services.mongo_service import get_distinct_values


def attraction_filters() -> dict:
    """Filtri sidebar per attrazioni. Ritorna { provinces, categories }."""
    st.sidebar.markdown("### Filtri")

    provinces = st.sidebar.multiselect(
        "Provincia",
        options=get_distinct_values("attractions", "location.province"),
        placeholder="Tutte",
        key="att_provinces",
    )
    categories = st.sidebar.multiselect(
        "Categoria",
        options=get_distinct_values("attractions", "category"),
        placeholder="Tutte",
        key="att_categories",
    )
    return {"provinces": provinces, "categories": categories}


def accommodation_filters() -> dict:
    """Filtri sidebar per alloggi. Ritorna { provinces, structure_types, stars_range }."""
    st.sidebar.markdown("### Filtri")

    provinces = st.sidebar.multiselect(
        "Provincia",
        options=get_distinct_values("accommodations", "location.province"),
        placeholder="Tutte",
        key="acc_provinces",
    )
    structure_types = st.sidebar.multiselect(
        "Tipo struttura",
        options=get_distinct_values("accommodations", "structure_type"),
        placeholder="Tutti",
        key="acc_types",
    )
    stars_range = st.sidebar.slider(
        "Stelle (min - max)",
        min_value=1,
        max_value=5,
        value=(1, 5),
        key="acc_stars",
    )
    return {
        "provinces": provinces,
        "structure_types": structure_types,
        "stars_range": stars_range,
    }
