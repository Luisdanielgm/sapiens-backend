from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db

def create_evaluation_plan(name, description, created_by, is_template=False, document_url=None):
    """
    Crea un nuevo plan de evaluación
    
    Args:
        name (str): Nombre del plan
        description (str): Descripción del plan
        created_by (str): Email del profesor que crea el plan
        is_template (bool): Indica si es una plantilla reutilizable
        document_url (str, optional): URL del documento original
        
    Returns:
        ObjectId: ID del plan de evaluación creado
    """
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

def get_evaluation_plan(evaluation_plan_id):
    """
    Obtiene los detalles de un plan de evaluación
    
    Args:
        evaluation_plan_id (str): ID del plan de evaluación
        
    Returns:
        dict: Detalles del plan de evaluación o None si no existe
    """
    db = get_db()
    return db.evaluation_plans.find_one({"_id": ObjectId(evaluation_plan_id)})

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

def update_evaluation_plan(evaluation_plan_id, updates):
    """
    Actualiza un plan de evaluación
    
    Args:
        evaluation_plan_id (str): ID del plan de evaluación
        updates (dict): Campos a actualizar
        
    Returns:
        bool: True si se actualizó correctamente
    """
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    result = db.evaluation_plans.update_one(
        {"_id": ObjectId(evaluation_plan_id)},
        {"$set": updates}
    )
    return result.modified_count > 0

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

def delete_evaluation_plan(evaluation_plan_id):
    """
    Elimina un plan de evaluación y todas sus evaluaciones asociadas
    
    Args:
        evaluation_plan_id (str): ID del plan de evaluación
        
    Returns:
        bool: True si se eliminó correctamente
    """
    db = get_db()
    # Primero eliminar todas las evaluaciones asociadas
    db.evaluations.delete_many({"evaluation_plan_id": ObjectId(evaluation_plan_id)})
    # Luego eliminar el plan de evaluación
    result = db.evaluation_plans.delete_one({"_id": ObjectId(evaluation_plan_id)})
    return result.deleted_count > 0

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