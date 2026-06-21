import argparse
import os
from datetime import datetime, timezone
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def seed_manager(mongo_uri: str, mongo_db: str) -> None:
    """Creates the default 'admin' manager account if it does not already exist."""
    client = MongoClient(mongo_uri)
    db = client[mongo_db]

    if db["users"].find_one({"username": "admin"}) is not None:
        print("[SKIP] Manager account 'admin' already exists.")
        return

    pw_hash = bcrypt.hashpw("admin".encode("utf-8"), bcrypt.gensalt())
    db["users"].insert_one({
        "username": "admin",
        "password_hash": pw_hash,
        "role": "manager",
        "email": "",
        "created_at": datetime.now(timezone.utc),
    })
    print("[SUCCESS] Manager account 'admin' created successfully.")


def main(args) -> None:
    seed_manager(mongo_uri=args.mongo_uri, mongo_db=args.mongo_db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed MongoDB with the default manager account."
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

    args = parser.parse_args()
    main(args)
