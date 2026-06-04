"""
Router Detail — recupero documento completo da MongoDB.
Endpoints:
    GET /detail/{collection}/{doc_id}
"""
import os
from fastapi import APIRouter, HTTPException, status, Path
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


@router.get("/{collection}/{doc_id}")
def get_detail(
    collection: str = Path(..., description="Nome della collezione MongoDB"),
    doc_id: str = Path(..., description="ID del documento"),
):
    """
    Recupera un documento completo da MongoDB.
    Collezioni supportate: attractions, accommodations.
    """
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collezione non valida. Scegliere tra: {ALLOWED_COLLECTIONS}",
        )
    db = _get_db()
    doc = db[collection].find_one({"_id": doc_id})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento '{doc_id}' non trovato in '{collection}'.",
        )
    # Converti _id in stringa per la serializzazione JSON
    doc["_id"] = str(doc["_id"])
    return doc
