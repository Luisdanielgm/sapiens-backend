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

def create_evaluation_plan(classroom_ids, document_url):
    db = get_db()
    evaluation_plan = {
        "classroom_ids": [ObjectId(id) for id in classroom_ids],
        "document_url": document_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.evaluation_plans.insert_one(evaluation_plan)
    return result.inserted_id

def create_evaluation(evaluation_plan_id, module_id, topic_ids, name, description, methodology, weight, date):
    db = get_db()
    evaluation = {
        "evaluation_plan_id": ObjectId(evaluation_plan_id),
        "module_id": ObjectId(module_id),
        "topic_ids": [ObjectId(id) for id in topic_ids],
        "name": name,
        "description": description,
        "methodology": methodology,
        "weight": weight,
        "date": date,
        "created_at": datetime.utcnow()
    }
    result = db.evaluations.insert_one(evaluation)
    return result.inserted_id

# Funciones GET
def get_study_plan(study_plan_id):
    db = get_db()
    return db.study_plans.find_one({"_id": ObjectId(study_plan_id)})

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
    result = db.study_plans.delete_one({"_id": ObjectId(study_plan_id)})
    return result.deleted_count > 0

def delete_module(module_id):
    db = get_db()
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