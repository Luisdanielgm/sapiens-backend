from database.mongodb import get_db
from database.common import get_user_id_by_email
import json
from datetime import datetime

def get_cognitive_profile(email):
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)
    if not user_id:
        return None

    profile_doc = cognitive_profiles_collection.find_one({"user_id": user_id})
    if not profile_doc or not profile_doc.get("profile"):
        return None

    try:
        # Convertir el string JSON a diccionario
        profile_json = json.loads(profile_doc["profile"])
        return profile_json
    except json.JSONDecodeError as e:
        print(f"Error al decodificar el perfil JSON: {str(e)}")
        return None

def update_cognitive_profile(email, profile_json_string):
    """
    Actualiza el perfil cognitivo de un usuario.
    El perfil debe proporcionarse como un string JSON.
    
    Args:
        email (str): El email del usuario.
        profile_json_string (str): El perfil cognitivo como string JSON.
    
    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario.
    """
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles

    user_id = get_user_id_by_email(email)
    if not user_id:
        return False

    try:
        # Verificar que el string sea un JSON válido
        json.loads(profile_json_string)
        
        # Actualizar el documento con el string JSON
        result = cognitive_profiles_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "profile": profile_json_string,
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )
        return True
    except json.JSONDecodeError as e:
        print(f"Error: El string proporcionado no es un JSON válido: {str(e)}")
        return False
    except Exception as e:
        print(f"Error al actualizar el perfil: {str(e)}")
        return False

def create_cognitive_profile(email):
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles
    users_collection = db.users

    user_id = get_user_id_by_email(email)
    if not user_id:
        return False

    user = users_collection.find_one({"_id": user_id})
    if not user:
        return False

    empty_profile = {
        "id": str(user_id),
        "name": user["name"],
        "learningStyle": {
            "visual": 0,
            "kinesthetic": 0,
            "auditory": 0,
            "readingWriting": 0
        },
        "diagnosis": "",
        "cognitiveStrengths": [],
        "cognitiveDifficulties": [],
        "personalContext": "",
        "recommendedStrategies": []
    }

    # Convertir a string JSON
    profile_json_string = json.dumps(empty_profile)

    new_profile = {
        "user_id": user_id, 
        "profile": profile_json_string,
        "updated_at": datetime.now()
    }

    try:
        result = cognitive_profiles_collection.insert_one(new_profile)
        return bool(result.inserted_id)
    except Exception as e:
        print(f"Error al crear el perfil cognitivo: {str(e)}")
        return False
