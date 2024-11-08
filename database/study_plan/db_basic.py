from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def create_study_plan(classroom_id, name, description, document_url):
    db = get_db()
    study_plan = {
        "classroom_id": ObjectId(classroom_id),
        "name": name,
        "description": description,
        "document_url": document_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.study_plans.insert_one(study_plan)
    return result.inserted_id

def get_study_plan(study_plan_id):
    db = get_db()
    return db.study_plans.find_one({"_id": ObjectId(study_plan_id)})

def update_study_plan(study_plan_id, updates):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.study_plans.update_one(
        {"_id": ObjectId(study_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def delete_study_plan(study_plan_id):
    db = get_db()
    result = db.study_plans.delete_one({"_id": ObjectId(study_plan_id)})
    return result.deleted_count > 0 