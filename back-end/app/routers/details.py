import os
from fastapi import APIRouter, HTTPException, status, Path, Request
from bson import ObjectId
from bson.errors import InvalidId
from app.database import get_mongo

router = APIRouter()

ALLOWED_COLLECTIONS = {"attractions", "accommodations"}


@router.get("/{collection}/{doc_id}")
def get_detail(
    request: Request,
    collection: str = Path(..., description="Nome della collezione MongoDB"),
    doc_id: str = Path(..., description="ID del documento proveniente dal client/ELK"),
):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collezione non valida. Scegliere tra: {ALLOWED_COLLECTIONS}",
        )
    
    db = get_mongo()

    query_id = doc_id
    try:
        query_id = ObjectId(doc_id)
    except InvalidId:
        pass

    doc = db[collection].find_one({"_id": query_id})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento '{doc_id}' non trovato in '{collection}'.",
        )

    doc["_id"] = str(doc["_id"])
    base_url = str(request.base_url).rstrip("/")
    image_filename = doc.get("image")
    if image_filename and isinstance(image_filename, str) and image_filename.strip():
        doc["image_url"] = f"{base_url}/static/images/{collection}/{image_filename.strip()}"
    else:
        doc["image_url"] = f"{base_url}/static/images/placeholder.jpg"
    return doc