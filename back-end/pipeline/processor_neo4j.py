import sys

if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    import selectors
    _orig_unregister = selectors.SelectSelector.unregister
    def _safe_unregister(self, fileobj):
        try:
            return _orig_unregister(self, fileobj)
        except (ValueError, KeyError):
            pass
    selectors.SelectSelector.unregister = _safe_unregister

import json
import os
from kafka import KafkaConsumer
from neo4j import GraphDatabase
from dotenv import load_dotenv
from common import extract_mongo_id

load_dotenv()

neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
neo4j_user = os.getenv("NEO4J_USER", "neo4j")
neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
neo4j_max_dist = float(os.getenv("NEO4J_MAX_DISTANCE_METERS", "5000"))

neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))


def index_in_neo4j(target_index: str, mongo_id: str, name: str, coords: list):
    if not coords or len(coords) < 2:
        return  
    lon, lat = float(coords[0]), float(coords[1])
    node_label = "Accommodation" if target_index == "accommodations" else "Attraction"
    opposite_label = "Attraction" if node_label == "Accommodation" else "Accommodation"

    query = """
        MERGE (n:`""" + node_label + """` { id: $id })
        SET n.name = $name,
            n.location = point({ latitude: $lat, longitude: $lon })
        
        WITH n
        MATCH (other:`""" + opposite_label + """`)
        WHERE other.location IS NOT NULL 
        AND point.distance(n.location, other.location) <= $max_distance
        
        WITH n, other, point.distance(n.location, other.location) / 1000.0 AS dist_km
        
        MERGE (n)-[r1:NEAR_TO]->(other)
        SET r1.distance_km = dist_km
        
        MERGE (n)<-[r2:NEAR_TO]-(other)
        SET r2.distance_km = dist_km
    """

    try:
        with neo4j_driver.session() as session:
            session.run(
                query, 
                id=mongo_id, 
                name=name, 
                lat=lat, 
                lon=lon, 
                max_distance=neo4j_max_dist
            )
    except Exception as e:
        print(f"[ERROR - Neo4j] Failed to index node/relations for {mongo_id}: {e}")


def delete_from_neo4j(label, doc_id):
    label_capitalized = "Accommodation" if label == "accommodations" else "Attraction"
    cypher_delete = f"""
        MATCH (n:{label_capitalized} {{id: $id}})
        DETACH DELETE n
    """
    with neo4j_driver.session() as session:
        session.run(cypher_delete, id=str(doc_id))


def main():
    print("[NEO4J PROCESSOR] Starting independent geospatial graph consumer...")

    consumer = KafkaConsumer(
        "Tourism.Tourism.accommodations",
        "Tourism.Tourism.attractions",
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(","),
        group_id="neo4j-processor-group",
        auto_offset_reset="earliest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")) if x is not None else None
    )

    try:
        for message in consumer:
            if message.value is None:
                continue
            try:
                payload = message.value.get("payload", {}) if message.value else {}
                op = payload.get("op")
                topic = message.topic
                target_label = "accommodations" if "accommodations" in topic else "attractions"

                mongo_id = extract_mongo_id(message.key)
                if not mongo_id:
                    print(f"[NEO4J WARNING] Could not extract _id from payload, skipping. op={op}")
                    continue

                if op == "d":
                    print(f"[NEO4J] Detected DELETE for ID {mongo_id} from graph")
                    delete_from_neo4j(target_label, mongo_id)
                    continue

                after_str = payload.get("after")
                if not after_str:
                    continue

                raw_data = json.loads(after_str)
                pos = raw_data.get("position", {})
                coords = pos.get("coordinates") if isinstance(pos, dict) else None
                name = raw_data.get("name", "N/D")

                if coords and len(coords) == 2:
                    index_in_neo4j(target_label, mongo_id, name, coords)
                    print(f"[NEO4J SUCCESS] Updated Node & Relations for ID: {mongo_id} [Op: {op}]")
                else:
                    print(f"[NEO4J WARNING] No valid coordinates for ID {mongo_id}, skipping node upsert.")

            except Exception as e:
                print(f"[NEO4J ERROR] Failed to process graph mutation: {e}")
                continue

    except KeyboardInterrupt:
        print("\n[NEO4J] Stopping consumer gracefully...")
    finally:
        consumer.close()
        neo4j_driver.close()


if __name__ == "__main__":
    main()