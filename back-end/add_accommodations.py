import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DEFAULT_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "accommodations")

COLLECTION_NAME = "accommodations"
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


def assign_ids(documents: list[dict], collection) -> list[dict]:
    # ALL_NNNN has zero-padding so lexicographic sort is safe, but using max() is more robust
    existing = collection.find(
        {"_id": {"$regex": r"^ALL_\d+$"}},
        {"_id": 1}
    )
    counter = 1
    try:
        nums = [int(doc["_id"].split("_")[1]) for doc in existing]
        if nums:
            counter = max(nums) + 1
    except (IndexError, ValueError):
        pass

    for doc in documents:
        if "_id" not in doc:
            doc["_id"] = f"ALL_{counter:04d}"
            counter += 1

    return documents


def main(args):
    full_path = os.path.join(args.path, args.file)

    mongo_client = MongoClient(args.mongo_uri)
    db = mongo_client[args.mongo_db]
    collection = db[COLLECTION_NAME]

    existing_indexes = [idx["name"] for idx in collection.list_indexes()]
    if f"{POSITION_FIELD}_2dsphere" not in existing_indexes:
        print(f"Creating geospatial index on '{POSITION_FIELD}'...")
        collection.create_index([(POSITION_FIELD, "2dsphere")])

    documents = load_json_file(full_path)
    print(f"Documents found: {len(documents)}")

    documents = assign_ids(documents, collection)

    collection.insert_many(documents)
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    print(f"Saving JSON backup to {args.output_json}...")
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=4, ensure_ascii=False)
    print(f"Completed. Stored {len(documents)} accommodations.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description=(
            "Add accommodations to MongoDB by reading a specific JSON file.\n\n"
            "Example:\n"
            "  python add_accommodations.py --file new_accommodations.json\n"
            "  python add_accommodations.py --file new_accommodations.json --path /other/path\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Name of the JSON file to load (e.g., new_accommodations.json).",
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
        default=os.path.join(script_dir, "data", "accommodations_added.json"),
        help="Path where the JSON backup file will be saved.",
    )

    args = parser.parse_args()
    os.makedirs(args.path, exist_ok=True)
    main(args)
