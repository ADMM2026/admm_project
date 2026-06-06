from services.api_client import get


def search_attractions(
    text: str,
    provinces: list[str],
    categories: list[str],
    limit: int = 100,
) -> tuple[list[dict], int]:
    params: dict = {"text": text, "limit": limit}
    for p in provinces:
        params.setdefault("provinces", []).append(p)  
    for c in categories:
        params.setdefault("categories", []).append(c) 

    data = get("/search/attractions", params=params)
    return data.get("hits", []), data.get("total", 0)


def search_accommodations(
    text: str,
    provinces: list[str],
    structure_types: list[str],
    stars_range: tuple[int, int] | None,
    limit: int = 100,
) -> tuple[list[dict], int]:
    params: dict = {"text": text, "limit": limit}
    for p in provinces:
        params.setdefault("provinces", []).append(p)  
    for s in structure_types:
        params.setdefault("structure_types", []).append(s)  
    if stars_range:
        params["stars_min"] = stars_range[0]
        params["stars_max"] = stars_range[1]

    data = get("/search/accommodations", params=params)
    return data.get("hits", []), data.get("total", 0)


def count_index(index: str) -> int:
    try:
        return get("/search/count", params={"index": index}).get("count", 0)
    except Exception:
        return 0
