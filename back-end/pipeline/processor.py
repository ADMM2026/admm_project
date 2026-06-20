import json
import os
from kafka import KafkaConsumer
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
es_user = os.getenv("ES_USER")
es_password = os.getenv("ES_PASSWORD")
auth = (es_user, es_password) if es_user and es_password else None

es_client = Elasticsearch(
    es_url,
    basic_auth=auth,
    verify_certs=False,
)

neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
neo4j_user = os.getenv("NEO4J_USER", "neo4j")
neo4j_password = os.getenv("NEO4J_PASSWORD", "password_segreta_123")
neo4j_max_dist = float(os.getenv("NEO4J_MAX_DISTANCE_METERS", "5000"))

neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

def process_reviews(raw_reviews) -> list[str]:
    if isinstance(raw_reviews, list):
        return [str(r).strip() for r in raw_reviews if r]
    elif isinstance(raw_reviews, str):
        return [raw_reviews.strip()] if raw_reviews.strip() else []
    return []

def extract_mongo_id(raw_id) -> str | None:
    if not raw_id:
        return None
    if isinstance(raw_id, str):
        raw_id_str = raw_id.strip()
        if '"$oid"' in raw_id_str or '$oid' in raw_id_str:
            try:
                parsed = json.loads(raw_id_str)
                if isinstance(parsed, dict) and "$oid" in parsed:
                    return parsed["$oid"]
            except Exception:
                pass
        return raw_id_str    
    if isinstance(raw_id, dict):
        if "$oid" in raw_id:
            return raw_id["$oid"]
        
    return str(raw_id)


def extract_after(debezium_payload: dict):
    payload = debezium_payload.get("payload", debezium_payload) if isinstance(debezium_payload, dict) else {}
    if not isinstance(payload, dict):
        return None
    op = payload.get("op")
    if op == "d":
        return None
    raw_after = payload.get("after")
    if isinstance(raw_after, str):
        try:
            raw_after = json.loads(raw_after)
        except Exception as e:
            print(f"[WARNING] Impossibile decodificare la stringa 'after' in JSON: {e}")
            pass

    return raw_after

def index_in_elk(target_index: str, mongo_id: str, document: dict):
    try:
        es_client.index(index=target_index, id=mongo_id, body=document)
    except Exception as e:
        print(f"[ERROR - Elasticsearch] Failed to index document {mongo_id}: {e}")


def index_in_neo4j(target_index: str, mongo_id: str, name: str, coords: list):
    if not coords or len(coords) < 2:
        return  
    lon, lat = float(coords[0]), float(coords[1])
    node_label = "Accommodation" if target_index == "accommodations" else "Attraction"
    opposite_label = "Attraction" if node_label == "Accommodation" else "Accommodation"

    query = """
        CREATE (n:`""" + node_label + """` { id: $id })
        SET n.name = $name,
            n.location = point({ latitude: $lat, longitude: $lon })
        
        WITH n
        MATCH (other:`""" + opposite_label + """`)
        WHERE other.location IS NOT NULL 
        AND point.distance(n.location, other.location) <= $max_distance
        
        WITH n, other, point.distance(n.location, other.location) / 1000.0 AS dist_km
        
        CREATE (n)-[r1:NEAR_TO]->(other)
        SET r1.distance_km = dist_km
        
        CREATE (n)<-[r2:NEAR_TO]-(other)
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



def main():
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
    topics = ["Tourism.Tourism.accommodations", "Tourism.Tourism.attractions"]
    
    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=kafka_servers,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="elk-neo4j-processor-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    print(f"[INFO] Processor pipeline started. Listening to topics: {topics}")
    indexed_count = 0

    try:
        for message in consumer:
            try: 
                payload = message.value
                if not payload:
                    continue

                raw_data = extract_after(payload)
                if not raw_data:
                    continue

                mongo_id = extract_mongo_id(raw_data.get("_id"))
                if not mongo_id:
                    print("[WARNING] Skipping message due to missing or invalid MongoDB ID.")
                    continue

                pos = raw_data.get("position", {})
                coords = pos.get("coordinates") if isinstance(pos, dict) else None

                topic = message.topic
                if "accommodation" in topic.lower():
                    target_index = "accommodations"
                    elk_document = {
                        "name": raw_data.get("name"),
                        "structure_type": raw_data.get("structure_type"),
                        "stars": raw_data.get("stars"),
                        "location": raw_data.get("location"),
                        "coordinates": coords,
                        "reviews": process_reviews(raw_data.get("reviews")),
                    }
                else:
                    target_index = "attractions"
                    elk_document = {
                        "name": raw_data.get("name"),
                        "category": raw_data.get("category"),
                        "description": raw_data.get("description"),
                        "location": raw_data.get("location"),
                        "coordinates": coords,
                        "reviews": process_reviews(raw_data.get("reviews")),
                    }

                index_in_elk(target_index, mongo_id, elk_document)
                if coords:
                    index_in_neo4j(target_index, mongo_id, elk_document["name"], coords)
                indexed_count += 1
                if indexed_count % 100 == 0:
                    print(f"[INFO] Successfully processed {indexed_count} total documents into ELK and Neo4j.")
            except json.JSONDecodeError:
                print("[WARNING] Impossibile decodificare il messaggio Kafka (JSON non valido).")
                continue
            except Exception as e:
                print(f"[ERROR] Errore durante l'elaborazione del singolo messaggio: {e}")
                continue


    except KeyboardInterrupt:
        print("\n[INFO] Stopping processor consumer group gracefully...")
    finally:
        consumer.close()
        neo4j_driver.close()
        print("[INFO] Connections closed. Pipeline process terminated.")


if __name__ == "__main__":
    main()