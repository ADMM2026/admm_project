import streamlit as st
import folium
from streamlit_folium import st_folium
from components.utils import load_css, require_login, smart_button, smart_image
from components.reviews import render_reviews, render_add_review_form
from services.mongo_service import get_details
from services.neo4j_service import fetch_graph_relations
from services.api_client import BASE_URL

st.set_page_config(
    page_title="Piemonte Turismo — Dettagli",
    page_icon="P",
    layout="wide",
)
load_css()

user = require_login(allowed_roles=["tourist"])

item = st.session_state.get("selected_item")
collection = st.session_state.get("selected_collection")

if not item or not collection:
    st.warning("Nessun elemento selezionato o sessione scaduta. Torna alla barra di ricerca.")
    if st.button("Torna alla ricerca 🔍", type="primary"):
        st.switch_page("pages/search.py")
    st.stop()

doc_id = item.get("_id", "")
doc = get_details(collection, doc_id) if doc_id else None
source = doc if doc else item

col_back, col_space, col_logout = st.columns([1.5, 4, 1])
with col_back:
    if smart_button("⬅️ Torna alla ricerca"):
        st.switch_page("pages/search.py")
with col_logout:
    if smart_button("Esci", type="secondary"):
        st.session_state.clear()
        st.switch_page("app.py")

st.divider()

name = source.get("name", "N/D")
st.title(name)

loc = source.get("location", {})
if isinstance(loc, dict):
    st.markdown(
        f"""<p style="font-size: 1.15rem; color: #94a3b8; margin-top: -1rem;">
            📍 Località: <strong>{loc.get('municipality', '')}</strong> ({loc.get('province', '')})
        </p>""",
        unsafe_allow_html=True
    )

col_info, col_map = st.columns([1, 1])

