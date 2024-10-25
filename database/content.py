from database.mongodb import get_db
from bson import ObjectId
from datetime import datetime

def create_content(classroom_id, student_id, content_text):
    """
    Crea un nuevo contenido para una clase.

    Args:
        classroom_id (str): ID de la clase.
        student_id (str): ID del estudiante.
        content_text (str): Contenido en formato texto.

    Returns:
        str: ID del contenido creado si es exitoso, None en caso contrario.
    """
    db = get_db()
    content_collection = db.content

    new_content = {
        "classroom_id": ObjectId(classroom_id),
        "student_id": ObjectId(student_id),
        "content": content_text,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

    try:
        result = content_collection.insert_one(new_content)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error al crear el contenido: {str(e)}")
        return None

def update_content(content_id, content_text):
    """
    Actualiza un contenido existente.

    Args:
        content_id (str): ID del contenido a actualizar.
        content_text (str): Nuevo contenido en formato texto.

    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario.
    """
    db = get_db()
    content_collection = db.content

    try:
        result = content_collection.update_one(
            {"_id": ObjectId(content_id)},
            {
                "$set": {
                    "content": content_text,
                    "updated_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error al actualizar el contenido: {str(e)}")
        return False

def get_content(content_id):
    """
    Obtiene un contenido específico por su ID.

    Args:
        content_id (str): ID del contenido a obtener.

    Returns:
        dict: Datos del contenido si se encuentra, None en caso contrario.
    """
    db = get_db()
    content_collection = db.content

    try:
        content = content_collection.find_one({"_id": ObjectId(content_id)})
        if content:
            content["_id"] = str(content["_id"])
            content["classroom_id"] = str(content["classroom_id"])
            content["student_id"] = str(content["student_id"])
        return content
    except Exception as e:
        print(f"Error al obtener el contenido: {str(e)}")
        return None

def get_student_content(student_id, classroom_id):
    """
    Obtiene todo el contenido de un estudiante en una clase específica.

    Args:
        student_id (str): ID del estudiante.
        classroom_id (str): ID de la clase.

    Returns:
        list: Lista de contenidos del estudiante en la clase.
    """
    db = get_db()
    content_collection = db.content

    try:
        contents = content_collection.find({
            "student_id": ObjectId(student_id),
            "classroom_id": ObjectId(classroom_id)
        }).sort("created_at", -1)  # Ordenar por fecha de creación, más reciente primero
        
        return [{
            "_id": str(content["_id"]),
            "classroom_id": str(content["classroom_id"]),
            "student_id": str(content["student_id"]),
            "content": content["content"],
            "created_at": content["created_at"],
            "updated_at": content["updated_at"]
        } for content in contents]
    except Exception as e:
        print(f"Error al obtener el contenido del estudiante: {str(e)}")
        return []

def delete_content(content_id):
    """
    Elimina un contenido existente.

    Args:
        content_id (str): ID del contenido a eliminar.

    Returns:
        bool: True si la eliminación fue exitosa, False en caso contrario.
    """
    db = get_db()
    content_collection = db.content

    try:
        result = content_collection.delete_one({"_id": ObjectId(content_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error al eliminar el contenido: {str(e)}")
        return False
