"""
Pagina Manager — Dashboard statistiche.
KPI da MongoDB aggregations. Grafici InfluxDB: placeholder (prossimamente).
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.utils import load_css, require_login
from services import mongo_service

st.set_page_config(
    page_title="Piemonte Tourism — Dashboard",
    page_icon="📊",
    layout="wide",
)
load_css()
user = require_login(allowed_roles=["manager"])

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("Dashboard Manager")
    st.caption(f"Loggato come **{user['username']}**")
with col_logout:
    st.write("")
    if st.button("Esci", use_container_width=True):
        st.session_state.clear()
        st.switch_page("app.py")

st.markdown("---")

# ── Load stats ────────────────────────────────────────────────────────────────
with st.spinner("Caricamento statistiche…"):
    try:
        stats = mongo_service.get_dashboard_stats()
        load_error = None
    except Exception as e:
        stats = {}
        load_error = str(e)

if load_error:
    st.error(f"Errore caricamento statistiche MongoDB: {load_error}")
    st.stop()

# ── KPI cards row ─────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
kpis = [
    ("Attrazioni", stats.get("n_attractions", 0), "#34d399"),
    ("Alloggi", stats.get("n_accommodations", 0), "#a78bfa"),
    ("Utenti", stats.get("n_users", 0), "#60a5fa"),
    ("Recensioni", stats.get("n_reviews", 0), "#f59e0b"),
]
for col, (label, value, color) in zip([k1, k2, k3, k4], kpis):
    with col:
        st.markdown(
            f"""<div class="metric-card">
                  <div class="metric-label">{label}</div>
                  <div class="metric-value" style="color:{color}">{value:,}</div>
                </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Charts row 1 ──────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### Attrazioni per Provincia")
    data = stats.get("attractions_by_province", [])
    if data:
        df = pd.DataFrame(data).rename(columns={"_id": "Provincia", "count": "Numero"})
        df = df[df["Provincia"].notna() & (df["Provincia"] != "")]
        st.bar_chart(df.set_index("Provincia"), color="#34d399", height=320)
    else:
        st.caption("Nessun dato disponibile.")

with col_right:
    st.markdown("#### Alloggi per Provincia")
    data = stats.get("accommodations_by_province", [])
    if data:
        df = pd.DataFrame(data).rename(columns={"_id": "Provincia", "count": "Numero"})
        df = df[df["Provincia"].notna() & (df["Provincia"] != "")]
        st.bar_chart(df.set_index("Provincia"), color="#a78bfa", height=320)
    else:
        st.caption("Nessun dato disponibile.")

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Charts row 2 ──────────────────────────────────────────────────────────────
col_left2, col_right2 = st.columns(2)

with col_left2:
    st.markdown("#### Attrazioni per Categoria")
    data = stats.get("attractions_by_category", [])
    if data:
        df = pd.DataFrame(data).rename(columns={"_id": "Categoria", "count": "Numero"})
        df = df[df["Categoria"].notna() & (df["Categoria"] != "")]
        st.bar_chart(df.set_index("Categoria")["Numero"], color="#60a5fa", height=300)
    else:
        st.caption("Nessun dato disponibile.")

with col_right2:
    st.markdown("#### Media stelle per tipo struttura")
    data = stats.get("stars_by_type", [])
    if data:
        df = (
            pd.DataFrame(data)
            .rename(columns={"_id": "Tipo", "avg_stars": "Media stelle", "count": "N"})
        )
        df["Media stelle"] = df["Media stelle"].round(2)
        df = df[df["Tipo"].notna() & (df["Tipo"] != "")].head(10)
        st.bar_chart(df.set_index("Tipo")[["Media stelle"]], color="#f59e0b", height=300)
    else:
        st.caption("Nessun dato disponibile.")

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── InfluxDB placeholder ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### Metriche temporali")
st.markdown(
    """
    <div class="result-card" style="border-color:rgba(251,191,36,0.3);text-align:center;padding:2rem">
      <div style="font-size:1.5rem;font-weight:600;color:#94a3b8">In arrivo</div>
      <div class="result-name" style="margin-top:0.5rem">InfluxDB — Prossimamente</div>
      <p class="result-desc">
        I grafici temporali (recensioni nel tempo, ricerche per ora, accessi al sistema)
        saranno disponibili quando InfluxDB sara pronto.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
