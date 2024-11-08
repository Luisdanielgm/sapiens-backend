from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def create_module(study_plan_id, name, start_date, end_date, objectives):
    db = get_db()
    module = {
        "study_plan_id": ObjectId(study_plan_id),
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "objectives": objectives,
        "created_at": datetime.utcnow()
    }
    result = db.modules.insert_one(module)
    return result.inserted_id

def get_modules(study_plan_id):
    db = get_db()
    return list(db.modules.find({"study_plan_id": ObjectId(study_plan_id)}))

def update_module(module_id, updates):
    db = get_db()
    result = db.modules.update_one(
        {"_id": ObjectId(module_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def delete_module(module_id):
    db = get_db()
    # Primero eliminar todos los temas asociados
    db.topics.delete_many({"module_id": ObjectId(module_id)})
    # Luego eliminar el módulo
    result = db.modules.delete_one({"_id": ObjectId(module_id)})
    return result.deleted_count > 0 