"""
MongoDB service — detail retrieval, reviews, and dashboard stats.
"""
import os
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        _client = MongoClient(uri)
    return _client[os.getenv("MONGO_DB_NAME", "Tourism")]


def get_detail(collection: str, doc_id: str) -> dict | None:
    """Fetch a full document from MongoDB by _id."""
    return _get_db()[collection].find_one({"_id": doc_id})


def get_distinct_values(collection: str, field: str) -> list[str]:
    """Fetch distinct string values for a field directly from MongoDB."""
    try:
        values = _get_db()[collection].distinct(field)
        return sorted([str(v) for v in values if v])
    except Exception:
        return []


def add_review(
    collection: str,
    doc_id: str,
    username: str,
    rating: int,
    text: str,
) -> dict:
    """Push a new review into the document's 'reviews' array."""
    review = {
        "username": username,
        "rating": rating,
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _get_db()[collection].update_one(
        {"_id": doc_id},
        {"$push": {"reviews": review}},
    )
    return review


def get_dashboard_stats() -> dict:
    """
    Aggregate statistics for the manager dashboard.
    Returns a dict with counts and distribution data.
    """
    db = _get_db()

    stats: dict = {}

    # ── Counts ──
    stats["n_attractions"] = db["attractions"].count_documents({})
    stats["n_accommodations"] = db["accommodations"].count_documents({})
    stats["n_users"] = db["users"].count_documents({}) if "users" in db.list_collection_names() else 0

    # Total embedded reviews across all accommodations
    r = list(
        db["accommodations"].aggregate(
            [
                {"$project": {"count": {"$size": {"$ifNull": ["$reviews", []]}}}},
                {"$group": {"_id": None, "total": {"$sum": "$count"}}},
            ]
        )
    )
    stats["n_reviews"] = r[0]["total"] if r else 0

    # ── Attractions by province ──
    stats["attractions_by_province"] = list(
        db["attractions"].aggregate(
            [
                {"$group": {"_id": "$location.province", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
        )
    )

    # ── Accommodations by province ──
    stats["accommodations_by_province"] = list(
        db["accommodations"].aggregate(
            [
                {"$group": {"_id": "$location.province", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
        )
    )

    # ── Attractions by category ──
    stats["attractions_by_category"] = list(
        db["attractions"].aggregate(
            [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        )
    )

    # ── Average stars by structure type ──
    stats["stars_by_type"] = list(
        db["accommodations"].aggregate(
            [
                {
                    "$group": {
                        "_id": "$structure_type",
                        "avg_stars": {"$avg": "$stars"},
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
        )
    )

    return stats
