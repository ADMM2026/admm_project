from shapely.geometry import Point
from bson import ObjectId
import json
import random
from datetime import datetime, timezone, timedelta

REVIEW_USERNAMES = [
    "marco_t", "giuly92", "traveler_luca", "silvia.b", "wanderer_pie",
    "ale_piemonte", "fra_explorer", "marta_v", "giorgio88", "elena_tours"
]

REVIEW_TEXTS = {
    "accommodations": [
        "Struttura accogliente e ben tenuta, personale molto disponibile.",
        "Ottimo rapporto qualità-prezzo, ci torneremo sicuramente.",
        "Posizione comoda, colazione abbondante. Consigliato.",
        "Camera pulita e silenziosa, ideale per una sosta.",
        "Servizio nella norma, niente di speciale ma nel complesso soddisfacente.",
        "Struttura un po' datata ma gestione familiare calorosa.",
        "Ottima accoglienza, ci siamo sentiti subito a casa.",
    ],
    "attractions": [
        "Luogo davvero suggestivo, vale assolutamente la visita.",
        "Ben conservato e ricco di storia, visita molto interessante.",
        "Paesaggio mozzafiato, consiglio di andarci al tramonto.",
        "Sito affascinante, pannelli informativi un po' scarsi.",
        "Esperienza unica, perfetto per chi ama la storia locale.",
        "Meno conosciuto di altri ma decisamente da scoprire.",
        "Ottima tappa durante un tour del Piemonte.",
    ]
}

PIEDMONT_PROVINCES = {
    201: "TO",   # Torino
    2: "VC",     # Vercelli
    3: "NO",     # Novara
    4: "CN",     # Cuneo
    5: "AT",     # Asti
    6: "AL",     # Alessandria
    96: "BI",    # Biella
    103: "VB"    # Verbano-Cusio-Ossola
}

def locate_municipality(lon, lat, piedmont_municipalities):
    point = Point(lon, lat)
    match = piedmont_municipalities[piedmont_municipalities.contains(point)]
    if not match.empty:
        municipality = match.iloc[0]['COMUNE']
        if isinstance(municipality, bytes):
            municipality = municipality.decode('utf-8', errors='ignore')
        else:
            municipality = str(municipality).encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
            
        cod_prov = int(match.iloc[0]['COD_PROV'])
        province = PIEDMONT_PROVINCES.get(cod_prov, "TO")
        return municipality, province
    return "Non specificato", "Non specificato"

class MongoEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)


def generate_reviews(mongo_id, collection_name):
    n = random.randint(0, 5)
    if n == 0:
        return [], [], []

    texts = REVIEW_TEXTS.get(collection_name, REVIEW_TEXTS["attractions"])
    all_reviews = []

    for _ in range(n):
        days_ago = random.randint(1, 365)
        created_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        review = {
            "username": random.choice(REVIEW_USERNAMES),
            "rating": random.choices([1, 2, 3, 4, 5], weights=[5, 10, 20, 40, 25])[0],
            "text": random.choice(texts),
            "created_at": created_at,
        }
        all_reviews.append(review)

    all_reviews.sort(key=lambda r: r["created_at"], reverse=True)

    last_reviews = all_reviews[:3]

    reviews_collection_docs = [
        {**r, "site_id": mongo_id, "collection": collection_name}
        for r in all_reviews
    ]

    extended_refs = [
        {"_id": None, "rating": r["rating"]}  
        for r in all_reviews
    ]

    return last_reviews, reviews_collection_docs, extended_refs