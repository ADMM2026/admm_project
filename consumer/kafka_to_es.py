"""
Kafka → Elasticsearch consumer.

Legge i change events prodotti da Debezium (topic tourism.tourism.*),
applica trasformazioni custom documento per documento, e indicizza su ES.

Per aggiungere/modificare trasformazioni: editare le funzioni
  transform_accomodation(doc)  e  transform_attraction(doc)
"""

import json
import logging
import os
import signal
import sys
import time

from elasticsearch import Elasticsearch, helpers
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

# ---------------------------------------------------------------------------
# Configurazione (da environment o default)
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPICS    = os.getenv(
    "KAFKA_TOPICS",
    "tourism.tourism.accomodations,tourism.tourism.attractions"
).split(",")
KAFKA_GROUP_ID  = os.getenv("KAFKA_GROUP_ID", "es-consumer-group")

ES_HOST         = os.getenv("ES_HOST", "http://elasticsearch:9200")

INDEX_MAP = {
    "tourism.tourism.accomodations": "accomodations",
    "tourism.tourism.attractions":   "attractions",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("consumer")

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_running = True

def _handle_signal(sig, frame):
    global _running
    log.info("Signal received, shutting down...")
    _running = False

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)

# ---------------------------------------------------------------------------
# Trasformazioni  ← MODIFICA QUI per cambiare la struttura dei documenti ES
# ---------------------------------------------------------------------------

def _avg_rating(reviews: list) -> float | None:
    """Calcola il rating medio da una lista di review con campo 'rating'."""
    ratings = [r["rating"] for r in reviews if isinstance(r, dict) and "rating" in r]
    return round(sum(ratings) / len(ratings), 2) if ratings else None


def transform_accomodation(after: dict) -> dict:
    """
    Trasforma un documento MongoDB 'accomodations' nel documento ES.
    Aggiungere/rimuovere campi liberamente qui.
    """
    coordinates = after.get("position", {}).get("coordinates", [None, None])
    reviews     = after.get("reviews", [])
    avg         = _avg_rating(reviews)

    doc = {
        "name":           after.get("name"),
        "structure_type": after.get("structure_type"),
        "sector":         after.get("sector"),
        "stars":          after.get("stars"),
        "location":       after.get("location"),           # { municipality, province }
        "geo_point": {                                     # campo geo_point ES
            "lat": coordinates[1],
            "lon": coordinates[0],
        } if coordinates[0] is not None else None,
        "capacity":       after.get("capacity"),           # { rooms, beds }
        "contacts":       after.get("contacts"),           # { phone, email, website }
        "review_count":   len(reviews),
    }

    if avg is not None:
        doc["avg_rating"] = avg

    # Rimuovi campi None per non sporcare l'indice
    return {k: v for k, v in doc.items() if v is not None}


def transform_attraction(after: dict) -> dict:
    """
    Trasforma un documento MongoDB 'attractions' nel documento ES.
    Aggiungere/rimuovere campi liberamente qui.
    """
    coordinates = after.get("position", {}).get("coordinates", [None, None])

    doc = {
        "name":        after.get("name"),
        "category":    after.get("category"),
        "description": after.get("description"),
        "location":    after.get("location"),              # { municipality, province }
        "geo_point": {
            "lat": coordinates[1],
            "lon": coordinates[0],
        } if coordinates[0] is not None else None,
        "image":       after.get("image"),
        "extra_info":  after.get("extra_info"),
    }

    return {k: v for k, v in doc.items() if v is not None}


# Dispatch per topic → funzione di trasformazione
TRANSFORM_FN = {
    "tourism.tourism.accomodations": transform_accomodation,
    "tourism.tourism.attractions":   transform_attraction,
}

# ---------------------------------------------------------------------------
# Parsing del messaggio Debezium
# ---------------------------------------------------------------------------

def parse_debezium_message(raw_value: bytes) -> tuple[str, dict | None] | None:
    """
    Ritorna (op, document) dove:
      op       = 'c' (create), 'u' (update), 'r' (snapshot read), 'd' (delete)
      document = il contenuto 'after' già deserializzato, oppure None se delete
    Ritorna None se il messaggio non è parsabile o va ignorato.
    """
    try:
        msg = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        log.warning("Non-JSON message, skipping.")
        return None

    # Debezium wrappa i valori MongoDB come stringa JSON all'interno del campo
    op    = msg.get("op")
    after = msg.get("after")

    if op is None:
        return None  # messaggio di sistema/heartbeat

    # 'after' può essere una stringa JSON (formato Debezium MongoDB)
    if isinstance(after, str):
        try:
            after = json.loads(after)
        except json.JSONDecodeError:
            return None

    return op, after


