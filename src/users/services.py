from typing import Tuple, Optional, Dict, List
from bson import ObjectId
from datetime import datetime
import json

from src.shared.database import get_db
from src.shared.standardization import BaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import User, CognitiveProfile

class UserService(BaseService):
    def __init__(self):
        super().__init__(collection_name="users")

    def register_user(self, user_data: dict, institute_name: Optional[str] = None) -> Tuple[bool, str]:
        try:
            # Crear usuario
            user = User(**user_data)
            result = self.collection.insert_one(user.to_dict())
            user_id = result.inserted_id

            # Si es institute_admin, crear instituto
            if user.role == 'INSTITUTE_ADMIN' and institute_name:
                db = get_db()
                institute_result = db.institutes.insert_one({
                    'name': institute_name,
                    'created_at': datetime.now(),
                    'status': 'pending'
                })
                
                # Crear relación instituto-admin
                db.institute_members.insert_one({
                    'institute_id': institute_result.inserted_id,
                    'user_id': user_id,
                    'role': 'INSTITUTE_ADMIN',
                    'joined_at': datetime.now()
                })

            # Crear perfil cognitivo para estudiantes
            if user.role == 'STUDENT':
                db = get_db()
                cognitive_profile = CognitiveProfile(str(user_id))
                db.cognitive_profiles.insert_one(cognitive_profile.to_dict())

            return True, str(user_id)

        except Exception as e:
            # Limpiar datos si algo falla
            if 'user_id' in locals():
                self.collection.delete_one({'_id': user_id})
            return False, str(e)

    def get_user_profile(self, email: str) -> Optional[Dict]:
        try:
            user = self.collection.find_one({"email": email})
            if not user:
                return None

            profile_data = {
                "user_info": user,
                "institutes": [],
                "cognitive_profile": None
            }

            # Obtener institutos asociados
            memberships = self.collection.find({"user_id": user["_id"]})
            for membership in memberships:
                institute = get_db().institutes.find_one({"_id": membership["institute_id"]})
                if institute:
                    profile_data["institutes"].append({
                        "id": str(institute["_id"]),
                        "name": institute["name"],
                        "role": membership["role"]
                    })

            # Obtener perfil cognitivo si es estudiante
            if user["role"] == "STUDENT":
                cognitive_profile = self.collection.find_one({"user_id": user["_id"]})
                if cognitive_profile:
                    profile_data["cognitive_profile"] = cognitive_profile

            return profile_data

        except Exception as e:
            print(f"Error al obtener perfil de usuario: {str(e)}")
            return None

    def verify_user_exists(self, email: str) -> Dict:
        user = self.collection.find_one({"email": email})
        if not user:
            raise AppException(f"Usuario con email {email} no encontrado", ErrorCodes.USER_NOT_FOUND, status_code=404)
        return user

    def search_users_by_email(self, partial_email: str) -> List[str]:
        users = self.collection.find({"email": {"$regex": partial_email, "$options": "i"}}, {"email": 1})
        return [user["email"] for user in users]

    def delete_student(self, email: str) -> Tuple[bool, str]:
        """Elimina un estudiante y todos sus datos asociados"""
        try:
            user = self.collection.find_one({"email": email})
            if not user or user.get("role") != "STUDENT":
                return False, "Usuario no encontrado o no es estudiante"

            user_id = user["_id"]

            # Eliminar datos asociados
            get_db().classroom_members.delete_many({"user_id": user_id})
            get_db().classroom_invitations.delete_many({
                "$or": [
                    {"invitee_id": user_id},
                    {"inviter_id": user_id}
                ]
            })
            get_db().contents.delete_many({"student_id": user_id})
            get_db().cognitive_profiles.delete_one({"user_id": user_id})
            self.collection.delete_one({"_id": user_id})

            return True, "Estudiante eliminado exitosamente"
        except Exception as e:
            return False, str(e)

    def get_user_info(self, email: str) -> Optional[Dict]:
        """Obtiene información básica del usuario"""
        try:
            user = self.collection.find_one({"email": email})
            if user:
                # Convertir ObjectId a string y filtrar campos sensibles
                return {
                    "id": str(user["_id"]),
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"],
                    "picture": user.get("picture"),
                    "status": user.get("status", "active")
                }
            return None
        except Exception as e:
            print(f"Error al obtener información del usuario: {str(e)}")
            return None

    def verify_password(self, plain_password, hashed_password):
        """Verifica si la contraseña en texto plano coincide con el hash almacenado"""
        try:
            import bcrypt
            # Verifica si el hash tiene el formato correcto para bcrypt
            if hashed_password and hashed_password.startswith('$2b$'):
                return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
            return False
        except Exception as e:
            print(f"Error verificando contraseña: {str(e)}")
            return False

class CognitiveProfileService(BaseService):
    def __init__(self):
        super().__init__(collection_name="cognitive_profiles")

    def update_cognitive_profile(self, email: str, profile_data: str) -> bool:
        """Actualiza el perfil cognitivo de un usuario"""
        try:
            user = get_db().users.find_one({"email": email})
            if not user:
                return False

            # Verificar que el string sea un JSON válido
            json.loads(profile_data)

            result = self.collection.update_one(
                {"user_id": user["_id"]},
                {
                    "$set": {
                        "profile": profile_data,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error al actualizar perfil cognitivo: {str(e)}")
            return False

    def get_cognitive_profile(self, email: str) -> Optional[Dict]:
        """Obtiene el perfil cognitivo de un usuario"""
        try:
            user = get_db().users.find_one({"email": email})
            if not user:
                return None

            profile = self.collection.find_one({"user_id": user["_id"]})
            if not profile:
                return None

            return json.loads(profile["profile"])
        except Exception as e:
            print(f"Error al obtener perfil cognitivo: {str(e)}")
            return None