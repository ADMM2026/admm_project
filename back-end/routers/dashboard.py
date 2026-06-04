"""
Router Dashboard — statistiche aggregate e dati mappa per il manager.
Endpoints:
    GET /dashboard/stats       — KPI counts + distribuzioni (grafici)
    GET /dashboard/map-data    — dati proiettati per la mappa Plotly
"""
import os
from fastapi import APIRouter
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

_client = None


def _get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        _client = MongoClient(uri)
    return _client[os.getenv("MONGO_DB_NAME", "Tourism")]


@router.get("/stats")
def get_stats():
    """
    Statistiche aggregate per la dashboard manager.
    Ritorna counts, distribuzioni per provincia/categoria e stelle medie.
    """
    db = _get_db()
    stats: dict = {}

    # ── Counts ──
    stats["n_attractions"] = db["attractions"].count_documents({})
    stats["n_accommodations"] = db["accommodations"].count_documents({})
    stats["n_users"] = (
        db["users"].count_documents({})
        if "users" in db.list_collection_names()
        else 0
    )

    # Totale recensioni embedded
    r = list(
        db["accommodations"].aggregate([
            {"$project": {"count": {"$size": {"$ifNull": ["$reviews", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$count"}}},
        ])
    )
    stats["n_reviews"] = r[0]["total"] if r else 0

    # ── Distribuzioni ──
    stats["attractions_by_province"] = list(
        db["attractions"].aggregate([
            {"$group": {"_id": "$location.province", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ])
    )
    stats["accommodations_by_province"] = list(
        db["accommodations"].aggregate([
            {"$group": {"_id": "$location.province", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ])
    )
    stats["attractions_by_category"] = list(
        db["attractions"].aggregate([
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])
    )
    stats["stars_by_type"] = list(
        db["accommodations"].aggregate([
            {
                "$group": {
                    "_id": "$structure_type",
                    "avg_stars": {"$avg": "$stars"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ])
    )

    # Serializza i campi _id (che in aggregazioni sono stringhe o None)
    for key in ("attractions_by_province", "accommodations_by_province",
                "attractions_by_category", "stars_by_type"):
        for item in stats[key]:
            item["_id"] = str(item["_id"]) if item["_id"] else "N/D"

    return stats


@router.get("/map-data")
def get_map_data():
    """
    Dati proiettati per la mappa geografica interattiva Plotly.
    Ritorna due liste: accommodations e attractions con lat/lon.
    """
    db = _get_db()

    pipeline_acc = [
        {
            "$project": {
                "name": 1, "structure_type": 1, "sector": 1, "stars": 1,
                "municipality": "$location.municipality",
                "province": "$location.province",
                "rooms": "$capacity.rooms",
                "beds": "$capacity.beds",
                "lon": {"$arrayElemAt": ["$position.coordinates", 0]},
                "lat": {"$arrayElemAt": ["$position.coordinates", 1]},
            }
        }
    ]
    pipeline_att = [
        {
            "$project": {
                "name": 1, "category": 1,
                "municipality": "$location.municipality",
                "province": "$location.province",
                "lon": {"$arrayElemAt": ["$position.coordinates", 0]},
                "lat": {"$arrayElemAt": ["$position.coordinates", 1]},
            }
        }
    ]

    def serialize(docs):
        result = []
        for d in docs:
            d["_id"] = str(d["_id"])
            result.append(d)
        return result

    return {
        "accommodations": serialize(list(db["accommodations"].aggregate(pipeline_acc))),
        "attractions": serialize(list(db["attractions"].aggregate(pipeline_att))),
    }
