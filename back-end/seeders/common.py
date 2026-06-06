from shapely.geometry import Point
from bson import ObjectId
import json

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