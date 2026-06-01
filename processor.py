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
es = Elasticsearch(["http://localhost:9200"])

print("Intermediario Python pronto e in ascolto sui topic nativi di Debezium... 🐍")

for message in consumer:
    if message.value is None:
        continue 
        
    try:
        # Decodifica il payload principale inviato da Debezium
        debezium_payload = json.loads(message.value.decode('utf-8'))
    except Exception as e:
        print(f"Errore nella decodifica JSON del messaggio: {e}")
        continue

    # Debezium inserisce i dati dentro l'oggetto "after" o direttamente nel "payload"
    payload_data = debezium_payload.get("payload", debezium_payload) if isinstance(debezium_payload, dict) else debezium_payload
    
    if isinstance(payload_data, dict) and "after" in payload_data:
        raw_after = payload_data.get("after")
    elif isinstance(debezium_payload, dict) and "after" in debezium_payload:
        raw_after = debezium_payload.get("after")
    else:
        raw_after = payload_data

    # Debezium per MongoDB invia il campo 'after' come STRINGA JSON serializzata
    if isinstance(raw_after, str):
        try:
            raw_data = json.loads(raw_after)
        except Exception as e:
            print(f"Impossibile parsare la stringa 'after': {e}")
            continue
    elif isinstance(raw_after, dict):
        raw_data = raw_after
    else:
        print("Struttura dati non riconosciuta, salto il record.")
        continue

    if not raw_data:
        continue

    topic = message.topic
    
    # Estrazione dell'ID MongoDB (gestisce stringhe, dizionari o l'_id nel formato standard del seeder)
    mongo_id = raw_data.get('_id')
    if isinstance(mongo_id, dict) and '$oid' in mongo_id:
        mongo_id = mongo_id['$oid']
    elif isinstance(mongo_id, str):
        # Se il seeder usa stringhe pulite come "ALL_0001", lo teniamo così com'è
        if '"$oid"' in mongo_id:
            try:
                mongo_id = json.loads(mongo_id).get('$oid')
            except:
                pass

    # Identifichiamo l'indice in base al topic reale (controllo case-insensitive)
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
    
    # Estrazione e normalizzazione del GeoJSON per il tipo geo_point di Elasticsearch
    position = raw_data.get("position")
    if isinstance(position, str):
        try:
            position = json.loads(position)
        except:
            position = None

    if isinstance(position, dict) and position.get("type") == "Point":
        coords = position.get("coordinates")  # Array [longitude, latitude]
        if coords and len(coords) == 2:
            # Elasticsearch accetta il formato geo_point sia come array [lon, lat] che come stringa/dict
            elk_document["coordinates"] = coords

    try:
        es.index(index=target_index, id=str(mongo_id), document=elk_document)
        print(f"[{target_index.upper()}] Sincronizzato ID: {mongo_id} su ELK ✅")
    except Exception as e:
        print(f"Errore durante l'indicizzazione su ELK per ID {mongo_id}: {e}")