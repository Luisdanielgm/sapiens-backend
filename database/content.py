from database.mongodb import get_db
from bson import ObjectId
from datetime import datetime

def create_content(classroom_id, title, description, content_type, file_url=None, created_by=None):
    """
    Crea un nuevo contenido para una clase.

    Args:
        classroom_id (str): ID de la clase.
        title (str): Título del contenido.
        description (str): Descripción del contenido.
        content_type (str): Tipo de contenido (ej. 'video', 'documento', 'tarea').
        file_url (str, opcional): URL del archivo si es aplicable.
        created_by (str, opcional): ID del usuario que crea el contenido.

    Returns:
        str: ID del contenido creado si es exitoso, None en caso contrario.
    """
    db = get_db()
    content_collection = db.content

    new_content = {
        "classroom_id": ObjectId(classroom_id),
        "title": title,
        "description": description,
        "content_type": content_type,
        "file_url": file_url,
        "created_by": ObjectId(created_by) if created_by else None,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

    try:
        result = content_collection.insert_one(new_content)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error al crear el contenido: {str(e)}")
        return None

def update_content(content_id, title=None, description=None, content_type=None, file_url=None):
    """
    Actualiza un contenido existente.

    Args:
        content_id (str): ID del contenido a actualizar.
        title (str, opcional): Nuevo título del contenido.
        description (str, opcional): Nueva descripción del contenido.
        content_type (str, opcional): Nuevo tipo de contenido.
        file_url (str, opcional): Nueva URL del archivo.

    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario.
    """
    db = get_db()
    content_collection = db.content

    update_data = {}
    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description
    if content_type is not None:
        update_data["content_type"] = content_type
    if file_url is not None:
        update_data["file_url"] = file_url
    
    update_data["updated_at"] = datetime.now()

    try:
        result = content_collection.update_one(
            {"_id": ObjectId(content_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error al actualizar el contenido: {str(e)}")
        return False

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
            if content["created_by"]:
                content["created_by"] = str(content["created_by"])
        return content
    except Exception as e:
        print(f"Error al obtener el contenido: {str(e)}")
        return None

def get_classroom_content(classroom_id):
    """
    Obtiene todo el contenido de una clase específica.

    Args:
        classroom_id (str): ID de la clase.

    Returns:
        list: Lista de contenidos de la clase.
    """
    db = get_db()
    content_collection = db.content

    try:
        contents = content_collection.find({"classroom_id": ObjectId(classroom_id)})
        return [{**content, "_id": str(content["_id"]), "classroom_id": str(content["classroom_id"]), "created_by": str(content["created_by"]) if content["created_by"] else None} for content in contents]
    except Exception as e:
        print(f"Error al obtener el contenido de la clase: {str(e)}")
        return []
