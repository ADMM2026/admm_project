import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from components.utils import load_css, require_login, smart_button, smart_plotly_chart
from components.filters import dashboard_manager_filters  
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

dash_filters = dashboard_manager_filters(df_acc, df_att)

df_acc_filtered = df_acc.copy()
df_att_filtered = df_att.copy()

if dash_filters["provinces"]:
    df_acc_filtered = df_acc_filtered[df_acc_filtered["province"].isin(dash_filters["provinces"])]
    df_att_filtered = df_att_filtered[df_att_filtered["province"].isin(dash_filters["provinces"])]

if dash_filters["structure_types"]:
    df_acc_filtered = df_acc_filtered[df_acc_filtered["structure_type"].isin(dash_filters["structure_types"])]
else:
    df_acc_filtered = df_acc_filtered.iloc[0:0] 

if dash_filters["categories"]:
    df_att_filtered = df_att_filtered[df_att_filtered["category"].isin(dash_filters["categories"])]
else:
    df_att_filtered = df_att_filtered.iloc[0:0]

df_total_map = pd.concat([df_acc_filtered, df_att_filtered], ignore_index=True)


col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("📊 Dashboard Direzionale Manager")
    st.caption(f"Operatore loggato: **{user['username']}** — Monitoraggio delle risorse e dei flussi sul territorio")
with col_logout:
    st.write("")
    if smart_button("Esci", type="secondary"):
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

st.subheader("🗺️ Mappa di Densità Territoriale")
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
    smart_plotly_chart(fig_map)
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
            template="plotly_dark", 
            color_discrete_sequence=["#a78bfa"], 
            height=360
        )
        
        fig_acc.update_yaxes(categoryorder="total ascending")
        
        fig_acc.update_layout(margin={"t": 20, "b": 20})
        smart_plotly_chart(fig_acc)
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
            color_discrete_sequence=px.colors.qualitative.Plotly, 
            height=360
        )
        fig_beds.update_layout(margin={"t": 20, "b": 20})
        smart_plotly_chart(fig_beds)
    else:
        st.info("Dati di capacità (posti letto) non disponibili per la selezione corrente.")

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
left_chart_col_2, right_chart_col_2 = st.columns(2)

with left_chart_col_2:
    st.subheader("📊 Consistenza Attrazioni per Categoria")
    if not df_att_filtered.empty:
        df_count_att = df_att_filtered["category"].value_counts().reset_index()
        df_count_att.columns = ["Categoria", "Numero Attrazioni"]

        fig_att = px.bar(
            df_count_att, 
            x="Numero Attrazioni", 
            y="Categoria", 
            orientation='h',
            template="plotly_dark", 
            color_discrete_sequence=["#34d399"], 
            height=360
        )
        fig_att.update_yaxes(categoryorder="total ascending")
        fig_att.update_layout(margin={"t": 20, "b": 20})
        smart_plotly_chart(fig_att)
    else:
        st.info("Nessuna attrazione disponibile per i filtri correnti.")

with right_chart_col_2:
    st.subheader("⭐ Distribuzione Recensioni e Gradimento Attrazioni")
    
    att_ratings = []
    if not df_att_filtered.empty and "ratings" in df_att_filtered.columns:
        for r_list in df_att_filtered["ratings"].dropna():
            if isinstance(r_list, list):
                att_ratings.extend(r_list)

    if att_ratings:
        counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for r in att_ratings:
            try:
                val = int(np.round(float(r)))
                if val in counts:
                    counts[val] += 1
            except (ValueError, TypeError):
                pass
        
        total_reviews = len(att_ratings)
        avg_rating = np.mean(att_ratings)
        
        sub_col_bars, sub_col_metrics = st.columns([1.7, 1])
        
        with sub_col_bars:
            bars_html = ""
            for star in [5, 4, 3, 2, 1]:
                count = counts[star]
                percentage = int(np.round(count / total_reviews * 100)) if total_reviews > 0 else 0
                
                bars_html += (
                    f'<div style="display: flex; align-items: center; margin-bottom: 10px;">'
                    f'<div style="width: 15px; font-size: 1.1rem; color: #94a3b8; text-align: right; margin-right: 15px; font-weight: 500;">{star}</div>'
                    f'<div style="flex-grow: 1; background-color: #334155; height: 16px; border-radius: 8px; overflow: hidden;">'
                    f'<div style="background-color: #f59e0b; width: {percentage}%; height: 100%; border-radius: 8px;"></div>'
                    f'</div>'
                    f'</div>'
                )
            st.markdown(f'<div style="padding-top: 20px;">{bars_html}</div>', unsafe_allow_html=True)
            
        with sub_col_metrics:
            formatted_avg = f"{avg_rating:.1f}".replace('.', ',')
            formatted_total = f"{total_reviews:,}".replace(',', '.')
            
            rounded_rating = int(np.round(avg_rating))
            stars_symbols = "★" * rounded_rating + "☆" * (5 - rounded_rating)

            st.markdown(f"""
                <div style="text-align: center; padding-top: 10px; font-family: sans-serif;">
                    <div style="font-size: 5rem; font-weight: 300; color: white; line-height: 1;">{formatted_avg}</div>
                    <div style="color: #f59e0b; font-size: 1.6rem; letter-spacing: 2px; margin: 8px 0;">{stars_symbols}</div>
                    <div style="font-size: 1.1rem; color: #94a3b8;">{formatted_total} recensioni</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Dati di gradimento o recensioni non disponibili per le attrazioni filtrate.")

st.markdown("---")
st.markdown("#### Monitoraggio delle metriche temporali")
st.markdown(
    """
    <div class="result-card" style="border-color:rgba(251,191,36,0.3); text-align:center; padding:2rem; background-color:rgba(30,41,59,0.5)">
      <div style="font-size:1.5rem; font-weight:600; color:#94a3b8">📊 Pipeline di Monitoraggio in Real-Time</div>
      <div class="result-name" style="margin-top:0.5rem; color:#f59e0b">Integrazione InfluxDB (In Sviluppo)</div>
      
    </div>
    """,
    unsafe_allow_html=True,
)