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

def create_evaluation_plan(name, description, created_by, is_template=False, document_url=None):
    db = get_db()
    evaluation_plan = {
        "name": name,
        "description": description,
        "created_by": created_by,
        "is_template": is_template,
        "status": "active",
        "document_url": document_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.evaluation_plans.insert_one(evaluation_plan)
    return result.inserted_id

def assign_evaluation_plan(evaluation_plan_id, classroom_id):
    db = get_db()
    assignment = {
        "evaluation_plan_id": ObjectId(evaluation_plan_id),
        "classroom_id": ObjectId(classroom_id),
        "assigned_at": datetime.utcnow(),
        "status": "active"
    }
    result = db.evaluation_plan_assignments.insert_one(assignment)
    return result.inserted_id

# Funciones GET
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

def get_modules(study_plan_id):
    db = get_db()
    return list(db.modules.find({"study_plan_id": ObjectId(study_plan_id)}))

def get_topics(module_id):
    db = get_db()
    return list(db.topics.find({"module_id": ObjectId(module_id)}))

def get_evaluation_plan(evaluation_plan_id):
    db = get_db()
    return db.evaluation_plans.find_one({"_id": ObjectId(evaluation_plan_id)})

def get_evaluations(evaluation_plan_id):
    db = get_db()
    return list(db.evaluations.find({"evaluation_plan_id": ObjectId(evaluation_plan_id)}))

# Funciones UPDATE
def update_study_plan(study_plan_id, updates):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.study_plans.update_one(
        {"_id": ObjectId(study_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_module(module_id, updates):
    db = get_db()
    result = db.modules.update_one(
        {"_id": ObjectId(module_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_topic(topic_id, updates):
    db = get_db()
    result = db.topics.update_one(
        {"_id": ObjectId(topic_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_evaluation_plan(evaluation_plan_id, updates):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.evaluation_plans.update_one(
        {"_id": ObjectId(evaluation_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def update_evaluation(evaluation_id, updates):
    db = get_db()
    result = db.evaluations.update_one(
        {"_id": ObjectId(evaluation_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

# Funciones DELETE
def delete_study_plan(study_plan_id):
    db = get_db()
    # Actualizar estado en lugar de eliminar
    result = db.study_plans.update_one(
        {"_id": ObjectId(study_plan_id)},
        {"$set": {"status": "archived"}}
    )
    return result.modified_count > 0

def delete_module(module_id):
    db = get_db()
    # Primero eliminar todos los temas asociados
    db.topics.delete_many({"module_id": ObjectId(module_id)})
    # Luego eliminar el módulo
    result = db.modules.delete_one({"_id": ObjectId(module_id)})
    return result.deleted_count > 0

def delete_topic(topic_id):
    db = get_db()
    result = db.topics.delete_one({"_id": ObjectId(topic_id)})
    return result.deleted_count > 0

def delete_evaluation_plan(evaluation_plan_id):
    db = get_db()
    result = db.evaluation_plans.delete_one({"_id": ObjectId(evaluation_plan_id)})
    return result.deleted_count > 0

def delete_evaluation(evaluation_id):
    db = get_db()
    result = db.evaluations.delete_one({"_id": ObjectId(evaluation_id)})
    return result.deleted_count > 0