import argparse
import os
import bcrypt
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

def get_db():
    load_dotenv()
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
    client = MongoClient(uri)
    return client[os.getenv("MONGO_DB_NAME", "Tourism")]

def add_manager(name, username, password, email):
    db = get_db()
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

def remove_manager(username):
    db = get_db()
    users = db["users"]
    
    result = users.delete_one({"username": username, "role": "manager"})
    
    if result.deleted_count > 0:
        print(f"Success: Manager '{username}' removed correctly.")
    else:
        print(f"Error: Manager '{username}' not found.")

def main():
    parser = argparse.ArgumentParser(description="Add or remove a manger account")
    subparsers = parser.add_subparsers(dest="action", required=True, help="Action to perform (add / remove)")
    

    add_parser = subparsers.add_parser("add", help="add a manager account ")
    add_parser.add_argument("--name", required=True, help="add manager's name")
    add_parser.add_argument("--username", required=True, help="add manager's surname")
    add_parser.add_argument("--password", required=True, help="add manager's password")
    add_parser.add_argument("--email", default="", help="add manager's email")
    

    remove_parser = subparsers.add_parser("remove", help="delete an existing manager account ")
    remove_parser.add_argument("--username", required=True, help="delete by manager's username")
    
    args = parser.parse_args()
    
    if args.action == "add":
        add_manager(args.name, args.username, args.password, args.email)
    elif args.action == "remove":
        remove_manager(args.username)

if __name__ == "__main__":
    main()
