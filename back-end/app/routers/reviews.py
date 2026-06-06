from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Path
from pydantic import BaseModel, Field
from app.database import get_mongo
from bson.objectid import ObjectId 

router = APIRouter()

ALLOWED_COLLECTIONS = {"attractions", "accommodations"}

class ReviewRequest(BaseModel):
    username: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    text: str = Field("", max_length=2000)

class ReviewResponse(BaseModel):
    username: str
    rating: int
    text: str
    created_at: str

def parse_object_id(doc_id: str) -> ObjectId:
    try:
        return ObjectId(doc_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato identificativo del documento (ID) non valido."
        )

@router.get("/{collection}/{doc_id}")
def get_reviews(
    collection: str = Path(...),
    doc_id: str = Path(...),
):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Collezione non valida.")
    
    db = get_mongo()
    mongo_id = parse_object_id(doc_id)
    
    doc = db[collection].find_one({"_id": mongo_id}, {"reviews": 1})
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
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Collezione non valida.")
    
    db = get_mongo()
    mongo_id = parse_object_id(doc_id)

    review = {
        "username": body.username,
        "rating": body.rating,
        "text": body.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    result = db[collection].update_one(
        {"_id": mongo_id},
        {"$push": {"reviews": review}},
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Documento non trovato.")
    return ReviewResponse(**review)