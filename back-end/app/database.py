import os
import urllib3
from pymongo import MongoClient
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_mongo_client = None
_es_client = None


def get_mongo():
    global _mongo_client
    if _mongo_client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        _mongo_client = MongoClient(uri)
    return _mongo_client[os.getenv("MONGO_DB_NAME", "Tourism")]


def get_es() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        es_user = os.getenv("ES_USER")
        es_password = os.getenv("ES_PASSWORD")
        auth = (es_user, es_password) if es_user and es_password else None

        _es_client = Elasticsearch(
            es_url,
            basic_auth=auth,
            verify_certs=False,
        )
    return _es_client