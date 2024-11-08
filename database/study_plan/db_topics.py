from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def create_topic(module_id, name, description, date_range, class_schedule):
    db = get_db()
    topic = {
        "module_id": ObjectId(module_id),
        "name": name,
        "description": description,
        "date_range": date_range,
        "class_schedule": class_schedule,
        "created_at": datetime.utcnow()
    }
    result = db.topics.insert_one(topic)
    return result.inserted_id

def get_topics(module_id):
    db = get_db()
    return list(db.topics.find({"module_id": ObjectId(module_id)}))

def update_topic(topic_id, updates):
    db = get_db()
    result = db.topics.update_one(
        {"_id": ObjectId(topic_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def delete_topic(topic_id):
    db = get_db()
    result = db.topics.delete_one({"_id": ObjectId(topic_id)})
    return result.deleted_count > 0 