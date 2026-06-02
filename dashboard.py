import streamlit as st
import pandas as pd
import plotly.express as px
from pymongo import MongoClient
from dotenv import load_dotenv
import os


load_dotenv()

st.set_page_config(page_title="Turismo Piemonte Dashboard", layout="wide")

st.title("Turismo Piemonte Dashboard")


@st.cache_resource
def get_mongo_db():
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"))
    return client[os.getenv("MONGO_DB_NAME", "Tourism")]

db = get_mongo_db()

@st.cache_data(ttl=60)  
def load_data():
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

df_acc, df_att = load_data()

st.sidebar.header("Filtri Dashboard")

all_provinces = sorted(list(set(df_acc["province"].dropna().unique()) | set(df_att["province"].dropna().unique())))
selected_province = st.sidebar.selectbox("Seleziona Provincia:", ["Tutte"] + all_provinces)

available_types = sorted(df_acc["structure_type"].unique())
selected_types = st.sidebar.multiselect("Tipo Struttura Ricettiva:", available_types, default=available_types)

available_cats = sorted(df_att["category"].unique())
selected_cats = st.sidebar.multiselect("Categoria Attrazione:", available_cats, default=available_cats)

df_acc_filtered = df_acc[df_acc["structure_type"].isin(selected_types)] if not df_acc.empty else df_acc
if selected_province != "Tutte":
    df_acc_filtered = df_acc_filtered[df_acc_filtered["province"] == selected_province]

df_att_filtered = df_att[df_att["category"].isin(selected_cats)] if not df_att.empty else df_att
if selected_province != "Tutte":
    df_att_filtered = df_att_filtered[df_att_filtered["province"] == selected_province]

df_total_map = pd.concat([df_acc_filtered, df_att_filtered], ignore_index=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🏨 Totale Alloggi", len(df_acc_filtered))
with col2:
    st.metric("🏛️ Totale Attrazioni", len(df_att_filtered))
with col3:
    total_rooms = int(df_acc_filtered["rooms"].sum()) if "rooms" in df_acc_filtered else 0
    st.metric("🛏️ Stanze Disponibili", f"{total_rooms:,}")
with col4:
    total_beds = int(df_acc_filtered["beds"].sum()) if "beds" in df_acc_filtered else 0
    st.metric("💤 Posti Letto Totali", f"{total_beds:,}")

st.markdown("---")

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
        zoom=8,
        height=600,
        title="Posizione Geografica di Alloggi (Punti Verdi/Blu) e Attrazioni"
    )
    
    fig_map.update_layout(
        mapbox_style="open-street-map",
        margin={"r":0,"t":40,"l":0,"b":0}
    )
    
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.warning("Nessun dato georeferenziato disponibile per i filtri applicati.")