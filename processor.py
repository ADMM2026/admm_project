from kafka import KafkaConsumer
from elasticsearch import Elasticsearch
import json

consumer = KafkaConsumer(
    'Tourism.Tourism.accommodations',  
    'Tourism.Tourism.attractions',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    group_id='elk-processor-group'
)
es = Elasticsearch(
    ["http://localhost:9200"],
    headers={"Accept": "application/json", "Content-Type": "application/json"}
)

print("Python Intermediary ready and listening Debezium topics...")
indexed_count = 0

for message in consumer:
    if message.value is None:
        continue 
        
    try:
        debezium_payload = json.loads(message.value.decode('utf-8'))
    except Exception as e:
        print(f"JSON error: {e}")
        continue

    payload_data = debezium_payload.get("payload", debezium_payload) if isinstance(debezium_payload, dict) else debezium_payload
    
    if isinstance(payload_data, dict) and "after" in payload_data:
        raw_after = payload_data.get("after")
    elif isinstance(debezium_payload, dict) and "after" in debezium_payload:
        raw_after = debezium_payload.get("after")
    else:
        raw_after = payload_data

    if isinstance(raw_after, str):
        try:
            raw_data = json.loads(raw_after)
        except Exception as e:
            print(f"Impossibile to parse string 'after': {e}")
            continue
    elif isinstance(raw_after, dict):
        raw_data = raw_after
    else:
        print("unrecognized data structure, skipping record.")
        continue

    if not raw_data:
        continue

    topic = message.topic
    
    mongo_id = raw_data.get('_id')
    if isinstance(mongo_id, dict) and '$oid' in mongo_id:
        mongo_id = mongo_id['$oid']
    elif isinstance(mongo_id, str):
        if '"$oid"' in mongo_id:
            try:
                mongo_id = json.loads(mongo_id).get('$oid')
            except:
                pass

    if "accommodation" in topic.lower():
        target_index = "accommodations"
        elk_document = {
            "name": raw_data.get("name"),
            "structure_type": raw_data.get("structure_type"),
            "sector": raw_data.get("sector"),
            "stars": raw_data.get("stars"),
            "location": raw_data.get("location"),
            "capacity": raw_data.get("capacity") 
        }
    else:
        target_index = "attractions"
        elk_document = {
            "name": raw_data.get("name"),
            "category": raw_data.get("category"),
            "description": raw_data.get("description"),
            "location": raw_data.get("location")
        }
    
    position = raw_data.get("position")
    if isinstance(position, str):
        try:
            position = json.loads(position)
        except:
            position = None

    if isinstance(position, dict) and position.get("type") == "Point":
        coords = position.get("coordinates")  # Array [longitude, latitude]
        if coords and len(coords) == 2:
            elk_document["coordinates"] = coords

    try:
        es.index(index=target_index, id=str(mongo_id), document=elk_document)
        print(".", end="")
        indexed_count += 1
    except Exception as e:
        print(f"Error for document {mongo_id}: {e}")

