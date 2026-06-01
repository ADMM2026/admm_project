from shapely.geometry import Point


PIEDMONT_PROVINCES = {
    201: "TO",  # Torino
    2: "VC",  # Vercelli
    3: "NO",  # Novara
    4: "CN",  # Cuneo
    5: "AT",  # Asti
    6: "AL",  # Alessandria
    96: "BI",  # Biella
    103: "VB"  # Verbano-Cusio-Ossola
}


def locate_municipality(lon, lat, piedmont_municipalities):
    point = Point(lon, lat)
    match = match = piedmont_municipalities[piedmont_municipalities.contains(point)]
    if not match.empty:
        municipality = match.iloc[0]['COMUNE']
        municipality = municipality.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
        cod_prov = int(match.iloc[0]['COD_PROV'])
        province = PIEDMONT_PROVINCES.get(cod_prov, "Piemonte")
        return municipality, province
    return "Non specificato", "Piemonte"