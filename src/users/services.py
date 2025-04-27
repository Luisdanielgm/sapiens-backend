from typing import Tuple, Optional, Dict, List
from bson import ObjectId
from datetime import datetime
import json

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
import logging
from src.shared.exceptions import AppException
from .models import User
from src.profiles.services import ProfileService

# Función auxiliar para hacer objetos serializables
def make_json_serializable(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    return obj

class UserService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="users")
        self.profile_service = ProfileService()

    def register_user(self, user_data: dict, institute_name: Optional[str] = None) -> Tuple[bool, str]:
        try:
            # Crear usuario
            user_data_clean = user_data.copy()
            user_data_clean.pop('institute_name', None)
            user = User(**user_data_clean)
            result = self.collection.insert_one(user.to_dict())
            user_id = result.inserted_id

            # Si es INSTITUTE_ADMIN, crear instituto
            if user.role == 'INSTITUTE_ADMIN' and institute_name:
                db = get_db()
                institute_result = db.institutes.insert_one({
                    'name': institute_name,
                    'created_at': datetime.now(),
                    'status': 'pending'
                })
                
                institute_id = institute_result.inserted_id
                
                # Crear relación instituto-admin
                db.institute_members.insert_one({
                    'institute_id': institute_id,
                    'user_id': user_id,
                    'role': 'INSTITUTE_ADMIN',
                    'joined_at': datetime.now()
                })
                
                # Crear perfil del instituto
                try:
                    from src.profiles.services import ProfileService
                    profile_service = ProfileService()
                    profile_service.create_institute_profile(
                        institute_id=str(institute_id),
                        name=institute_name,
                        profile_data=None
                    )
                    
                    # Crear perfil de administrador de instituto
                    profile_service.create_institute_admin_profile(
                        user_id_or_email=str(user_id),
                        institute_id=str(institute_id),
                        profile_data=None
                    )
                except Exception as profile_error:
                    logging.error(f"Error al crear los perfiles de instituto: {str(profile_error)}")
                    # Continuar a pesar del error en la creación del perfil

            # Crear perfiles para el usuario según su rol
            try:
                # Usar el servicio de perfiles para crear el perfil adecuado
                success, message = self.profile_service.create_profile_for_user(str(user_id), user.role)
                if not success:
                    logging.warning(f"No se pudo crear el perfil para el usuario: {message}")
                else:
                    logging.info(f"Perfil creado exitosamente para usuario {user.email}: {message}")
            except Exception as e:
                logging.error(f"Error al crear perfil para el usuario: {str(e)}")
                # No fallamos todo el registro si solo falla el perfil

            return True, str(user_id)

        except Exception as e:
            # Limpiar datos si algo falla
            if 'user_id' in locals():
                self.collection.delete_one({'_id': user_id})
            logging.error(f"Error en register_user: {str(e)}")
            return False, str(e)

    def get_user_profile(self, email_or_id: str) -> Optional[Dict]:
        """
        Obtiene el perfil completo de un usuario utilizando el servicio de perfiles.
        
        Args:
            email_or_id: Email o ID del usuario
            
        Returns:
            Dict: Perfil completo del usuario
        """
        try:
            # Utilizar el servicio de perfiles centralizado
            return self.profile_service.get_user_profile(email_or_id)
        except Exception as e:
            logging.error(f"Error al obtener perfil de usuario: {str(e)}")
            return None

    def verify_user_exists(self, email: str) -> bool:
        """
        Verifica si un usuario con el email dado existe en la base de datos.
        
        Args:
            email: Email del usuario a verificar
            
        Returns:
            True si el usuario existe, False si no
        """
        user = self.collection.find_one({"email": email})
        return user is not None

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
            get_db().class_members.delete_many({"user_id": user_id})
            get_db().classroom_invitations.delete_many({
                "$or": [
                    {"invitee_id": user_id},
                    {"inviter_id": user_id}
                ]
            })
            get_db().contents.delete_many({"student_id": user_id})
            
            # Eliminar perfiles usando el servicio de perfiles
            self.profile_service.delete_student_profile(str(user_id))
            self.profile_service.delete_cognitive_profile(str(user_id))
            
            # Eliminar el usuario
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
            logging.error(f"Error al obtener información del usuario: {str(e)}")
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
            logging.error(f"Error verificando contraseña: {str(e)}")
            return False

