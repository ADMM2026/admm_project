"""
Router Reviews — aggiunta recensioni a documenti MongoDB.
Endpoints:
    POST /reviews/{collection}/{doc_id}
    GET  /reviews/{collection}/{doc_id}
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Path
from pydantic import BaseModel, Field
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

_client = None

ALLOWED_COLLECTIONS = {"attractions", "accommodations"}


def _get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        _client = MongoClient(uri)
    return _client[os.getenv("MONGO_DB_NAME", "Tourism")]


# ── Modelli Pydantic ──────────────────────────────────────────────────────────
class ReviewRequest(BaseModel):
    username: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    text: str = Field("", max_length=2000)


class ReviewResponse(BaseModel):
    username: str
    rating: int
    text: str
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/{collection}/{doc_id}")
def get_reviews(
    collection: str = Path(...),
    doc_id: str = Path(...),
):
    """Recupera le recensioni di un documento."""
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Collezione non valida.")
    db = _get_db()
    doc = db[collection].find_one({"_id": doc_id}, {"reviews": 1})
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Documento non trovato.")
    return {"reviews": doc.get("reviews", [])}


@router.post("/{collection}/{doc_id}", response_model=ReviewResponse,
             status_code=status.HTTP_201_CREATED)
def add_review(
    body: ReviewRequest,
    collection: str = Path(...),
    doc_id: str = Path(...),
):
    """Aggiunge una recensione al documento specificato."""
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Collezione non valida.")
    db = _get_db()

    review = {
        "username": body.username,
        "rating": body.rating,
        "text": body.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db[collection].update_one(
        {"_id": doc_id},
        {"$push": {"reviews": review}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Documento non trovato.")
    return ReviewResponse(**review)
