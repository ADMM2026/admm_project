import pandas as pd
import random
import json
import re
import geopandas as gpd
from pymongo import MongoClient
import os
import argparse
from seeders.common import PIEDMONT_PROVINCES, locate_municipality, MongoEncoder
from dotenv import load_dotenv


load_dotenv()

PIEMONT_PREFIXES = {
    "TO": "011",
    "VC": "0161",
    "NO": "0321",
    "CN": "0171",
    "AT": "0141",
    "AL": "0131",
    "BI": "015",
    "VB": "0323",
    "PIEMONTE": "011" 
}

NATURE_NAMES = {
    "animals": ["Cervo", "Volpe", "Aquila", "Orso", "Scoiattolo", "Cinghiale", "Lupo", "Marmotta", "Gufo", "Falco",
                "Airone", "Istrice"],
    "plants": ["Betulla", "Quercia", "Castagno", "Faggio", "Abete", "Larice", "Pino", "Glicine", "Agrifoglio", "Felce",
               "Edera", "Genziana"]
}
ADJECTIVES_COLORS = [
    "Dorato", "Verde", "Silenzioso", "Antico", "Segreto", "Odoroso", "Innevato", "Soleggiato",
    "Fiorito", "Alpino", "Rifugiato", "Incantato", "Bianco", "Rosso", "Azzurro", "Grande"
]

POSITION_FIELD = "position"
COLLECTION_NAME = "accommodations"


def generate_name(qualification):
    qualification_clean = qualification.lower()
    category_nature = random.choice(["animals", "plants"])
    core_name = random.choice(NATURE_NAMES[category_nature])
    adjective = random.choice(ADJECTIVES_COLORS)

    if core_name.endswith('a') or core_name in ["Volpe", "Felce", "Edera"]:
        if adjective.endswith('o'): adjective = adjective[:-1] + 'a'
    else:
        if adjective.endswith('a'): adjective = adjective[:-1] + 'o'

    if "rifugio" in qualification_clean:
        return f"Rifugio {core_name} {adjective}"
    elif "bed" in qualification_clean or "b&b" in qualification_clean:
        return f"B&B Il {core_name} {adjective}" if not core_name.endswith(
            'a') else f"B&B La {core_name} {adjective}"
    elif "albergo" in qualification_clean or "hotel" in qualification_clean:
        return f"Albergo {core_name} {adjective}"
    elif "agriturismo" in qualification_clean:
        return f"Agriturismo {core_name} {adjective}"
    else:
        prefix = random.choice(["Residenza", "Dimora", "La Casa del", "Il Nido del"])
        if "Casa" in prefix or "Dimora" in prefix or "Residenza" in prefix:
            if adjective.endswith('o'): adjective = adjective[:-1] + 'a'
        return f"{prefix} {core_name} {adjective}"


def clean_stars(category):
    match = re.search(r'\d', category)
    if match:
        return int(match.group())
    return random.randint(1, 5)


def generate_email(name):
    name_clean = name.replace("B&B ", "").replace("Albergo ", "").replace("Rifugio ", "").replace(
        "Agriturismo ", "")
    name_slug = name_clean.lower().strip()
    name_slug = re.sub(r'[^a-z0-9]', '', name_slug)  
    domain = random.choice(["gmail.com", "outlook.it", f"{name_slug}.it", "yahoo.com"])
    if domain.startswith(name_slug):
        return f"info@{domain}"
    return f"{name_slug}@{domain}"


def generate_phone_number(province):
    prefix = PIEMONT_PREFIXES.get(province, "011")
    length = random.choice([6, 7])
    number = "".join([str(random.randint(0, 9)) for _ in range(length)])
    return f"{prefix} {number}"

