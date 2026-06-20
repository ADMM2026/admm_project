from fastapi import APIRouter, HTTPException, status, Query
from app.database import get_neo4j

router = APIRouter()

@router.get("/accommodations/{accommodation_id}/nearby-attractions")
def get_nearby_attractions(accommodation_id: str):
    driver = get_neo4j()
    query = """
        MATCH (a:Accommodation {id: $id})-[r:NEAR_TO]->(b:Attraction)
        RETURN b.id AS id, 
               b.name AS name, 
               r.distance_km AS distance_km,
               b.location.latitude AS latitude,
               b.location.longitude AS longitude
        ORDER BY r.distance_km ASC
    """
    try:
        with driver.session() as session:
            result = session.run(query, id=accommodation_id)
            attractions = [
                {
                    "id": record["id"],
                    "name": record["name"],
                    "distance_km": round(record["distance_km"], 2),
                    # Aggiungiamo le coordinate direttamente nel dizionario
                    "latitude": record["latitude"],
                    "longitude": record["longitude"]
                }
                for record in result
            ]
        return {"accommodation_id": accommodation_id, "nearby_attractions": attractions}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Neo4j Graph Database error: {e}"
        )


@router.get("/attractions/{attraction_id}/cluster-analysis")
def get_attraction_cluster_analysis(attraction_id: str):
    driver = get_neo4j()    
    
    query = """
    MATCH (start:Attraction {id: $id})-[:NEAR_TO]-(acc:Accommodation)
    MATCH (acc)-[r2:NEAR_TO]->(other:Attraction)
    WHERE other.id <> start.id
    
    RETURN acc.id AS acc_id, 
           acc.name AS acc_name,
           acc.location.latitude AS acc_lat,
           acc.location.longitude AS acc_lon,
           collect({
               id: other.id,
               name: other.name,
               distance_km: round(r2.distance_km, 2),
               latitude: other.location.latitude,
               longitude: other.location.longitude
           }) AS alternative_attractions
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, id=attraction_id)
            cluster = [
                {
                    "accommodation_id": record["acc_id"],
                    "accommodation_name": record["acc_name"],
                    "latitude": record["acc_lat"],
                    "longitude": record["acc_lon"],
                    "alternative_attractions": record["alternative_attractions"]
                }
                for record in result
            ]
        return {"start_attraction_id": attraction_id, "accommodation_hubs": cluster}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Neo4j Graph Database error: {e}"
        )