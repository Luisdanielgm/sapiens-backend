#!/usr/bin/env python3
"""Rellena nombre y descripción en VirtualTopic existentes."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from bson import ObjectId
from src.shared.database import get_db

def main():
    db = get_db()
    topics = list(db.virtual_topics.find({"$or": [{"name": {"$exists": False}}, {"description": {"$exists": False}}]}))
    for vt in topics:
        original = db.topics.find_one({"_id": vt["topic_id"]})
        if not original:
            continue
        update = {}
        if "name" not in vt:
            update["name"] = original.get("name")
        if "description" not in vt:
            update["description"] = original.get("theory_content", "")
        if update:
            update["updated_at"] = datetime.now()
            db.virtual_topics.update_one({"_id": vt["_id"]}, {"$set": update})
    print(f"Actualizados {len(topics)} documentos")

if __name__ == "__main__":
    main()
