import time
import requests
import json

CONNECT_URL = "http://localhost:8083/connectors"
ES_URL = "http://localhost:9200"

def init_elasticsearch_indices():
    mapping_template = {
        "mappings": {
            "properties": {
                "name": { "type": "text", "analyzer": "standard" },
                "location": {
                    "properties": {
                        "municipality": { "type": "text", "analyzer": "standard" },
                        "province": { "type": "text", "analyzer": "standard" }
                    }
                },
                "coordinates": { "type": "geo_point" }
            }
        }
    }

    for index_name in ["accommodations", "attractions"]:
        res = requests.put(f"{ES_URL}/{index_name}", json=mapping_template)
        if res.status_code == 200:
            print(f"ELK index '{index_name}' succesfully created.")
        else:
            print(f"ELK index '{index_name}' already existing or error: {res.text}")

def start_debezium():
    print("Waiting for Kafka Connect...")
    while True:
        try:
            if requests.get("http://localhost:8083/").status_code == 200:
                break
        except:
            pass
        time.sleep(2)
    
    with open("mongo-source.json", "r") as f:
        config = json.load(f)
    
    res = requests.put(f"{CONNECT_URL}/mongodb-source-connector/config", json=config["config"])
    if res.status_code in [200, 201]:
        print("Debezium Connettor started!")
    else:
        print(f"Debezium Error: {res.text}")

