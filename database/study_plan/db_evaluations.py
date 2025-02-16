from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def get_module_evaluations(module_id):
    """Obtiene todas las actividades de evaluación de un módulo"""
    db = get_db()
    module = db.modules.find_one({"_id": ObjectId(module_id)})
    return module.get("evaluation_activities", []) if module else []

def get_student_evaluations(student_id, module_id=None):
    """Obtiene las evaluaciones de un estudiante"""
    db = get_db()
    query = {"student_id": ObjectId(student_id)}
    if module_id:
        query["module_id"] = ObjectId(module_id)
    return list(db.student_evaluations.find(query))

def record_student_evaluation(module_id, activity_id, student_id, score, feedback):
    """Registra la evaluación de un estudiante"""
    db = get_db()
    evaluation = {
        "module_id": ObjectId(module_id),
        "activity_id": activity_id,
        "student_id": ObjectId(student_id),
        "score": score,
        "feedback": feedback,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.student_evaluations.insert_one(evaluation)
    return result.inserted_id

def update_student_evaluation(evaluation_id, updates):
    """Actualiza la evaluación de un estudiante"""
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.student_evaluations.update_one(
        {"_id": ObjectId(evaluation_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def assign_evaluation_plan(evaluation_plan_id, classroom_id):
    """
    Asigna un plan de evaluación a un aula
    
    Args:
        evaluation_plan_id (str): ID del plan de evaluación
        classroom_id (str): ID del aula
        
    Returns:
        ObjectId: ID de la asignación creada
    """
    db = get_db()
    assignment = {
        "evaluation_plan_id": ObjectId(evaluation_plan_id),
        "classroom_id": ObjectId(classroom_id),
        "assigned_at": datetime.utcnow(),
        "status": "active"
    }
    result = db.evaluation_plan_assignments.insert_one(assignment)
    return result.inserted_id

def create_evaluation(evaluation_plan_id, module_id, topic_ids, name, description, 
                     methodology, weight, date):
    """
    Crea una nueva evaluación dentro de un plan
    
    Args:
        evaluation_plan_id (str): ID del plan de evaluación
        module_id (str): ID del módulo asociado
        topic_ids (list): Lista de IDs de los temas evaluados
        name (str): Nombre de la evaluación
        description (str): Descripción detallada
        methodology (str): Metodología de evaluación
        weight (float): Peso de la evaluación en la nota final
        date (datetime): Fecha programada
        
    Returns:
        ObjectId: ID de la evaluación creada
    """
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
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.evaluations.insert_one(evaluation)
    return result.inserted_id

def get_evaluations(evaluation_plan_id):
    """
    Obtiene todas las evaluaciones de un plan
    
    Args:
        evaluation_plan_id (str): ID del plan de evaluación
        
    Returns:
        list: Lista de evaluaciones asociadas al plan
    """
    db = get_db()
    return list(db.evaluations.find(
        {"evaluation_plan_id": ObjectId(evaluation_plan_id)}
    ))

def update_evaluation(evaluation_id, updates):
    """
    Actualiza una evaluación específica
    
    Args:
        evaluation_id (str): ID de la evaluación
        updates (dict): Campos a actualizar
        
    Returns:
        bool: True si se actualizó correctamente
    """
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.evaluations.update_one(
        {"_id": ObjectId(evaluation_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

def delete_evaluation(evaluation_id):
    """
    Elimina una evaluación específica
    
    Args:
        evaluation_id (str): ID de la evaluación
        
    Returns:
        bool: True si se eliminó correctamente
    """
    db = get_db()
    result = db.evaluations.delete_one({"_id": ObjectId(evaluation_id)})
    return result.deleted_count > 0

def get_evaluation_by_id(evaluation_id):
    """
    Obtiene una evaluación específica por su ID
    
    Args:
        evaluation_id (str): ID de la evaluación
        
    Returns:
        dict: Detalles de la evaluación o None si no existe
    """
    db = get_db()
    return db.evaluations.find_one({"_id": ObjectId(evaluation_id)})

def get_evaluations_by_module(module_id):
    """
    Obtiene todas las evaluaciones asociadas a un módulo
    
    Args:
        module_id (str): ID del módulo
        
    Returns:
        list: Lista de evaluaciones del módulo
    """
    db = get_db()
    return list(db.evaluations.find({"module_id": ObjectId(module_id)}))

def get_evaluations_by_topic(topic_id):
    """
    Obtiene todas las evaluaciones que incluyen un tema específico
    
    Args:
        topic_id (str): ID del tema
        
    Returns:
        list: Lista de evaluaciones que incluyen el tema
    """
    db = get_db()
    return list(db.evaluations.find({"topic_ids": ObjectId(topic_id)}))