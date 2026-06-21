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
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
es_user = os.getenv("ES_USER")
es_password = os.getenv("ES_PASSWORD")
auth = (es_user, es_password) if es_user and es_password else None

es_client = Elasticsearch(es_url, basic_auth=auth, verify_certs=False)


def extract_mongo_id(payload):
    """
    Estrae l'ObjectId MongoDB dal payload Debezium.
    Prova prima da 'after', poi da 'before', poi da 'documentKey'/'filter'.
    Il formato atteso dell'_id è: {"$oid": "..."} oppure una stringa diretta.
    """
    for field in ("after", "before"):
        raw = payload.get(field)
        if raw:
            try:
                data = json.loads(raw)
                oid = data.get("_id")
                if isinstance(oid, dict):
                    return oid.get("$oid") or str(oid)
                if oid:
                    return str(oid)
            except (json.JSONDecodeError, AttributeError):
                pass

    for field in ("documentKey", "filter"):
        raw = payload.get(field)
        if raw:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                oid = data.get("_id")
                if isinstance(oid, dict):
                    return oid.get("$oid") or str(oid)
                if oid:
                    return str(oid)
            except (json.JSONDecodeError, AttributeError):
                pass

    return None


def process_reviews(raw_reviews) -> list[str]:
    if isinstance(raw_reviews, list):
        return [str(r).strip() for r in raw_reviews if r]
    return []


def main():
    print("[ELK PROCESSOR] Starting independent full-text indexing consumer...")

    consumer = KafkaConsumer(
        "Tourism.Tourism.accommodations",
        "Tourism.Tourism.attractions",
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(","),
        group_id="elk-processor-group",
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
                target_index = "accommodations" if "accommodations" in topic else "attractions"

                mongo_id = extract_mongo_id(payload)
                if not mongo_id:
                    print(f"[ELK WARNING] Could not extract _id from payload, skipping. op={op}")
                    continue

                if op == "d":
                    print(f"[ELK] Detected DELETE for ID {mongo_id} in {target_index}")
                    if es_client.exists(index=target_index, id=mongo_id):
                        es_client.delete(index=target_index, id=mongo_id)
                    continue

                after_str = payload.get("after")
                if not after_str:
                    continue

                raw_data = json.loads(after_str)

                pos = raw_data.get("position", {})
                coords = pos.get("coordinates") if isinstance(pos, dict) else None

                if target_index == "accommodations":
                    elk_document = {
                        "name": raw_data.get("name"),
                        "structure_type": raw_data.get("structure_type"),
                        "stars": raw_data.get("stars"),
                        "location": raw_data.get("location"),
                        "coordinates": coords,
                        "reviews": process_reviews(raw_data.get("reviews")),
                    }
                else:
                    elk_document = {
                        "name": raw_data.get("name"),
                        "category": raw_data.get("category"),
                        "description": raw_data.get("description"),
                        "location": raw_data.get("location"),
                        "coordinates": coords,
                        "reviews": process_reviews(raw_data.get("reviews")),
                    }

                es_client.index(index=target_index, id=mongo_id, document=elk_document)
                print(f"[ELK SUCCESS] Indexed {target_index} ID: {mongo_id} [Op: {op}]")

            except Exception as e:
                print(f"[ELK ERROR] Failed to process message: {e}")
                continue

    except KeyboardInterrupt:
        print("\n[ELK] Stopping consumer gracefully...")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()