import time
import requests
import json
import copy

CONNECT_URL = "http://localhost:8083/connectors"
ES_URL = "http://localhost:9200"

def init_elasticsearch_indices(fresh_start=False):
    mapping_template = {
        "settings": {
            "analysis": {
                "filter": {
                    "provinces_synonyms": {
                        "type": "synonym",
                        "synonyms": [
                            "to, torino",
                            "al, alessandria",
                            "at, asti",
                            "cn, cuneo",
                            "no, novara",
                            "vc, vercelli",
                            "bi, biella",
                            "vb, verbano, cusio, ossola"
                        ]
                    }
                },
                "analyzer": {
                    "province_analyzer": {
                        "tokenizer": "standard",
                        "filter": ["lowercase", "provinces_synonyms"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "name": { "type": "text", "analyzer": "italian" },
                "reviews": {"type": "text", "analyzer": "italian"},
                "coordinates": { "type": "geo_point" },
                "location": {
                    "properties": {
                        "municipality": {
                            "type": "text",
                            "analyzer": "italian",  
                                "fields": {
                                    "keyword": {"type": "keyword"}  
                                }
                            },
                        "province": {
                            "type": "text",
                            "analyzer": "province_analyzer",  
                                "fields": {
                                    "keyword": {"type": "keyword"}  
                                }
                            }
                    }
                }
            }
        }
    }

    mapping_attractions = copy.deepcopy(mapping_template)
    mapping_attractions["mappings"]["properties"]["category"] = {
                            "type": "text",
                            "analyzer": "italian",  
                                "fields": {
                                    "keyword": {"type": "keyword"}  
                                }
                            }
    mapping_attractions["mappings"]["properties"]["description"] = { "type": "text", "analyzer": "italian" }


    mapping_accommodations = copy.deepcopy(mapping_template)  
    mapping_accommodations["mappings"]["properties"]["structure_type"] = {"type": "keyword"}
    mapping_accommodations["mappings"]["properties"]["stars"] = { "type": "integer" }

    index_names = ["accommodations", "attractions"]
    mappings = [mapping_accommodations, mapping_attractions]

    for (index_name, mapping) in zip(index_names, mappings):
        index_url = f"{ES_URL}/{index_name}"
        check_res = requests.head(index_url)
        index_exists = (check_res.status_code == 200)

        if index_exists:
            if fresh_start:
                print(f"Removing old ELK index '{index_name}'...")
                delete_res = requests.delete(index_url)
                if delete_res.status_code != 200:
                    print(f"Impossible to remove '{index_name}': {delete_res.text}")
                    continue
            else:
                print(f"ELK index '{index_name}' already exists.")
                continue # 

        res = requests.put(index_url, json=mapping)
        if res.status_code in [200, 201]:
            print(f"ELK index '{index_name}' created.")
        else:
            print(f"Error during ELK index creation '{index_name}': {res.text}")

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

