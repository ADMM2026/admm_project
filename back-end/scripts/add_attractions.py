import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DEFAULT_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "attractions")

COLLECTION_NAME = "attractions"
POSITION_FIELD = "position"


def load_json_file(file_path: str) -> list[dict]:
    p = Path(file_path)

    if not p.exists():
        print(f"[ERROR] File not found: '{file_path}'")
        sys.exit(1)

    if not p.is_file() or p.suffix.lower() != ".json":
        print(f"[ERROR] '{file_path}' is not a valid .json file.")
        sys.exit(1)

    print(f"Reading: {p}")
    with open(p, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return [data]
    else:
        print(f"[ERROR] Unrecognized JSON structure in '{p.name}'.")
        sys.exit(1)


def main(args):
    full_path = os.path.join(args.path, args.file)
    documents = load_json_file(full_path)
    if not documents:
        print("[WARNING] No documents found in the JSON file. Exiting.")
        sys.exit(0)
    print(f"Documents found: {len(documents)}")
    for doc in documents:
        if "position" in doc and isinstance(doc["position"], dict):
            if "type" not in doc["position"]:
                doc["position"]["type"] = "Point"
    mongo_client = MongoClient(args.mongo_uri)
    db = mongo_client[args.mongo_db]
    collection = db[COLLECTION_NAME]
    print(f"Inserting {len(documents)} documents into '{COLLECTION_NAME}'...")
    result = collection.insert_many(documents)
    print(f"[SUCCESS] Successfully inserted {len(result.inserted_ids)} attractions.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description=(
            "Add attractions to MongoDB by reading a specific JSON file.\n\n"
            "Example:\n"
            "  python add_attractions.py --file new_attractions.json\n"
            "  python add_attractions.py --file new_attractions.json --path /other/path\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Name of the JSON file to load (e.g. new_attractions.json).",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=DEFAULT_UPLOAD_DIR,
        help=f"Base directory where to search for the file. Default: {DEFAULT_UPLOAD_DIR}",
    )
    parser.add_argument(
        "--mongo-uri",
        type=str,
        default=os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"),
        help="MongoDB connection URI.",
    )
    parser.add_argument(
        "--mongo-db",
        type=str,
        default=os.getenv("MONGO_DB_NAME", "Tourism"),
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=os.path.join(script_dir, "data", "attractions_added.json"),
        help="Path where the JSON backup file will be saved.",
    )

    args = parser.parse_args()
    os.makedirs(args.path, exist_ok=True)
    main(args)