class CognitiveProfileService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="cognitive_profiles")

    def update_cognitive_profile(self, email: str, profile_data: str) -> bool:
        """
        Actualiza el perfil cognitivo de un usuario.
        Actualiza tanto el campo 'profile' como los campos individuales para asegurar consistencia.
        
        Args:
            email: Email del usuario
            profile_data: Datos del perfil en formato JSON string o diccionario
            
        Returns:
            bool: True si la actualización fue exitosa, False en caso contrario
        """
        try:
            user = get_db().users.find_one({"email": email})
            if not user:
                logging.warning(f"Usuario no encontrado al actualizar perfil cognitivo: {email}")
                return False

            # Convertir profile_data a diccionario si es string
            if isinstance(profile_data, str):
                profile_dict = json.loads(profile_data)
            else:
                profile_dict = profile_data

            # Asegurar que el user_id sea un ObjectId para la base de datos 
            # si existe en el diccionario
            if "user_id" in profile_dict and not isinstance(profile_dict["user_id"], ObjectId):
                # Si user_id es un string, convertirlo a ObjectId para la BD
                if isinstance(profile_dict["user_id"], str):
                    # Crear una copia para no modificar el original
                    profile_dict_for_db = profile_dict.copy()
                    try:
                        profile_dict_for_db["user_id"] = ObjectId(profile_dict["user_id"])
                    except:
                        # Si no es un ObjectId válido, usar el ID del usuario encontrado
                        profile_dict_for_db["user_id"] = user["_id"]
                else:
                    # Si no es string ni ObjectId, usar el ID del usuario
                    profile_dict_for_db = profile_dict.copy()
                    profile_dict_for_db["user_id"] = user["_id"]
            else:
                # Si no hay user_id o ya es ObjectId, usar como está
                profile_dict_for_db = profile_dict.copy()
                if "user_id" not in profile_dict_for_db:
                    profile_dict_for_db["user_id"] = user["_id"]

            # Crear una versión serializable para JSON usando la función auxiliar
            profile_dict_serializable = make_json_serializable(profile_dict_for_db)

            # Convertir a JSON para almacenar en el campo 'profile'
            profile_json = json.dumps(profile_dict_serializable)

            # Preparar actualización manteniendo los campos individuales también
            update_data = {
                "profile": profile_json,
                "updated_at": datetime.now()
            }
            
            # Actualizar también los campos individuales si existen en profile_dict
            for field in ["learning_style", "diagnosis", "cognitive_strengths", 
                          "cognitive_difficulties", "personal_context", "recommended_strategies"]:
                if field in profile_dict_for_db:
                    update_data[field] = profile_dict_for_db[field]

            # Actualizar documento en la base de datos
            result = self.collection.update_one(
                {"user_id": user["_id"]},
                {"$set": update_data},
                upsert=True
            )
            
            logging.info(f"Perfil cognitivo actualizado para: {email}")
            return True
        except json.JSONDecodeError as e:
            logging.error(f"Error de formato JSON en profile_data: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Error al actualizar perfil cognitivo: {str(e)}")
            return False

    def get_cognitive_profile(self, email: str) -> Optional[Dict]:
        """
        Obtiene el perfil cognitivo de un usuario.
        Maneja tanto perfiles nuevos (con campo 'profile') como perfiles antiguos.
        """
        try:
            user = get_db().users.find_one({"email": email})
            if not user:
                logging.warning(f"Usuario no encontrado: {email}")
                return None

            profile = self.collection.find_one({"user_id": user["_id"]})
            if not profile:
                logging.warning(f"Perfil cognitivo no encontrado para: {email}")
                return None

            # Intentar obtener el perfil del campo 'profile' (formato nuevo)
            if "profile" in profile and profile["profile"]:
                try:
                    return json.loads(profile["profile"])
                except Exception as e:
                    logging.error(f"Error al decodificar el campo 'profile': {str(e)}")
                    # Si falla, intentaremos construir el perfil desde los campos individuales
            
            # Si no hay campo 'profile' o falló al decodificarlo, construimos el perfil 
            # usando los campos individuales (formato antiguo)
            try:
                # Construir el perfil a partir de los campos individuales
                profile_data = {
                    "user_id": profile["user_id"],
                    "learning_style": profile.get("learning_style", {
                        "visual": 0,
                        "kinesthetic": 0,
                        "auditory": 0,
                        "readingWriting": 0
                    }),
                    "diagnosis": profile.get("diagnosis", ""),
                    "cognitive_strengths": profile.get("cognitive_strengths", []),
                    "cognitive_difficulties": profile.get("cognitive_difficulties", []),
                    "personal_context": profile.get("personal_context", ""),
                    "recommended_strategies": profile.get("recommended_strategies", []),
                    "created_at": profile.get("created_at", datetime.now())
                }
                
                # Convertir a formato serializable
                profile_data_serializable = make_json_serializable(profile_data)
                
                # Actualizar el campo 'profile' para futuras consultas
                self.collection.update_one(
                    {"_id": profile["_id"]},
                    {"$set": {"profile": json.dumps(profile_data_serializable)}}
                )
                
                return profile_data_serializable
            except Exception as e:
                logging.error(f"Error al construir perfil desde campos individuales: {str(e)}")
                return None
                
        except Exception as e:
            logging.error(f"Error al obtener perfil cognitivo: {str(e)}")
            return None
