"""
Pagina dettaglio — mostrata dopo aver cliccato "Vedi dettagli" dalla ricerca.
Legge l'item selezionato da st.session_state, recupera il documento completo
da MongoDB e permette di aggiungere recensioni.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.utils import load_css, require_login
from components.reviews import render_reviews, render_add_review_form
from services import mongo_service, neo4j_service

st.set_page_config(
    page_title="Piemonte Tourism — Dettaglio",
    page_icon="P",
    layout="wide",
)
load_css()
user = require_login(allowed_roles=["tourist"])

# ── Recupera l'item selezionato dalla ricerca ──────────────────────────────────
item = st.session_state.get("selected_item")
collection = st.session_state.get("selected_collection")

if not item or not collection:
    st.warning("Nessun elemento selezionato. Torna alla ricerca.")
    if st.button("Torna alla ricerca"):
        st.switch_page("pages/ricerca.py")
    st.stop()

# ── Recupera documento completo da MongoDB ────────────────────────────────────
doc_id = item.get("_id", "")
doc = mongo_service.get_detail(collection, doc_id) if doc_id else None
source = doc if doc else item  # fallback ai dati ES se MongoDB non risponde

# ── Header + bottone indietro ─────────────────────────────────────────────────
col_back, col_logout = st.columns([5, 1])
with col_back:
    if st.button("Torna alla ricerca"):
        st.switch_page("pages/ricerca.py")
with col_logout:
    st.write("")
    if st.button("Esci", use_container_width=True):
        st.session_state.clear()
        st.switch_page("app.py")

st.divider()

# ── Titolo e tipo ─────────────────────────────────────────────────────────────
name = source.get("name", "N/D")
st.title(name)

loc = source.get("location", {})
if isinstance(loc, dict):
    mun = loc.get("municipality", "")
    prov = loc.get("province", "")
    st.caption(f"Localita: {mun} ({prov})")

st.markdown("")

# ── Layout: info a sinistra, mappa a destra ───────────────────────────────────
col_info, col_map = st.columns([3, 2])

with col_info:
    if collection == "attractions":
        st.markdown(f"**Categoria:** {source.get('category', '—')}")
        desc = source.get("description", "")
        if desc:
            st.markdown("**Descrizione:**")
            st.markdown(desc)
        extra = source.get("extra_info")
        if extra:
            with st.expander("Informazioni aggiuntive"):
                st.json(extra)

    else:  # accommodations
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Tipo struttura:** {source.get('structure_type', '—')}")
            st.markdown(f"**Settore:** {source.get('sector', '—')}")
            stars = source.get("stars")
            if stars:
                st.markdown(f"**Stelle:** {int(stars)} / 5")
        with col2:
            cap = source.get("capacity", {})
            if isinstance(cap, dict):
                st.markdown(f"**Camere:** {cap.get('rooms', '—')}")
                st.markdown(f"**Letti:** {cap.get('beds', '—')}")

        contacts = source.get("contacts", {})
        if isinstance(contacts, dict) and any(contacts.values()):
            st.markdown("**Contatti:**")
            if contacts.get("phone"):
                st.markdown(f"- Telefono: {contacts['phone']}")
            if contacts.get("email"):
                st.markdown(f"- Email: {contacts['email']}")
            if contacts.get("website"):
                st.markdown(f"- Sito web: {contacts['website']}")

    st.markdown("")

    # ── Trova vicini (placeholder Neo4j) ──────────────────────────────────────
    if neo4j_service.is_available():
        if st.button("Trova luoghi vicini", use_container_width=True, type="primary"):
            target = "accommodation" if collection == "attractions" else "attraction"
            nearby = neo4j_service.find_nearby(doc_id, collection, target)
            st.write(nearby)
    else:
        st.button(
            "Trova luoghi vicini  (prossimamente)",
            disabled=True,
            use_container_width=True,
            help="Funzionalita Neo4j in arrivo.",
        )

with col_map:
    pos = source.get("position", {})
    coords = pos.get("coordinates") if isinstance(pos, dict) else None
    if coords and len(coords) == 2:
        df = pd.DataFrame([{"lat": float(coords[1]), "lon": float(coords[0])}])
        st.map(df, latitude="lat", longitude="lon", size=300, zoom=12)
    else:
        st.caption("Coordinate non disponibili.")

st.divider()

# ── Recensioni ────────────────────────────────────────────────────────────────
st.subheader("Recensioni")

# Recupera le recensioni aggiornate direttamente da MongoDB
if doc:
    reviews = doc.get("reviews", [])
else:
    reviews = source.get("reviews", [])

render_reviews(reviews)

st.markdown("")

# Form per aggiungere recensioni — disponibile per entrambe le collezioni.
# Per attractions, aggiunge il campo reviews se non esiste (via $push).
if doc_id:
    render_add_review_form(collection, doc_id, user["username"])
else:
    st.caption("Impossibile aggiungere recensioni: ID documento non trovato.")
