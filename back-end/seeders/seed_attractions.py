import os
import csv
import random
import re
import unicodedata
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import json
from seeders.common import PIEDMONT_PROVINCES, locate_municipality, MongoEncoder
from pymongo import MongoClient
import argparse
from dotenv import load_dotenv

load_dotenv()

SOURCES = {
    "siti_unesco.csv": {"cat": "Siti UNESCO", "has_desc": True},
    "aree_storico_culturali_census.csv": {"cat": "Aree Storico Culturali", "has_desc": True},
    "beni_culturali_ambientali.csv": {"cat": "Beni Culturali Ambientali", "has_desc": True},
    "zone_archeologiche.csv": {"cat": "Zone Archeologiche", "has_desc": False},
    "centri_storici.csv": {"cat": "Centri Storici", "has_desc": False},
    "beni_architettonici-ubranistici-archeologici.csv": {"cat": "Beni Architettonici", "has_desc": False}
}

POSITION_FIELD = "position"
COLLECTION_NAME = "attractions"


def clean_string_for_image_name(s):
    if not s or pd.isna(s):
        return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(re.compile(r"['\s\-_]+"), "", s)
    return re.sub(re.compile(r"[^a-z0-9]"), "", s)


def generate_descriton_arc_item(row):
    cat = row.get('CAT', 'A')
    name = str(row.get('NOME', 'Bene')).lower()

    religious_styles = ["Romanico", "Barocco", "Gotico", "Rinascimentale"]
    civil_styles = ["Neoclassico", "Liberty", "Ottocentesco", "Settecentesco"]
    states = ["splendidamente conservato", "di immenso valore storico", "parzialmente alterato dal tempo",
              "caratteristico del paesaggio locale"]

    state = random.choice(states)
    if cat == 'A':
        return f"Interessante {name} di architettura sacra in stile {random.choice(religious_styles)}. Il sito è {state} e costituisce un punto di riferimento per la devozione locale."
    elif cat == 'B':
        return f"Struttura di natura difensiva catalogata como {name}. Questo avamposto militare testimonia le antiche fortificazioni storiche del territorio."
    elif cat == 'C':
        return f"Esempio di architettura civile rappresentato da un {name} in stile {random.choice(civil_styles)}. L'edificio, {state}, riflette l'evoluzione storica del borgo."
    elif cat == 'E':
        return f"Sito di rilevanza archeologica contenente un {name}. L'area conserva resti storici di eccezionale valore documentario per lo studio degli insediamenti antichi."
    return f"Manufatto storico catalogato come {name}, avente rilevanza sotto il profilo testimoniale e architettonico piemontese."


def generate_description_arc_zone(row):
    name = str(row.get('NOME', 'sito archeologico'))
    epochs = ["di età romana", "risalente all'età paleocristiana", "di epoca altomedievale",
              "con stratificazioni pre-romane"]
    details = ["oggetto di scavi e studi per il suo eccezionale valore",
               "che testimonia l'antico tessuto insediativo della zona",
               "tutelato per la rarità dei suoi reperti strutturali"]

    return f"{name}. Si tratta di un'area archeologica {random.choice(epochs)}, {random.choice(details)}."


def generate_description_historic_center(row):
    municipality = str(row.get('NOME', 'questo comune'))
    adjectives = ["caratteristico", "antico", "suggestivo", "storico"]
    elements = [
        "conserva l'impianto urbanistico originario ed elementi architettonici tipici della zona",
        "rappresenta un nucleo di antica formazione con importanti stratificazioni storiche",
        "si sviluppa attorno al nucleo originario del borgo, testimoniando la storia della comunità locale"
    ]
    return f"Il {random.choice(adjectives)} centro storico di {municipality} {random.choice(elements)} nel territorio piemontese."


