import streamlit as st
import pandas as pd
from components.utils import load_css, require_login
from components.reviews import render_reviews, render_add_review_form
from services.mongo_service import get_details

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
    if st.button("⬅️ Torna alla ricerca", use_container_width=True):
        st.switch_page("pages/search.py")
with col_logout:
    if st.button("Esci", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.switch_page("app.py")

st.divider()

name = source.get("name", "N/D")
st.title(name)

loc = source.get("location", {})
if isinstance(loc, dict):
    mun = loc.get("municipality", "")
    prov = loc.get("province", "")
    st.markdown(
        f"""<p style="font-size: 1.15rem; color: #94a3b8; margin-top: -1rem;">
            📍 Località: <strong>{mun}</strong> ({prov})
        </p>""", 
        unsafe_allow_html=True
    )

st.markdown("")

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
        
        extra = source.get("extra_info")
        if extra:
            st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
            with st.expander("📊 Informazioni Tecniche / Aggiuntive"):
                st.json(extra)

    else:  
        st.markdown(f"### 🏨 Dettagli Struttura")
        
        stars = source.get("stars")
        if stars and str(stars).isdigit():
            stars_count = int(stars)
            stars_graphic = "⭐" * stars_count
            st.markdown(f"**Classificazione:** <span style='font-size:1.2rem;'>{stars_graphic}</span> ({stars_count} stelle)", unsafe_allow_html=True)
        else:
            st.markdown("**Classificazione:** —")
            
        st.markdown("<div style='margin-bottom:0.8rem'></div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Tipo struttura:** `{source.get('structure_type', '—')}`")
            st.markdown(f"**Settore:** {source.get('sector', '—')}")
        with c2:
            cap = source.get("capacity", {})
            if isinstance(cap, dict):
                st.markdown(f"🛏️ **Camere disponibili:** {cap.get('rooms', '—')}")
                st.markdown(f"👥 **Posti letto totali:** {cap.get('beds', '—')}")

        st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
        
        contacts = source.get("contacts", {})
        if isinstance(contacts, dict) and any(contacts.values()):
            st.markdown("📞 **Contatti e Recapiti:**")
            if contacts.get("phone"):
                st.markdown(f"- **Telefono:** {contacts['phone']}")
            if contacts.get("email"):
                st.markdown(f"- **Email:** [{contacts['email']}](mailto:{contacts['email']})")
            if contacts.get("website"):
                st.markdown(f"- **Sito web:** [{contacts['website']}]({contacts['website']})")

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    st.button(
        "🌐 Trova luoghi di interesse nelle vicinanze (prossimamente)",
        disabled=True,
        use_container_width=True,
        help="La funzionalità di analisi geospaziale su grafo tramite Neo4j sarà abilitata a breve.",
    )

with col_map:
    pos = source.get("position", {})
    coords = pos.get("coordinates") if isinstance(pos, dict) else None
    if coords and len(coords) == 2:
        st.markdown("<p class='map-title' style='margin-bottom:0.3rem; font-weight:600;'>Posizione Geografica</p>", unsafe_allow_html=True)
        df = pd.DataFrame([{"lat": float(coords[1]), "lon": float(coords[0])}])
        st.map(df, latitude="lat", longitude="lon", size=200, zoom=13)
    else:
        st.info("ℹ️ Coordinate geografiche non disponibili per la mappatura puntuale.")

image_url = source.get("image_url")
if image_url and str(image_url).strip() and image_url != "N/D":
    st.markdown("<div style='margin-top:2rem'></div>", unsafe_allow_html=True)
    _, col_img_center, _ = st.columns([1, 2, 1])  
    with col_img_center:
        st.image(image_url, use_container_width=True, caption=f"Galleria immagini: {name}")

st.divider()

st.subheader("💬 Recensioni degli Utenti")

reviews_list = source.get("reviews", []) if doc else source.get("reviews", [])
render_reviews(reviews_list)

st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

if doc_id:
    render_add_review_form(collection, doc_id, user["username"])
else:
    st.caption("⚠️ Impossibile inserire recensioni: identificativo del documento mancante.")