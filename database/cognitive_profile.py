from database.mongodb import get_db
from database.common import get_user_id_by_email
import json
from datetime import datetime
from bson.objectid import ObjectId

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

def create_cognitive_profile(user_id_or_email):
    """
    Crea un perfil cognitivo vacío para un estudiante
    Args:
        user_id_or_email: Puede ser el ObjectId del usuario o su email
    """
    db = get_db()
    cognitive_profiles_collection = db.cognitive_profiles
    users_collection = db.users

    try:
        # Determinar si el input es un email o un ID
        if isinstance(user_id_or_email, str) and '@' in user_id_or_email:
            user = users_collection.find_one({"email": user_id_or_email})
            if not user:
                print(f"Usuario no encontrado para el email: {user_id_or_email}")
                return False
            user_id = user["_id"]
        else:
            # Asumimos que es un ID
            user_id = user_id_or_email if isinstance(user_id_or_email, ObjectId) else ObjectId(user_id_or_email)
            user = users_collection.find_one({"_id": user_id})
            if not user:
                print(f"Usuario no encontrado para el ID: {user_id}")
                return False

        # Verificar si ya existe un perfil
        existing_profile = cognitive_profiles_collection.find_one({"user_id": user_id})
        if existing_profile:
            print(f"Ya existe un perfil cognitivo para el usuario: {user_id}")
            return True

        # Crear perfil vacío
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

        print(f"Creando perfil cognitivo para usuario: {user['name']} ({user_id})")  # Debug log

        # Convertir a string JSON
        profile_json_string = json.dumps(empty_profile)

        new_profile = {
            "user_id": user_id, 
            "profile": profile_json_string,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        result = cognitive_profiles_collection.insert_one(new_profile)
        success = bool(result.inserted_id)
        
        if success:
            print(f"Perfil cognitivo creado exitosamente para: {user['name']}")
        else:
            print("Error: No se pudo crear el perfil cognitivo")
            
        return success

    except Exception as e:
        print(f"Error al crear el perfil cognitivo: {str(e)}")
        return False