def extract_doc_id(msg_key: bytes | None, after: dict | None) -> str | None:
    """Recupera l'_id del documento da usare come _id in ES."""
    if after and "_id" in after:
        raw_id = after["_id"]
        # Debezium MongoDB serializza _id come { "$oid": "..." } o stringa
        if isinstance(raw_id, dict):
            return str(raw_id.get("$oid") or next(iter(raw_id.values()), None))
        return str(raw_id)
    if msg_key:
        try:
            key = json.loads(msg_key)
            payload = key.get("payload") or key
            doc_id  = payload.get("id") or payload.get("_id")
            if isinstance(doc_id, dict):
                return str(next(iter(doc_id.values()), None))
            return str(doc_id) if doc_id else None
        except (json.JSONDecodeError, AttributeError):
            pass
    return None

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def wait_for_kafka(bootstrap: str, retries: int = 20, delay: int = 5) -> KafkaConsumer:
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                *KAFKA_TOPICS,
                bootstrap_servers=bootstrap,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda v: v,   # raw bytes, parse manually
                key_deserializer=lambda k: k,
                consumer_timeout_ms=1000,
            )
            log.info("Connected to Kafka at %s", bootstrap)
            return consumer
        except NoBrokersAvailable:
            log.info("Kafka not ready yet (attempt %d/%d), retrying in %ds...", attempt, retries, delay)
            time.sleep(delay)
    log.error("Could not connect to Kafka after %d attempts. Exiting.", retries)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    es = Elasticsearch(ES_HOST)
    log.info("Connected to Elasticsearch at %s", ES_HOST)

    consumer = wait_for_kafka(KAFKA_BOOTSTRAP)
    log.info("Subscribed to topics: %s", KAFKA_TOPICS)

    buffer: list[dict] = []
    BATCH_SIZE  = int(os.getenv("CONSUMER_BATCH_SIZE", "50"))
    FLUSH_SECS  = float(os.getenv("CONSUMER_FLUSH_SECS", "2.0"))
    last_flush  = time.monotonic()

    def flush_buffer():
        nonlocal buffer, last_flush
        if not buffer:
            return
        try:
            ok, errors = helpers.bulk(es, buffer, raise_on_error=False)
            if errors:
                log.warning("Bulk errors: %s", errors[:3])
            else:
                log.info("Indexed %d document(s)", ok)
        except Exception as exc:
            log.error("Bulk index failed: %s", exc)
        buffer = []
        last_flush = time.monotonic()

    while _running:
        try:
            for msg in consumer:
                if not _running:
                    break

                topic = msg.topic
                index = INDEX_MAP.get(topic)
                if index is None:
                    continue

                parsed = parse_debezium_message(msg.value)
                if parsed is None:
                    continue

                op, after = parsed

                if op == "d":
                    # Delete: rimuovi da ES
                    doc_id = extract_doc_id(msg.key, None)
                    if doc_id:
                        buffer.append({
                            "_op_type": "delete",
                            "_index":   index,
                            "_id":      doc_id,
                        })
                    continue

                if after is None:
                    continue

                transform_fn = TRANSFORM_FN.get(topic)
                if transform_fn is None:
                    continue

                try:
                    transformed = transform_fn(after)
                except Exception as exc:
                    log.warning("Transform failed for topic %s: %s", topic, exc)
                    continue

                doc_id = extract_doc_id(msg.key, after)

                action = {
                    "_op_type": "index",
                    "_index":   index,
                    "_source":  transformed,
                }
                if doc_id:
                    action["_id"] = doc_id

                buffer.append(action)

                # Flush per batch size o timeout
                if len(buffer) >= BATCH_SIZE or (time.monotonic() - last_flush) >= FLUSH_SECS:
                    flush_buffer()

            # consumer_timeout_ms scaduto (nessun messaggio nel ciclo)
            if (time.monotonic() - last_flush) >= FLUSH_SECS:
                flush_buffer()

        except Exception as exc:
            log.error("Unexpected error in consumer loop: %s", exc, exc_info=True)
            time.sleep(2)

    flush_buffer()
    consumer.close()
    log.info("Consumer stopped cleanly.")


if __name__ == "__main__":
    main()
