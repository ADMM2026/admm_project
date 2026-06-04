import argparse
import os
import bcrypt
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def get_db(uri, db_name):
    client = MongoClient(uri)
    return client[db_name]

def add_manager(uri, db_name, name, username, password, email):
    db = get_db(uri, db_name)
    users = db["users"]
    
    if users.find_one({"username": username}):
        print(f"Error : Username '{username}' is already in use.")
        return
    
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    
    user_doc = {
        "name": name,
        "username": username,
        "password_hash": pw_hash,
        "role": "manager",
        "email": email,
        "created_at": datetime.now(timezone.utc),
    }
    
    users.insert_one(user_doc)
    print(f"Success: Manager '{username}' added correctly.")

def remove_manager(uri, db_name, username):
    db = get_db(uri, db_name)
    users = db["users"]
    
    result = users.delete_one({"username": username, "role": "manager"})
    
    if result.deleted_count > 0:
        print(f"Success: Manager '{username}' removed correctly.")
    else:
        print(f"Error: Manager '{username}' not found.")

def main():
    parser = argparse.ArgumentParser(description="Add or remove a manager account")
    parser.add_argument("--mongo-uri", type=str, 
                        default=os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"), 
                        help="MongoDB connection URI.")
    parser.add_argument("--mongo-db", type=str,
                        default=os.getenv("MONGO_DB_NAME", "Tourism"),
                        help="MongoDB database name.")
    parser.add_argument("--action", type=str, choices=["add", "remove"], required=True, 
                        help="Action to perform (add / remove)")
    parser.add_argument("--name", type=str, 
                        help="Manager's name -> required for 'add'")
    parser.add_argument("--username", type=str, required=True, 
                        help="Manager's username")
    parser.add_argument("--password", type=str, 
                        help="Manager's password -> required for 'add'")
    parser.add_argument("--email", type=str, default="", 
                        help="Manager's email")
    
    args = parser.parse_args()
    
    if args.action == "add":
        if not args.name or not args.password:
            parser.error("--name and --password are required for the 'add' action")
        add_manager(args.mongo_uri, args.mongo_db, args.name, args.username, args.password, args.email)
    elif args.action == "remove":
        remove_manager(args.mongo_uri, args.mongo_db, args.username)

if __name__ == "__main__":
    main()
