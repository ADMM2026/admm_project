import json
def extract_mongo_id(key):
    document_id = None
    try:
        key_data = json.loads(key.decode('utf-8'))
        raw_id_string = key_data.get("payload", {}).get("id")
        
        if raw_id_string:
            id_dict = json.loads(raw_id_string)
            document_id = id_dict.get("$oid")
            
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"[ERROR] Impossible parsing Kafka Key: {e}")

    return document_id
