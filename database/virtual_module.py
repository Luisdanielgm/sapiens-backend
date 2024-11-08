from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def create_virtual_module(module_id, name, description, created_by, content):
    db = get_db()
    virtual_module = {
        "module_id": ObjectId(module_id),
        "name": name,
        "description": description,
        "created_by": ObjectId(created_by),
        "content": content,
        "created_at": datetime.utcnow()
    }
    result = db.virtual_modules.insert_one(virtual_module)
    return result.inserted_id

def get_virtual_module(virtual_module_id):
    db = get_db()
    return db.virtual_modules.find_one({"_id": ObjectId(virtual_module_id)})

def get_personalized_module(personalized_module_id):
    db = get_db()
    return db.personalized_modules.find_one({"_id": ObjectId(personalized_module_id)})

def get_student_modules(student_id):
    db = get_db()
    return list(db.personalized_modules.find({"student_id": ObjectId(student_id)}))

def update_personalized_module_progress(module_id, content_index, completed, score=None):
    db = get_db()
    updates = {
        f"adaptive_content.{content_index}.completed": completed,
        "updated_at": datetime.utcnow()
    }
    if score is not None:
        updates[f"adaptive_content.{content_index}.score"] = score
    
    # Actualizar el progreso general
    module = get_personalized_module(module_id)
    total_items = len(module["adaptive_content"])
    completed_items = sum(1 for item in module["adaptive_content"] if item["completed"])
    progress = (completed_items / total_items) * 100
    updates["progress"] = progress
    
    if progress >= 100:
        updates["status"] = "completed"
    
    result = db.personalized_modules.update_one(
        {"_id": ObjectId(module_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def add_module_resource(virtual_module_id, file_url, type, learning_style, description):
    db = get_db()
    resource = {
        "virtual_module_id": ObjectId(virtual_module_id),
        "type": type,
        "learning_style": learning_style,
        "url": file_url,
        "description": description,
        "created_at": datetime.utcnow()
    }
    result = db.module_resources.insert_one(resource)
    return result.inserted_id

def get_module_resources(virtual_module_id, learning_style=None):
    db = get_db()
    query = {"virtual_module_id": ObjectId(virtual_module_id)}
    if learning_style:
        query["learning_style"] = learning_style
    return list(db.module_resources.find(query))

# ... (más funciones de base de datos) 