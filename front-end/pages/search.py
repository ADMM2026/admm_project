import streamlit as st
import pandas as pd
from components.utils import load_css, require_login
from components.cards import render_attraction_card, render_accommodation_card
from components.filters import attraction_filters, accommodation_filters
from services.es_service import search_attractions, search_accommodations, count_index
from streamlit_folium import st_folium
import folium

st.set_page_config(
    page_title="Piemonte Turismo — Ricerca",
    page_icon="P",
    layout="wide",
)
load_css()
user = require_login(allowed_roles=["tourist"])

col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("Esplora il Piemonte")
    st.caption(f"Loggato come **{user['username']}**")
with col_logout:
    st.write("")
    if st.button("Esci", use_container_width=True):
        st.session_state.clear()
        st.switch_page("app.py")

st.divider()

index_choice = st.radio(
    "Tipo di ricerca",
    options=["Attrazioni", "Alloggi"],
    horizontal=True,
    label_visibility="collapsed",
    key="index_choice",
)
active_index = "attractions" if index_choice == "Attrazioni" else "accommodations"

if active_index == "attractions":
    filters = attraction_filters()
else:
    filters = accommodation_filters()

st.markdown("")

placeholder = (
    "Cerca per nome, categoria, localita, descrizione..."
    if active_index == "attractions"
    else "Cerca per nome, tipo struttura, localita..."
)
query = st.text_input(
    "Cerca",
    placeholder=placeholder,
    label_visibility="collapsed",
    key="search_query",
)

if "result_limit" not in st.session_state:
    st.session_state["result_limit"] = 10

current_search_state = f"{active_index}_{query}_{filters}"
if st.session_state.get("last_search_state") != current_search_state:
    st.session_state["result_limit"] = 10
    st.session_state["last_search_state"] = current_search_state

try:
    if active_index == "attractions":
        hits, total = search_attractions(
            text=query,
            provinces=filters["provinces"],
            categories=filters["categories"],
        )
    else:
        hits, total = search_accommodations(
            text=query,
            provinces=filters["provinces"],
            structure_types=filters["structure_types"],
            stars_range=filters["stars_range"],
        )
except Exception as e:
    st.error(f"Errore Elasticsearch: {e}")
    hits, total = [], 0

c1, c2 = st.columns(2)
with c1:
    st.markdown(
        f"""<div class="metric-card">
              <div class="metric-label">Risultati trovati</div>
              <div class="metric-value">{total}</div>
            </div>""",
        unsafe_allow_html=True,
    )
with c2:
    label = "Attrazioni nel DB" if active_index == "attractions" else "Alloggi nel DB"
    try:
        db_count = count_index(active_index)
    except Exception:
        db_count = "—"
    st.markdown(
        f"""<div class="metric-card">
              <div class="metric-label">{label}</div>
              <div class="metric-value">{db_count:,}</div>
            </div>""",
        unsafe_allow_html=True,
    )

st.markdown("")

def extract_geo(hits: list[dict]) -> list[dict]:
    rows = []
    for item in hits:
        coords = item.get("coordinates")
        if isinstance(coords, list) and len(coords) == 2:
            rows.append({"lat": float(coords[1]), "lon": float(coords[0])})
        elif isinstance(coords, dict):
            lat = coords.get("lat") or coords.get("latitude")
            lon = coords.get("lon") or coords.get("longitude")
            if lat and lon:
                rows.append({"lat": float(lat), "lon": float(lon)})
    return rows


if hits:
    col_map_view, col_cards = st.columns([3, 2])

    with col_map_view:
        st.markdown("<p class='map-title'>Mappa dei Risultati</p>", unsafe_allow_html=True)
        geo = extract_geo(hits)
        
        # Latitudine e Longitudine medie per centrare la mappa in base ai risultati
        if geo:
            df_geo = pd.DataFrame(geo)
            center_lat = df_geo["lat"].mean()
            center_lon = df_geo["lon"].mean()
            
            # Creiamo la mappa Folium coerente con la pagina details
            m_search = folium.Map(location=[center_lat, center_lon], zoom_start=9, control_scale=True)
            
            # Colore coerente: Verde per attrazioni, Rosso per alloggi
            marker_color = "green" if active_index == "attractions" else "red"
            marker_icon = "landmark" if active_index == "attractions" else "home"
            
            for item in hits:
                coords = item.get("coordinates")
                item_name = item.get("name", "Risultato")
                
                # Parsing sicuro delle coordinate del singolo hit
                lat, lon = None, None
                if isinstance(coords, list) and len(coords) == 2:
                    lon, lat = float(coords[0]), float(coords[1])
                elif isinstance(coords, dict):
                    lat = coords.get("lat") or coords.get("latitude")
                    lon = coords.get("lon") or coords.get("longitude")
                
                if lat and lon:
                    folium.Marker(
                        location=[float(lat), float(lon)],
                        tooltip=item_name,
                        icon=folium.Icon(color=marker_color, icon=marker_icon)
                    ).add_to(m_search)
            
            # Visualizzazione mappa senza intercettare click (solo overview)
            st_folium(m_search, width=700, height=500, key="search_global_map", returned_objects=[])
        else:
            # Fallback Piemonte se i risultati non hanno coordinate valide
            m_fallback = folium.Map(location=[45.07, 7.68], zoom_start=8)
            st_folium(m_fallback, width=700, height=500, key="search_fallback_map", returned_objects=[])
    with col_cards:
        limit = st.session_state["result_limit"]
        st.markdown(
            f"<p class='section-label'>Mostrando {len(hits)} di {total} risultati</p>",
            unsafe_allow_html=True,
        )
        render_fn = (
            render_attraction_card if active_index == "attractions" else render_accommodation_card
        )
        for i, item in enumerate(hits[:limit]):
            clicked = render_fn(item, i)
            if clicked:
                st.session_state["selected_item"] = item
                st.session_state["selected_collection"] = active_index
                st.switch_page("pages/details.py")
        
        if limit < total:
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            if st.button("Mostra altri risultati ⬇️", use_container_width=True):
                st.session_state["result_limit"] += 10
                st.rerun()

elif query.strip() or filters.get("provinces") or filters.get("categories") or filters.get("structure_types"):
    st.info("Nessun risultato trovato. Prova con termini diversi o rimuovi qualche filtro.")

else:
    col_map_view, col_info = st.columns([3, 2])
    with col_map_view:
        st.markdown("<p class='map-title'>Piemonte</p>", unsafe_allow_html=True)
        st.map(pd.DataFrame([{"lat": 45.07, "lon": 7.68}]), zoom=8)
    with col_info:
        st.markdown("")
        label = "attrazioni" if active_index == "attractions" else "alloggi"
        st.markdown(
            f"""<div class="result-card" style="border-color:rgba(167,139,250,0.3)">
                 <div class="result-name">Come iniziare</div>
                 <p class="result-desc">
                   Usa la barra di ricerca per trovare <strong>{label}</strong>
                   oppure seleziona filtri dal pannello laterale.<br><br>
                   Clicca su un risultato per vedere i dettagli e le recensioni.
                 </p>
               </div>""",
            unsafe_allow_html=True,
        )
