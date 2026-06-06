from fastapi import APIRouter, HTTPException, status
from app.database import get_mongo

router = APIRouter()


@router.get("/raw-data")
def get_dashboard_raw_data():
    try:
        db = get_mongo()
        
        accommodations_cursor = db["accommodations"].find(
            {},
            {
                "name": 1,
                "structure_type": 1,
                "sector": 1,
                "stars": 1,
                "location.municipality": 1,
                "location.province": 1,
                "capacity.rooms": 1,
                "capacity.beds": 1,
                "position.coordinates": 1,
                "reviews.rating": 1  
            }
        )
        
        attractions_cursor = db["attractions"].find(
            {},
            {
                "name": 1,
                "category": 1,
                "location.municipality": 1,
                "location.province": 1,
                "position.coordinates": 1,
                "reviews.rating": 1
            }
        )

        accommodations = []
        for doc in accommodations_cursor:
            coords = doc.get("position", {}).get("coordinates", [None, None])
            raw_reviews = doc.get("reviews", [])
            ratings = [r["rating"] for r in raw_reviews if isinstance(r, dict) and "rating" in r] if isinstance(raw_reviews, list) else []
            
            accommodations.append({
                "_id": str(doc["_id"]),
                "name": doc.get("name"),
                "structure_type": doc.get("structure_type"),
                "sector": doc.get("sector"),
                "stars": doc.get("stars"),
                "municipality": doc.get("location", {}).get("municipality"),
                "province": doc.get("location", {}).get("province"),
                "rooms": doc.get("capacity", {}).get("rooms"),
                "beds": doc.get("capacity", {}).get("beds"),
                "ratings": ratings, 
                "lon": coords[0] if len(coords) > 0 else None,
                "lat": coords[1] if len(coords) > 1 else None,
            })

        attractions = []
        for doc in attractions_cursor:
            coords = doc.get("position", {}).get("coordinates", [None, None])
            raw_reviews = doc.get("reviews", [])
            ratings = [r["rating"] for r in raw_reviews if isinstance(r, dict) and "rating" in r] if isinstance(raw_reviews, list) else []
            
            attractions.append({
                "_id": str(doc["_id"]),
                "name": doc.get("name"),
                "category": doc.get("category"),
                "municipality": doc.get("location", {}).get("municipality"),
                "province": doc.get("location", {}).get("province"),
                "ratings": ratings,  
                "lon": coords[0] if len(coords) > 0 else None,
                "lat": coords[1] if len(coords) > 1 else None,
            })

        return {
            "accommodations": accommodations,
            "attractions": attractions
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero dati dashboard: {e}"
        )