with col_info:
    if collection == "attractions":
        st.markdown(f"### 🏛️ Informazioni Attrazione")
        st.markdown(f"**Categoria:** <span class='badge badge-blue'>{source.get('category', '—')}</span>", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:0.8rem'></div>", unsafe_allow_html=True)

        desc = source.get("description", "")
        if desc:
            st.markdown("**Descrizione:**")
            st.markdown(f"<div class='result-desc' style='font-size:1rem; max-height:none;'>{desc}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"### 🏨 Dettagli Struttura Ricettiva")
        stars = source.get("stars")
        if stars and str(stars).isdigit():
            st.markdown(f"**Classificazione:** <span style='font-size:1.2rem;'>{'⭐' * int(stars)}</span> ({stars} stelle)", unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom:0.8rem'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Tipo struttura:** `{source.get('structure_type', '—')}`")
            st.markdown(f"**Settore:** {source.get('sector', '—')}")
        with c2:
            cap = source.get("capacity", {})
            if isinstance(cap, dict):
                st.markdown(f"🛏️ **Camere:** {cap.get('rooms', '—')} | 👥 **Posti letto:** {cap.get('beds', '—')}")

        contacts = source.get("contacts", {})
        if isinstance(contacts, dict) and any(contacts.values()):
            st.markdown("<div style='margin-top:0.8rem'></div>", unsafe_allow_html=True)
            st.markdown("📞 **Contatti:**")
            if contacts.get("phone"): st.markdown(f"- **Tel:** {contacts['phone']}")
            if contacts.get("email"): st.markdown(f"- **Email:** {contacts['email']}")
            if contacts.get("website"): st.markdown(f"- **Sito:** [{contacts['website']}]({contacts['website']})")

with col_map:
    pos = source.get("position", {})
    coords = pos.get("coordinates") if isinstance(pos, dict) else None

    if coords and len(coords) == 2:
        center_lat, center_lon = float(coords[1]), float(coords[0])
        st.markdown("<p class='map-title' style='margin-bottom:0.3rem; font-weight:600;'>Mappa Geospaziale delle Relazioni</p>", unsafe_allow_html=True)

        m = folium.Map(location=[center_lat, center_lon], zoom_start=13, control_scale=True)
        graph_data = fetch_graph_relations(collection, doc_id) if doc_id else None

        if graph_data == "__TIMEOUT_OR_ERROR__":
            st.caption("⚠️ *Grafo Neo4j non raggiungibile o query in timeout. Mappa in modalità standard.*")
            graph_data = None

        marker_id_map = {}

        if collection == "accommodations":
            folium.Marker(
                location=[center_lat, center_lon],
                popup=f"<b>{name}</b><br>(Alloggio Corrente)",
                icon=folium.Icon(color="red", icon="home")
            ).add_to(m)

            if isinstance(graph_data, list):
                for att in graph_data:
                    att_id = att.get("id")
                    att_name = att.get("name", "Attrazione")
                    dist_km = att.get("distance_km", 0)
                    a_lat = att.get("latitude")
                    a_lon = att.get("longitude")

                    if a_lat and a_lon and att_id:
                        marker_id_map[f"{a_lat},{a_lon}"] = {"id": str(att_id), "collection": "attractions"}

                        tooltip_html = f"""
                        <div style="font-family: sans-serif; font-size: 0.9rem; padding: 4px; min-width: 160px;">
                            <strong style="color: #10b981;">🏛️ {att_name}</strong><br>
                            📏 Distanza: <b>{dist_km:.2f} km</b><br>
                            <span style="color: #64748b; font-size: 0.75rem; margin-top: 3px; display: inline-block;">
                                👆 <i>Clicca per aprire la scheda</i>
                            </span>
                        </div>
                        """

                        folium.Marker(
                            location=[a_lat, a_lon],
                            tooltip=folium.Tooltip(tooltip_html, permanent=False),
                            icon=folium.Icon(color="green", icon="landmark")
                        ).add_to(m)

                        folium.PolyLine(
                            locations=[[center_lat, center_lon], [a_lat, a_lon]],
                            color="#10b981", weight=2.5, opacity=0.8
                        ).add_to(m)

        else:
            folium.Marker(
                location=[center_lat, center_lon],
                popup=f"<b>{name}</b><br>(Attrazione Corrente)",
                icon=folium.Icon(color="green", icon="landmark")
            ).add_to(m)

            if isinstance(graph_data, list):
                for hub in graph_data:
                    acc_id = hub.get("accommodation_id")
                    acc_name = hub.get("accommodation_name", "Alloggio Hub")
                    a_lat = hub.get("latitude")
                    a_lon = hub.get("longitude")
                    alt_attractions = hub.get("alternative_attractions", [])

                    if a_lat and a_lon and acc_id:
                        marker_id_map[f"{a_lat},{a_lon}"] = {"id": str(acc_id), "collection": "accommodations"}

                        html_list = "".join([f"<li>{alt['name']} ({alt['distance_km']:.1f} km)</li>" for alt in alt_attractions[:3]])

                        tooltip_html = f"""
                        <div style="font-family: sans-serif; font-size: 0.9rem; padding: 4px; min-width: 200px;">
                            <strong style="color: #ef4444;">🏨 {acc_name}</strong><br>
                            <span style="font-size: 0.8rem; color: #64748b;">Vicino anche a:</span>
                            <ul style="margin: 3px 0; padding-left: 12px; font-size: 0.75rem; color: #334155;">{html_list}</ul>
                            <span style="color: #94a3b8; font-size: 0.75rem;">👆 <i>Clicca per aprire la scheda alloggio</i></span>
                        </div>
                        """

                        folium.Marker(
                            location=[a_lat, a_lon],
                            tooltip=folium.Tooltip(tooltip_html, permanent=False),
                            icon=folium.Icon(color="red", icon="home")
                        ).add_to(m)

                        folium.PolyLine(
                            locations=[[center_lat, center_lon], [a_lat, a_lon]],
                            color="#ef4444", weight=2.5, opacity=0.8
                        ).add_to(m)

        map_output = st_folium(m, width=700, height=430, returned_objects=["last_object_clicked"])

        if map_output and map_output.get("last_object_clicked"):
            click_coords = map_output["last_object_clicked"]
            c_lat, c_lng = click_coords.get("lat"), click_coords.get("lng")

            if c_lat and c_lng:
                matched_target = None
                for coords_key, target_info in marker_id_map.items():
                    lat_k, lon_k = map(float, coords_key.split(","))
                    if abs(lat_k - c_lat) < 0.0001 and abs(lon_k - c_lng) < 0.0001:
                        matched_target = target_info
                        break

                if matched_target:
                    new_doc = get_details(matched_target["collection"], matched_target["id"])
                    if new_doc:
                        st.session_state["selected_item"] = new_doc
                        st.session_state["selected_collection"] = matched_target["collection"]
                        st.slots = {}
                        st.rerun()
    else:
        st.info("ℹ️ Coordinate geografiche non disponibili per l'elemento corrente.")

img_field = source.get("image") or source.get("image_url")

if img_field and str(img_field).strip() and str(img_field) != "N/D" and "placeholder" not in str(img_field):
    if not str(img_field).startswith(("http://", "https://")):
        img_url_to_render = f"{BASE_URL}/static/images/{collection}/{img_field}"
    else:
        img_url_to_render = img_field

    st.markdown("<div style='margin-top:2rem'></div>", unsafe_allow_html=True)
    _, col_img_center, _ = st.columns([1.2, 1.6, 1.2])
    with col_img_center:
        smart_image(img_url_to_render, caption=f"{name}", output_format="auto")

st.divider()
st.subheader("💬 Recensioni degli Utenti")
reviews_list = source.get("last_reviews", [])
render_reviews(reviews_list)

st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
if doc_id:
    render_add_review_form(collection, doc_id, user["username"])
