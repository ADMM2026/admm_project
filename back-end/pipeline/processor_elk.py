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
from common import extract_mongo_id

load_dotenv()

es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
es_client = Elasticsearch(es_url, verify_certs=False)


def process_reviews(raw_reviews) -> list[str]:
    if isinstance(raw_reviews, list):
        return [str(r["text"]).strip() for r in raw_reviews if r]
    return []


def main():
    print("[ELK PROCESSOR] Starting full-text indexing consumer...")

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

                mongo_id = extract_mongo_id(message.key)
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

                data = json.loads(after_str)

                pos = data.get("position", {})
                coords = pos.get("coordinates") if isinstance(pos, dict) else None

                if target_index == "accommodations":
                    elk_document = {
                        "name": data.get("name"),
                        "structure_type": data.get("structure_type"),
                        "stars": data.get("stars"),
                        "location": data.get("location"),
                        "coordinates": coords,
                        "reviews": process_reviews(data.get("last_reviews")),
                    }
                else:
                    elk_document = {
                        "name": data.get("name"),
                        "category": data.get("category"),
                        "description": data.get("description"),
                        "location": data.get("location"),
                        "coordinates": coords,
                        "reviews": process_reviews(data.get("last_reviews")),
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