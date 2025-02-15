from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def create_study_plan(name, description, created_by, is_template=False, document_url=None):
    db = get_db()
    study_plan = {
        "name": name,
        "description": description,
        "created_by": created_by,
        "is_template": is_template,
        "status": "active",
        "document_url": document_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.study_plans.insert_one(study_plan)
    return result.inserted_id

def assign_study_plan(study_plan_id, classroom_id):
    db = get_db()
    assignment = {
        "study_plan_id": ObjectId(study_plan_id),
        "classroom_id": ObjectId(classroom_id),
        "assigned_at": datetime.utcnow(),
        "status": "active"
    }
    result = db.study_plan_assignments.insert_one(assignment)
    return result.inserted_id

def get_study_plan(study_plan_id):
    db = get_db()
    return db.study_plans.find_one({"_id": ObjectId(study_plan_id)})

def get_study_plan_assignments(study_plan_id=None, classroom_id=None):
    db = get_db()
    query = {}
    if study_plan_id:
        query["study_plan_id"] = ObjectId(study_plan_id)
    if classroom_id:
        query["classroom_id"] = ObjectId(classroom_id)
    return list(db.study_plan_assignments.find(query))

def update_study_plan(study_plan_id, updates):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.study_plans.update_one(
        {"_id": ObjectId(study_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_study_plan_assignment(assignment_id, updates):
    db = get_db()
    result = db.study_plan_assignments.update_one(
        {"_id": ObjectId(assignment_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def delete_study_plan(study_plan_id):
    db = get_db()
    # Actualizar estado en lugar de eliminar
    result = db.study_plans.update_one(
        {"_id": ObjectId(study_plan_id)},
        {"$set": {"status": "archived"}}
    )
    return result.modified_count > 0

def remove_study_plan_assignment(assignment_id):
    db = get_db()
    result = db.study_plan_assignments.update_one(
        {"_id": ObjectId(assignment_id)},
        {"$set": {"status": "cancelled"}}
    )
    return result.modified_count > 0 