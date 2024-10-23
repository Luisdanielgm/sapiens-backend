from database.mongodb import get_db
from datetime import datetime
from bson import ObjectId
from database.db_user import get_user_id_by_email

def get_cognitive_profile(email):
    """
    Obtiene el perfil cognitivo de un usuario por su email.
    
    Args:
        email (str): El email del usuario.
    
    Returns:
        dict: El perfil cognitivo del usuario o None si no se encuentra.
    """
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)
    if not user_id:
        return None

    profile = cognitive_profiles_collection.find_one({"user_id": user_id})
    return profile

def update_cognitive_profile(email, profile):
    """
    Actualiza el perfil cognitivo de un usuario.
    
    Args:
        email (str): El email del usuario.
        profile (dict): Los datos actualizados del perfil.
    
    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario.
    """
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)
    if not user_id:
        return False

    try:
        result = cognitive_profiles_collection.update_one(
            {"user_id": user_id},
            {"$set": profile}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error al actualizar el perfil cognitivo: {str(e)}")
        return False

def create_cognitive_profile(email, profile, status):
    """
    Crea un nuevo perfil cognitivo para un usuario.
    
    Args:
        email (str): El email del usuario.
        profile (str): El perfil cognitivo.
        status (str): El estado del perfil.
    
    Returns:
        bool: True si la creación fue exitosa, False en caso contrario.
    """
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)
    if not user_id:
        return False

    new_profile = {
        "user_id": user_id, 
        "status": status,
        "profile": profile,
        "date": datetime.now()
    }

    try:
        result = cognitive_profiles_collection.insert_one(new_profile)
        return bool(result.inserted_id)
    except Exception as e:
        print(f"Error al crear el perfil cognitivo: {str(e)}")
        return False