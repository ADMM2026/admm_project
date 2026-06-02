"""
Neo4j service — STUB (not yet active).
Replace the body of each function when Neo4j is ready.
"""


def is_available() -> bool:
    """Returns True when Neo4j is connected and ready."""
    return False


def find_nearby(
    doc_id: str,
    source_type: str,        # 'attraction' | 'accommodation'
    target_type: str,        # 'attraction' | 'accommodation'
    radius_km: float = 5.0,
    limit: int = 10,
) -> list[dict]:
    """
    Returns a list of nearby POIs within radius_km.
    STUB: always returns an empty list until Neo4j is connected.

    Future Cypher query example:
        MATCH (a {id: $id})-[r:NEARBY]->(b)
        WHERE r.distance_km <= $radius
        RETURN b, r.distance_km AS distance
        ORDER BY distance LIMIT $limit
    """
    return []