def csv_to_mongo_json(file_locations_path, file_details_path, file_municipalities_path):
    print("Loading municipality boundaries ISTAT...")
    reg_code = int(os.getenv("PIEDMONT_REG_CODE", 1))
    target_crs = os.getenv("GEO_EPSG_CRS", "epsg:4326")

    municipalities_italy = gpd.read_file(file_municipalities_path)
    municipalities_piedmont = municipalities_italy[municipalities_italy['COD_REG'] == reg_code].to_crs(target_crs)

    df_locations = pd.read_csv(file_locations_path, sep=';', encoding='utf-8')
    df_details = pd.read_csv(file_details_path, sep=';', encoding='utf-8')

    df_locations.columns = df_locations.columns.str.strip()
    df_details.columns = df_details.columns.str.strip()

    df_details['comune'] = df_details['comune'].str.strip().str.upper()
    df_details['sigla_prov'] = df_details['sigla_prov'].str.strip().str.upper()

    
    queues_municipalities = {}  
    queues_provinces = {}  
    queue_region = []  

    queue_region = df_details.to_dict('records')
    random.shuffle(queue_region)

    for municp, group in df_details.groupby('comune'):
        queues_municipalities[municp] = group.to_dict('records')

    for prov, group in df_details.groupby('sigla_prov'):
        queues_provinces[prov] = group.to_dict('records')

    accommodations = []
    used_rows = set()

    for _, row in df_locations.iterrows():
        lon = float(row['longitude'])
        lat = float(row['latitude'])

        municipality = "NON SPECIFICATO"
        province = "PIEMONTE"

        try:
            municipality, province = locate_municipality(lon, lat, municipalities_piedmont)
        except Exception:
            if pd.notna(row['COMUNE']):
                municipality = str(row['COMUNE']).strip().upper()

        info_extra = None

        if municipality in queues_municipalities and len(queues_municipalities[municipality]) > 0:
            info_extra = queues_municipalities[municipality].pop(0)
            used_rows.add(
                (info_extra['comune'], info_extra['qualifica'], info_extra['letti'], info_extra['camere']))

        if info_extra is None and province in queues_provinces:
            while len(queues_provinces[province]) > 0:
                prov_row = queues_provinces[province].pop(0)
                key = (prov_row['comune'], prov_row['qualifica'], prov_row['letti'], prov_row['camere'])
                if key not in used_rows:
                    info_extra = prov_row
                    used_rows.add(key)
                    break

        if info_extra is None:
            while len(queue_region) > 0:
                reg_row = queue_region.pop(0)
                key = (reg_row['comune'], reg_row['qualifica'], reg_row['letti'], reg_row['camere'])
                if key not in used_rows:
                    info_extra = reg_row
                    used_rows.add(key)
                    break

        if info_extra is None:
            info_extra = df_details.iloc[random.randint(0, len(df_details) - 1)].to_dict()

        structure_type = str(info_extra.get('qualifica', 'Albergo')).strip()
        sector = str(info_extra.get('settore', 'SETTORE ALBERGHIERO')).strip()
        stars = clean_stars(info_extra.get('categoria'))
        rooms = int(info_extra.get('camere', 10))
        beds = int(info_extra.get('letti', 20))

        name = generate_name(structure_type)
        phone = generate_phone_number(province.upper())
        email = generate_email(name)

        document_mongo = {
            "name": name,
            "structure_type": structure_type,
            "sector": sector,
            "stars": stars,
            "location": {
                "municipality": municipality.title(),
                "province": province.upper()
            },
            POSITION_FIELD: {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "capacity": {
                "rooms": rooms,
                "beds": beds
            },
            "contacts": {
                "phone": phone,
                "email": email,
                "website": f"www.{email.split('@')[1]}" if "gmail" not in email and "outlook" not in email and "yahoo" not in email else ""
            },
            "last_reviews": [],
            "reviews": []
        }

        accommodations.append(document_mongo)
    return accommodations

    
    
def main(args):
    accommodations = csv_to_mongo_json(
        file_locations_path=args.locations,
        file_details_path=args.details,
        file_municipalities_path=args.municipalities
    )

    mongo_client = MongoClient(args.mongo_uri)
    db = mongo_client[args.mongo_db]
    collection = db[COLLECTION_NAME]

    print(f"Database reset: removing data from collection '{COLLECTION_NAME}'...")
    collection.delete_many({}) 

    
    print(f"Inserting {len(accommodations)} documents into '{COLLECTION_NAME}'...")
    result = collection.insert_many(accommodations)
    print(f"[SUCCESS] Successfully inserted {len(result.inserted_ids)} accommodations.")
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    print(f"Saving JSON backup to {args.output_json}...")
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(accommodations, f, indent=4, ensure_ascii=False, cls=MongoEncoder)
    print(f"Completed. Stored {len(accommodations)} accommodations.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Seed MongoDB with accommodations data from regional CSV files.")
    
    parser.add_argument("--mongo-uri", type=str, 
                        default=os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"), 
                        help="MongoDB connection URI.")
    parser.add_argument("--mongo-db", type=str,
                        default=os.getenv("MONGO_DB_NAME", "Tourism"),
                        help="MongoDB database name.")
    parser.add_argument("--locations", type=str, 
                        default=os.path.join(script_dir, "raw_data", "accommodations", "villeggiatura_losir.csv"),
                        help="Path to the file containing geolocations.")
    parser.add_argument("--details", type=str, 
                        default=os.path.join(script_dir, "raw_data", "accommodations", "offerta_ricettiva_comuni.csv"),
                        help="Path to the file containing descriptive data.")
    parser.add_argument("--municipalities", type=str, 
                        default=os.path.join(script_dir, "raw_data", "municipalities", "Com01012026_g_WGS84.shp"),
                        help="Path to the ISTAT shapefile.")
    parser.add_argument("--output-json", type=str, 
                        default=os.path.join(script_dir, "data", "accommodations_backup.json"),
                        help="Path where the JSON backup file will be saved.")
    
    args = parser.parse_args()
    main(args)
