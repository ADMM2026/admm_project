import time
import requests
import json
import copy
import os
from dotenv import load_dotenv
from kafka import KafkaAdminClient
from kafka.errors import UnknownTopicOrPartitionError
from neo4j import GraphDatabase


load_dotenv()

CONNECT_URL = os.getenv("KAFKA_CONNECT_URL", "http://localhost:8083/connectors")
if not CONNECT_URL.endswith("/connectors") and "localhost:8083" in CONNECT_URL:
    CONNECT_URL = f"{CONNECT_URL.rstrip('/')}/connectors"
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")


def reset_neo4j(fresh_start=False):
    if not fresh_start:
        return

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "admin")
    password = os.getenv("NEO4J_PASSWORD", "password")

    print("[INFO] Cleaning up Neo4j Graph Database (--fresh)...")
    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
                print("[SUCCESS] Neo4j database cleared successfully.")
    except Exception as e:
        print(f"[WARNING] Could not clear Neo4j: {e}")


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
                "name": {"type": "text", "analyzer": "italian"},
                "reviews": {"type": "text", "analyzer": "italian"},
                "coordinates": {"type": "geo_point"},
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

    mapping_accommodations = copy.deepcopy(mapping_template)
    mapping_accommodations["mappings"]["properties"]["structure_type"] = {"type": "keyword"}
    mapping_accommodations["mappings"]["properties"]["stars"] = {"type": "integer"}

    mapping_attractions = copy.deepcopy(mapping_template)
    mapping_attractions["mappings"]["properties"]["category"] = {
        "type": "text",
        "analyzer": "italian",
        "fields": {
            "keyword": {"type": "keyword"}
        }
    }
    mapping_attractions["mappings"]["properties"]["description"] = {"type": "text", "analyzer": "italian"}

    index_names = ["accommodations", "attractions"]
    mappings = [mapping_accommodations, mapping_attractions]

    for index_name, mapping in zip(index_names, mappings):
        index_url = f"{ES_URL}/{index_name}"
        try:
            check_res = requests.head(index_url)
            index_exists = (check_res.status_code == 200)
        except requests.exceptions.ConnectionError:
            print("[ERROR] Cannot connect to Elasticsearch. Is it running?")
            return

        if index_exists:
            if fresh_start:
                print(f"Removing old ELK index '{index_name}'...")
                del_res = requests.delete(index_url)
                if del_res.status_code != 200:
                    print(f"[ERROR] Could not delete '{index_name}': {del_res.text}")
                    continue
            else:
                print(f"ELK index '{index_name}' already exists.")
                continue

        res = requests.put(index_url, json=mapping)
        if res.status_code in [200, 201]:
            print(f"[SUCCESS] ELK index '{index_name}' created.")
        else:
            print(f"[ERROR] Failed to create ELK index '{index_name}': {res.text}")


def start_debezium(fresh_start=False):
    connect_base = os.getenv("KAFKA_CONNECT_URL", "http://localhost:8083/connectors")
    connect_base_root = connect_base.replace("/connectors", "").rstrip("/")

    print("Waiting for Kafka Connect...")
    while True:
        try:
            if requests.get(f"{connect_base_root}/").status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mongo-source.json")
    if not os.path.exists(config_path):
        print(f"[WARNING] Debezium config file not found at '{config_path}'. Skipping Debezium init.")
        return

    with open(config_path, "r") as f:
        config_data = json.load(f)

    connector_name = config_data.get("name", "mongodb-source-connector")
    connector_url = f"{CONNECT_URL}/{connector_name}"

    try:
        check_connector = requests.get(connector_url)
        if check_connector.status_code == 200:
            if fresh_start:
                print(f"[{connector_name}] already exists. '--fresh' active: deleting old connector...")
                del_res = requests.delete(connector_url)
                if del_res.status_code in [200, 204]:
                    print(f"[SUCCESS] Deleted old Debezium connector '{connector_name}'.")
                    time.sleep(1)
                else:
                    print(f"[ERROR] Failed to delete old connector: {del_res.text}")
                    return
            else:
                print(f"Debezium connector '{connector_name}' is already configured. Skipping init.")
                return

        res = requests.post(CONNECT_URL, json=config_data)
        if res.status_code in [200, 201]:
            print(f"[SUCCESS] Debezium MongoDB source connector submitted.")
        else:
            print(f"[ERROR] Failed to start Debezium connector: {res.text}")

    except Exception as e:
        print(f"[ERROR] Debezium initialization failed: {e}")


def reset_kafka(fresh_start=False):
    if not fresh_start:
        return

    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
    topics_to_delete = [
        "Tourism.Tourism.accommodations",
        "Tourism.Tourism.attractions"
    ]
    consumer_group = "elk-processor-group"
    try:
        admin = KafkaAdminClient(bootstrap_servers=kafka_servers)
        try:
            admin.delete_consumer_groups([consumer_group])
            print(f"[SUCCESS] Deleted consumer group '{consumer_group}'.")
        except Exception as e:
            print(f"[WARNING] Could not delete consumer group: {e}")
        try:
            admin.delete_topics(topics_to_delete)
            print(f"[SUCCESS] Deleted Kafka topics.")
        except UnknownTopicOrPartitionError:
            print("[INFO] Kafka topics didn't exist, skipping.")
        except Exception as e:
            print(f"[WARNING] Could not delete topics: {e}")

        admin.close()
        time.sleep(3)
    except Exception as e:
        print(f"[ERROR] Kafka reset failed: {e}")