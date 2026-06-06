import json
import os
from kafka import KafkaConsumer
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

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
    payload = debezium_payload.get("payload", debezium_payload)
    
    op = payload.get("op")
    if op == "d":
        return None

    raw_after = payload.get("after")

    if isinstance(raw_after, str):
        try:
            raw_after = json.loads(raw_after)
        except Exception:
            pass

    return raw_after

def main():
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
    consumer = KafkaConsumer(
        'Tourism.Tourism.accommodations',
        'Tourism.Tourism.attractions',
        bootstrap_servers=kafka_servers,
        auto_offset_reset='earliest',
        group_id='elk-processor-group',
        api_version=(2, 5, 0),
        max_poll_records=100,
        max_partition_fetch_bytes=1048576,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None,
    )

    es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    es = Elasticsearch(
        [es_url],
        headers={"Accept": "application/json", "Content-Type": "application/json"}
    )

    print(f"Python Intermediary ready (Kafka: {kafka_servers}, ES: {es_url}). Listening topics...")
    indexed_count = 0

    for message in consumer:
        if message.value is None:
            continue

        debezium_payload = message.value 

        raw_data = extract_after(debezium_payload)
        if not raw_data:
            continue

        mongo_id = extract_mongo_id(raw_data.get("_id"))
        if not mongo_id:
            print("[WARNING] Skipping document: unable to extract valid MongoDB ID.")
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

        try:
            es.index(index=target_index, id=mongo_id, body=elk_document)
            indexed_count += 1
            if indexed_count % 100 == 0:
                print(f"[INFO] Indexed {indexed_count} total documents into Elasticsearch.")
        except Exception as e:
            print(f"[ERROR] Failed to index document {mongo_id} into ELK: {e}")

if __name__ == "__main__":
    main()