def csv_to_mongo_json(dir_attractions_paths, file_municipalities_path):
    print("Loading municipality boundaries ISTAT...")
    reg_code = int(os.getenv("PIEDMONT_REG_CODE", 1))
    target_crs = os.getenv("GEO_EPSG_CRS", "epsg:4326")
    municipalities_italy = gpd.read_file(file_municipalities_path)
    municipalities_piedmont = municipalities_italy[municipalities_italy['COD_REG'] == reg_code].to_crs(target_crs)
    
    attractions = []
    
    for file_name, config in SOURCES.items():
        path_file = os.path.join(dir_attractions_paths, file_name)
        if not os.path.exists(path_file):
            print(f"File not found, skipping: {file_name}")
            continue

        print(f"{file_name} -> {config['cat']}")

        df = pd.read_csv(path_file, sep=';', quoting=csv.QUOTE_MINIMAL, on_bad_lines='skip')

        for _, row in df.iterrows():
            try:
                lon = float(row['longitude'])
                lat = float(row['latitude'])
            except (ValueError, KeyError):
                continue 

            municipality, province = locate_municipality(lon, lat, municipalities_piedmont)

            name = str(row.get('NOME', 'Bene Culturale')).strip()
            extra = {}
            description = ""

            if config['has_desc']:
                description = str(row.get('DESC', 'Nessuna descrizione disponibile.'))
                if config['cat'] == "Beni Culturali Ambientali":
                    extra['scope'] = str(row.get('TIPO', 'Generico'))
            else:
                if file_name == "zone_archeologiche.csv":
                    description = generate_description_arc_zone(row)
                    extra['cod'] = str(row.get('CODICE', ''))
                    extra['area_mq'] = float(row.get('AREA', 0))

                elif file_name == "centri_storici.csv":
                    description = generate_description_historic_center(row)

                elif file_name == "beni_architettonici-ubranistici-archeologici.csv":
                    description = generate_descriton_arc_item(row)
                    type_map = {'A': 'Opere Religiose', 'B': 'Opere Militari', 'C': 'Opere Civili',
                                'E': 'Beni Archeologici'}
                    extra['subcategory'] = type_map.get(row.get('CAT'), 'Altro')
                    extra['emergency'] = True if row.get('EMERG') == 'E' else False

            image_filename = None
            if config['cat'] in ["Siti UNESCO", "Aree Storico Culturali"]:
                image_filename = f"{clean_string_for_image_name(name)}.jpg"

            document_mongo = {
                "category": config['cat'],
                "name": name,
                "description": description,
                "location": {
                    "municipality": municipality.title(),
                    "province": province.upper()
                },
                POSITION_FIELD: {
                    "type": "Point",
                    "coordinates": [lon, lat]
                }
            }

            if image_filename:
                document_mongo["image"] = image_filename

            if extra:
                document_mongo["extra_info"] = extra

            attractions.append(document_mongo)
        
    return attractions

  
def main(args):
    attractions = csv_to_mongo_json(
        dir_attractions_paths=args.attractions_dir,
        file_municipalities_path=args.municipalities
    )

    mongo_client = MongoClient(args.mongo_uri)
    db = mongo_client[args.mongo_db]
    collection = db[COLLECTION_NAME]

    print(f"Database reset: removing data from collection '{COLLECTION_NAME}'...")
    collection.delete_many({}) 

    print(f"Creating geospatial index on '{POSITION_FIELD}'...")
    collection.create_index([(POSITION_FIELD, "2dsphere")])
    print(f"Inserting {len(attractions)} documents into '{COLLECTION_NAME}'...")
    result = collection.insert_many(attractions)
    print(f"[SUCCESS] Successfully inserted {len(result.inserted_ids)} attractions.")
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    print(f"Saving JSON backup to {args.output_json}...")
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(attractions, f, indent=4, ensure_ascii=False, cls=MongoEncoder)
    print(f"Completed. Stored {len(attractions)} attractions.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Seed MongoDB with attractions data.")
    
    parser.add_argument("--mongo-uri", type=str, 
                        default=os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"), 
                        help="MongoDB connection URI.")
    parser.add_argument("--mongo-db", type=str,
                        default=os.getenv("MONGO_DB_NAME", "Tourism"),
                        help="MongoDB database name.")
    parser.add_argument("--attractions_dir", type=str, 
                        default=os.path.join(script_dir, "raw_data", "attractions"),
                        help="Path to the directory containing attraction csv files.")
    parser.add_argument("--municipalities", type=str, 
                        default=os.path.join(script_dir, "raw_data", "municipalities", "Com01012026_g_WGS84.shp"),
                        help="Path to the ISTAT shapefile.")
    parser.add_argument("--output-json", type=str, 
                        default=os.path.join(script_dir, "data", "attractions_backup.json"),
                        help="Path where the JSON backup file will be saved.")
    
    args = parser.parse_args()
    main(args)