import streamlit as st
from services.mongo_service import get_field_values

def render_sidebar_header():
    st.sidebar.markdown(
        """
        <div style="padding: 0.5rem 0 1rem 0;">
            <h2 style="margin: 0; font-size: 1.4rem; color: #f8fafc; font-weight: 700;">🎛️ Filtri Analitici</h2>
            <p style="margin: 0; font-size: 0.85rem; color: #94a3b8;">Affina i risultati in tempo reale</p>
        </div>
        <hr style="margin-top: 0; margin-bottom: 1.5rem; border-color: rgba(148, 163, 184, 0.2);" />
        """,
        unsafe_allow_html=True
    )

def attraction_filters() -> dict:
    render_sidebar_header()

    provinces = st.sidebar.multiselect(
        "📍 Seleziona Province",
        options=get_field_values("attractions", "location.province"),
        placeholder="Tutte le province",
        key="att_provinces",
    )
    
    st.sidebar.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    categories = st.sidebar.multiselect(
        "🏛️ Categorie Attrazione",
        options=get_field_values("attractions", "category"),
        placeholder="Tutte le categorie",
        key="att_categories",
    )
    return {"provinces": provinces, "categories": categories}


def accommodation_filters() -> dict:
    render_sidebar_header()

    provinces = st.sidebar.multiselect(
        "📍 Seleziona Province",
        options=get_field_values("accommodations", "location.province"),
        placeholder="Tutte le province",
        key="acc_provinces",
    )
    
    st.sidebar.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    structure_types = st.sidebar.multiselect(
        "🏨 Tipologie Struttura",
        options=get_field_values("accommodations", "structure_type"),
        placeholder="Tutte le tipologie",
        key="acc_types",
    )
    
    st.sidebar.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    
    stars_range = st.sidebar.slider(
        "⭐ Classificazione Stelle",
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


def dashboard_manager_filters(df_acc, df_att) -> dict:
    render_sidebar_header()

    all_provinces = sorted(list(
        set(df_acc["province"].dropna().unique() if not df_acc.empty else []) |
        set(df_att["province"].dropna().unique() if not df_att.empty else [])
    ))
    
    selected_provinces = st.sidebar.multiselect(
        "📍 Filtra per Province", 
        options=all_provinces,
        default=[],
        placeholder="Tutte le province",
        key="dash_provinces"
    )

    st.sidebar.markdown("<hr style='border-color: rgba(148, 163, 184, 0.1); margin: 1.5rem 0;' />", unsafe_allow_html=True)

    available_types = sorted(df_acc["structure_type"].dropna().unique()) if not df_acc.empty else []
    selected_types = st.sidebar.multiselect(
        "🏨 Tipologia Struttura", 
        available_types, 
        default=available_types,
        placeholder="Nessuna tipologia scelta",
        key="dash_types"
    )

    st.sidebar.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    available_cats = sorted(df_att["category"].dropna().unique()) if not df_att.empty else []
    selected_cats = st.sidebar.multiselect(
        "🏛️ Categoria Attrazione", 
        available_cats, 
        default=available_cats,
        placeholder="Nessuna categoria scelta",
        key="dash_cats"
    )

    return {
        "provinces": selected_provinces, 
        "structure_types": selected_types,
        "categories": selected_cats
    }