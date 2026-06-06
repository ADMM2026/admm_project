import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from components.utils import load_css, require_login
from services.mongo_service import get_raw_data

st.set_page_config(
    page_title="Piemonte Turismo — Dashboard Manager",
    page_icon="📊",
    layout="wide",
)

load_css()
user = require_login(allowed_roles=["manager"])

@st.cache_data(ttl=60)
def load_data():
    """Carica e normalizza i dati grezzi estratti dal Backend."""
    data = get_raw_data()
    raw_acc = data.get("accommodations", [])
    df_acc = pd.DataFrame(raw_acc)
    if not df_acc.empty:
        df_acc["data_type"] = "Alloggio"
        df_acc["category"] = "N/A"
        df_acc["rooms"] = pd.to_numeric(df_acc["rooms"], errors="coerce").fillna(0).astype(int)
        df_acc["beds"] = pd.to_numeric(df_acc["beds"], errors="coerce").fillna(0).astype(int)
        df_acc["avg_rating"] = df_acc["ratings"].apply(lambda x: np.mean(x) if isinstance(x, list) and len(x) > 0 else np.nan)
    else:
        df_acc = pd.DataFrame(columns=["name", "structure_type", "sector", "stars", "municipality", "province", "rooms", "beds", "lon", "lat", "data_type", "category", "avg_rating"])

    raw_att = data.get("attractions", [])
    df_att = pd.DataFrame(raw_att)
    if not df_att.empty:
        df_att["data_type"] = "Attrazione"
        df_att["structure_type"] = "N/A"
        df_att["stars"] = 0
        df_att["rooms"] = 0
        df_att["beds"] = 0
        df_att["avg_rating"] = df_att["ratings"].apply(lambda x: np.mean(x) if isinstance(x, list) and len(x) > 0 else np.nan)
    else:
        df_att = pd.DataFrame(columns=["name", "category", "municipality", "province", "lon", "lat", "data_type", "structure_type", "stars", "rooms", "beds", "avg_rating"])

    return df_acc, df_att


with st.spinner("Caricamento componenti analitici dal database distribuito..."):
    df_acc, df_att = load_data()

st.sidebar.header("🎛️ Filtri Analitici")


all_provinces = sorted(list(
    set(df_acc["province"].dropna().unique() if not df_acc.empty else []) |
    set(df_att["province"].dropna().unique() if not df_att.empty else [])
))
selected_province = st.sidebar.selectbox("Filtra per Provincia:", ["Tutte"] + all_provinces)

available_types = sorted(df_acc["structure_type"].dropna().unique()) if not df_acc.empty else []
selected_types = st.sidebar.multiselect("Tipologia Struttura:", available_types, default=available_types)

available_cats = sorted(df_att["category"].dropna().unique()) if not df_att.empty else []
selected_cats = st.sidebar.multiselect("Categoria Attrazione:", available_cats, default=available_cats)


df_acc_filtered = df_acc.copy()
df_att_filtered = df_att.copy()

if selected_province != "Tutte":
    df_acc_filtered = df_acc_filtered[df_acc_filtered["province"] == selected_province]
    df_att_filtered = df_att_filtered[df_att_filtered["province"] == selected_province]

if selected_types:
    df_acc_filtered = df_acc_filtered[df_acc_filtered["structure_type"].isin(selected_types)]
else:
    df_acc_filtered = df_acc_filtered.iloc[0:0] 

if selected_cats:
    df_att_filtered = df_att_filtered[df_att_filtered["category"].isin(selected_cats)]
else:
    df_att_filtered = df_att_filtered.iloc[0:0]

df_total_map = pd.concat([df_acc_filtered, df_att_filtered], ignore_index=True)


col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("📊 Dashboard Direzionale Manager")
    st.caption(f"Operatore loggato: **{user['username']}** — Monitoraggio delle risorse e dei flussi sul territorio")
