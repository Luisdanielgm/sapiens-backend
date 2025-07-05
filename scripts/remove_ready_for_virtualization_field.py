#!/usr/bin/env python3
"""Elimina el campo ready_for_virtualization en todos los módulos."""
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def main():
    load_dotenv()
    uri = os.getenv("MONGO_DB_URI")
    db_name = os.getenv("DB_NAME")
    if not uri or not db_name:
        print("Faltan variables de entorno MONGO_DB_URI y DB_NAME")
        return
    client = MongoClient(uri)
    db = client[db_name]
    result = db.modules.update_many({}, {"$unset": {"ready_for_virtualization": 1}})
    print(f"Se eliminaron {result.modified_count} campos")


if __name__ == "__main__":
    main()
