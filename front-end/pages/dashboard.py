"""
Pagina Manager — Dashboard Completa ed Estesa.
Mantiene i filtri nativi, la mappa Plotly e i grafici dinamici del PoC originale,
protetta dallo scheletro di autenticazione e dai componenti del team.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from pymongo import MongoClient
import os
import sys
from pathlib import Path

# ── Integrazione Percorsi dello Scheletro ──────────────────────────────────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.utils import load_css, require_login
# Escludiamo l'uso di mongo_service per i grafici per evitare conflitti di attributi

# Configurazione della pagina ad ampio schermo (deve essere la prima istruzione Streamlit)
st.set_page_config(
    page_title="Piemonte Tourism — Dashboard",
    page_icon="📊",
    layout="wide",
)

# Caricamento dello stile globale e controllo dell'autenticazione del team
load_css()
user = require_login(allowed_roles=["manager"])

# ── Connessione Diretta a MongoDB via Variabili d'Ambiente ────────────────────
@st.cache_resource
def get_mongo_db():
    # Pesca direttamente dal file .env nella ROOT del progetto lanciato da fuori
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
    db_name = os.getenv("MONGO_DB_NAME", "Tourism")
    client = MongoClient(mongo_uri)
    return client[db_name]

db = get_mongo_db()

# ── Caricamento e Proiezione Dati Originale (Ottimizzato in RAM) ──────────────
@st.cache_data(ttl=60)  
def load_data():
    # Estrazione alloggi con proiezione dei soli campi utili (escludendo array pesanti)
    pipeline_acc = [
        {
            "$project": {
                "name": 1, "structure_type": 1, "sector": 1, "stars": 1,
                "municipality": "$location.municipality",
                "province": "$location.province",
                "rooms": "$capacity.rooms",
                "beds": "$capacity.beds",
                "lon": { "$arrayElemAt": ["$position.coordinates", 0] },
                "lat": { "$arrayElemAt": ["$position.coordinates", 1] }
            }
        }
    ]
    df_acc = pd.DataFrame(list(db.accommodations.aggregate(pipeline_acc)))
    if not df_acc.empty:
        df_acc["data_type"] = "Alloggio"
        df_acc["category"] = "N/A"
    
    # Estrazione attrazioni 
    pipeline_att = [
        {
            "$project": {
                "name": 1, "category": 1,
                "municipality": "$location.municipality",
                "province": "$location.province",
                "lon": { "$arrayElemAt": ["$position.coordinates", 0] },
                "lat": { "$arrayElemAt": ["$position.coordinates", 1] }
            }
        }
    ]
    df_att = pd.DataFrame(list(db.attractions.aggregate(pipeline_att)))
    if not df_att.empty:
        df_att["data_type"] = "Attrazione"
        df_att["structure_type"] = "N/A"
        df_att["stars"] = 0
        df_att["rooms"] = 0
        df_att["beds"] = 0

    return df_acc, df_att

with st.spinner("Caricamento componenti analitici da MongoDB…"):
    df_acc, df_att = load_data()

# ── Sidebar con i Nostri Filtri Interattivi Originali ────────────────────────
st.sidebar.header("🎛️ Filtri Dashboard")

all_provinces = sorted(list(set(df_acc["province"].dropna().unique()) | set(df_att["province"].dropna().unique())))
selected_province = st.sidebar.selectbox("Seleziona Provincia:", ["Tutte"] + all_provinces)

available_types = sorted(df_acc["structure_type"].unique())
selected_types = st.sidebar.multiselect("Tipo Struttura Ricettiva:", available_types, default=available_types)

available_cats = sorted(df_att["category"].unique())
selected_cats = st.sidebar.multiselect("Categoria Attrazione:", available_cats, default=available_cats)

# ── Applicazione Logica di Filtraggio in RAM (Pandas) ─────────────────────────
df_acc_filtered = df_acc[df_acc["structure_type"].isin(selected_types)] if not df_acc.empty else df_acc
if selected_province != "Tutte":
    df_acc_filtered = df_acc_filtered[df_acc_filtered["province"] == selected_province]

df_att_filtered = df_att[df_att["category"].isin(selected_cats)] if not df_att.empty else df_att
if selected_province != "Tutte":
    df_att_filtered = df_att_filtered[df_att_filtered["province"] == selected_province]

df_total_map = pd.concat([df_acc_filtered, df_att_filtered], ignore_index=True)

# ── Header Layout del Team ───────────────────────────────────────────────────
col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("Dashboard Manager")
    st.caption(f"Loggato come **{user['username']}** — Analisi geospaziale e statistica")
with col_logout:
    st.write("")
    if st.button("Esci", use_container_width=True):
        st.session_state.clear()
        st.switch_page("app.py")

st.markdown("---")

# ── Sezione Metriche Generali (Card KPI con Stile del Team) ────────────────────
k1, k2, k3, k4 = st.columns(4)
total_rooms = int(df_acc_filtered["rooms"].sum()) if "rooms" in df_acc_filtered else 0
total_beds = int(df_acc_filtered["beds"].sum()) if "beds" in df_acc_filtered else 0

kpis = [
    ("Attrazioni", len(df_att_filtered), "#34d399"),
    ("Alloggi", len(df_acc_filtered), "#a78bfa"),
    ("Stanze Disponibili", total_rooms, "#60a5fa"),
    ("Posti Letto Totali", total_beds, "#f59e0b"),
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

# ── Mappa Geografica Interattiva (La nostra Mappa Plotly) ─────────────────────
st.subheader("🗺️ Mappa Geografica Interattiva del Territorio")
df_total_map = df_total_map.dropna(subset=["lon", "lat"])

if not df_total_map.empty:
    fig_map = px.scatter_mapbox(
        df_total_map,
        lat="lat",
        lon="lon",
        color="data_type",  
        hover_name="name",
        hover_data={
            "data_type": True,
            "municipality": True,
            "province": True,
            "structure_type": True,
            "category": True,
            "stars": True,
            "lat": False, "lon": False
        },
        zoom=7.5,
        height=500,
    )
    fig_map.update_layout(
        mapbox_style="open-street-map",
        margin={"r":0,"t":0,"l":0,"b":0}
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.warning("Nessun dato georeferenziato disponibile per i filtri applicati.")

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Grafici Statistici Interattivi Originali (Plotly Express) ─────────────────
left_chart_col, right_chart_col = st.columns(2)

with left_chart_col:
    st.subheader("📊 Distribuzione Alloggi per Tipologia")
    if not df_acc_filtered.empty:
        df_count_acc = df_acc_filtered["structure_type"].value_counts().reset_index()
        df_count_acc.columns = ["Tipo Struttura", "Numero"]
        
        fig_acc = px.bar(df_count_acc, x="Numero", y="Tipo Struttura", orientation='h',
                         color="Tipo Struttura", template="plotly_white", height=350)
        fig_acc.update_layout(showlegend=False)
        st.plotly_chart(fig_acc, use_container_width=True)
    else:
        st.info("Nessun alloggio corrisponde ai filtri selezionati.")

with right_chart_col:
    st.subheader("📈 Posti Letto per Provincia")
    if not df_acc_filtered.empty:
        df_beds_prov = df_acc_filtered.groupby("province")["beds"].sum().reset_index()
        df_beds_prov = df_beds_prov.sort_values(by="beds", ascending=False)
        
        fig_beds = px.pie(df_beds_prov, values="beds", names="province", 
                          hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu, height=350)
        st.plotly_chart(fig_beds, use_container_width=True)
    else:
        st.info("Nessun dato per calcolare i posti letto.")

# ── InfluxDB Placeholder (Mantenuto dalla struttura dei colleghi) ─────────────
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