with col_logout:
    st.write("")
    if st.button("Esci", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.switch_page("app.py")

st.markdown("---")


k1, k2, k3, k4 = st.columns(4)

total_rooms = int(df_acc_filtered["rooms"].sum()) if not df_acc_filtered.empty else 0
total_beds = int(df_acc_filtered["beds"].sum()) if not df_acc_filtered.empty else 0


all_ratings = []
if not df_acc_filtered.empty:
    for r_list in df_acc_filtered["ratings"].dropna():
        all_ratings.extend(r_list)
if not df_att_filtered.empty:
    for r_list in df_att_filtered["ratings"].dropna():
        all_ratings.extend(r_list)
global_score = f"{np.mean(all_ratings):.2f} ⭐" if all_ratings else "N/D"

kpis = [
    ("Attrazioni Filtrate", len(df_att_filtered), "#34d399"),
    ("Strutture Ricettive", len(df_acc_filtered), "#a78bfa"),
    ("Posti Letto Totali", total_beds, "#f59e0b"),
    ("Gradimento Medio", global_score, "#60a5fa"),
]

for col, (label, value, color) in zip([k1, k2, k3, k4], kpis):
    formatted_value = f"{value:,}" if isinstance(value, (int, float)) else str(value)
    
    with col:
        st.markdown(
            f"""<div class="metric-card">
                  <div class="metric-label">{label}</div>
                  <div class="metric-value" style="color:{color}">{formatted_value}</div>
                </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)


st.subheader("🗺️ Mappa di Densità e Georeferenziazione Territoriale")
if "lon" in df_total_map.columns and "lat" in df_total_map.columns:
    df_total_map = df_total_map.dropna(subset=["lon", "lat"])

if not df_total_map.empty:
    df_total_map["size_marker"] = df_total_map["beds"].apply(lambda x: min(int(x * 0.1) + 8, 25) if x > 0 else 4)
    
    fig_map = px.scatter_mapbox(
        df_total_map,
        lat="lat",
        lon="lon",
        color="data_type",
        size="size_marker",
        hover_name="name",
        hover_data={
            "data_type": True,
            "municipality": True,
            "province": True,
            "structure_type": False,
            "category": False,
            "stars": False,
            "avg_rating": True,
            "size_marker": False,
            "lat": False, 
            "lon": False
        },
        color_discrete_map={"Alloggio": "#a78bfa", "Attrazione": "#34d399"},
        zoom=7.5,
        height=520,
    )
    fig_map.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(yanchor="top", y=0.98, xanchor="left", x=0.01, bgcolor="rgba(15,23,42,0.8)")
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.warning("⚠️ Nessuna risorsa georeferenziata soddisfa i criteri dei filtri correnti.")

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)


left_chart_col, right_chart_col = st.columns(2)

with left_chart_col:
    st.subheader("📊 Consistenza Alloggi per Tipologia")
    if not df_acc_filtered.empty:
        df_count_acc = df_acc_filtered["structure_type"].value_counts().reset_index()
        df_count_acc.columns = ["Tipo Struttura", "Numero Strutture"]

        fig_acc = px.bar(
            df_count_acc, 
            x="Numero Strutture", 
            y="Tipo Struttura", 
            orientation='h',
            color="Tipo Struttura", 
            template="plotly_dark", 
            height=360
        )
        fig_acc.update_layout(showlegend=False, margin={"t": 20, "b": 20})
        st.plotly_chart(fig_acc, use_container_width=True)
    else:
        st.info("Nessun alloggio disponibile per i filtri correnti.")

with right_chart_col:
    st.subheader("📈 Distribuzione Capacità (Posti Letto) per Provincia")
    if not df_acc_filtered.empty and df_acc_filtered["beds"].sum() > 0:
        df_beds_prov = df_acc_filtered.groupby("province")["beds"].sum().reset_index()
        df_beds_prov = df_beds_prov.sort_values(by="beds", ascending=False)

        fig_beds = px.pie(
            df_beds_prov, 
            values="beds", 
            names="province",
            hole=0.4, 
            color_discrete_sequence=px.colors.sequential.Plotly3, 
            height=360
        )
        fig_beds.update_layout(margin={"t": 20, "b": 20})
        st.plotly_chart(fig_beds, use_container_width=True)
    else:
        st.info("Dati di capacità (posti letto) non disponibili per la selezione corrente.")


st.markdown("---")
st.markdown("#### Monitoraggio delle metriche temporali")
st.markdown(
    """
    <div class="result-card" style="border-color:rgba(251,191,36,0.3); text-align:center; padding:2rem; background-color:rgba(30,41,59,0.5)">
      <div style="font-size:1.5rem; font-weight:600; color:#94a3b8">📊 Pipeline di Monitoraggio in Real-Time</div>
      <div class="result-name" style="margin-top:0.5rem; color:#f59e0b">Integrazione InfluxDB & Telegraf (In Sviluppo)</div>
      <p class="result-desc" style="max-width:700px; margin:0 auto; margin-top:0.5rem;">
        I grafici delle serie temporali riguardanti l'andamento dei flussi di recensioni inserite dagli utenti, 
        la frequenza oraria delle query di ricerca inviate a Elasticsearch e le telemetrie prestazionali dei container 
        saranno visualizzabili qui non appena lo storage a serie temporali <strong>InfluxDB</strong> sarà agganciato al sistema.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)