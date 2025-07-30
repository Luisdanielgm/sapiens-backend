from typing import Tuple, Optional, Dict, List
from bson import ObjectId
from datetime import datetime, timedelta
import os
import uuid
import json

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
import logging
from src.shared.exceptions import AppException
from .models import User
from src.profiles.services import ProfileService
import bcrypt
from src.classes.services import ClassService
from src.institute.services import GenericAcademicService

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
        self.class_service = ClassService()
        self.generic_academic_service = GenericAcademicService()

    def register_user(self, user_data: dict, institute_name: Optional[str] = None) -> Tuple[bool, str]:
        try:
            # Hashear contraseña si se proporciona
            if 'password' in user_data and user_data['password']:
                salt = bcrypt.gensalt()
                hashed_password = bcrypt.hashpw(user_data['password'].encode('utf-8'), salt)
                user_data['password'] = hashed_password.decode('utf-8')
                user_data['provider'] = 'email' # Indicar que es un registro local
            else:
                user_data['password'] = None # No guardar contraseña para logins sociales

            # Extraer institute_name localmente sin afectar user_data original
            institute_name_local = institute_name or user_data.get('institute_name')
            # Crear usuario
            # Preparar datos para User sin campo institute_name
            user_data_clean = {k: v for k, v in user_data.items() if k != 'institute_name'}
            user = User(**user_data_clean)
            result = self.collection.insert_one(user.to_dict())
            user_id = result.inserted_id

            # --- LÓGICA PARA ROLES INDIVIDUALES Y DE INSTITUTO ---
            user_role = user.role
            
            # Flujo para Administrador de Instituto
            if user_role == 'INSTITUTE_ADMIN' and institute_name_local:
                db = get_db()
                institute_result = db.institutes.insert_one({
                    'name': institute_name_local,
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
                        name=institute_name_local,
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

            # Flujo para Usuarios Individuales (Profesores y Estudiantes)
            elif user_role in ['INDIVIDUAL_TEACHER', 'INDIVIDUAL_STUDENT']:
                db = get_db()
                
                # 1. Obtener/Crear Instituto y Entidades Académicas Genéricas
                generic_entities = self.generic_academic_service.get_or_create_generic_entities()
                institute_id = ObjectId(generic_entities["institute_id"])
                
                # 2. Vincular al usuario como miembro del instituto genérico
                db.institute_members.insert_one({
                    'institute_id': institute_id,
                    'user_id': user_id,
                    'role': user_role, # Mantener su rol específico
                    'joined_at': datetime.now()
                })

                # 3. Flujo especial para profesores individuales: crear una clase personal
                if user_role == 'INDIVIDUAL_TEACHER':
                    # Usar los IDs de las entidades genéricas para crear la clase
                    class_data = {
                        "name": f"Clase Personal de {user.name}",
                        "description": "Tu espacio para crear y gestionar tus propios planes de estudio.",
                        "institute_id": generic_entities["institute_id"],
                        "level_id": generic_entities["level_id"],
                        "academic_period_id": generic_entities["academic_period_id"],
                        "subject_id": generic_entities["subject_id"],
                        "section_id": generic_entities["section_id"],
                        "created_by": str(user_id)
                    }
                    try:
                        success, class_id_or_msg = self.class_service.create_class(class_data)
                        if success:
                            logging.info(f"Clase personal creada para profesor individual {user_id}: {class_id_or_msg}")
                        else:
                            logging.warning(f"No se pudo crear la clase personal para {user_id}: {class_id_or_msg}")
                    except Exception as e:
                        logging.error(f"Error creando clase para profesor individual: {str(e)}")


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

    def login_user(self, email: str, password: str) -> Optional[Dict]:
        """
        Autentica a un usuario por email y contraseña.
        
        Args:
            email: Email del usuario
            password: Contraseña en texto plano
            
        Returns:
            Diccionario con datos del usuario si las credenciales son correctas, de lo contrario None.
        """
        try:
            user = self.collection.find_one({"email": email})
            
            if not user:
                return None # Usuario no encontrado

            hashed_password = user.get('password')
            if not hashed_password:
                return None # El usuario no tiene contraseña (es de un proveedor social)
                
            if self.verify_password(password, hashed_password):
                # Contraseña correcta, devolver datos del usuario
                return {
                    "id": str(user["_id"]),
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"]
                }
            
            return None # Contraseña incorrecta
        except Exception as e:
            logging.error(f"Error en login_user: {str(e)}")
            return None

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
            get_db().class_invitations.delete_many({
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

    def get_user_info_by_id(self, user_id: str) -> Optional[Dict]:
        """Obtiene información básica del usuario a partir de su ID"""
        try:
            user = self.collection.find_one({"_id": ObjectId(user_id)})
            if user:
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
            logging.error(f"Error al obtener información del usuario por ID: {str(e)}")
            return None

    def verify_password(self, plain_password, hashed_password):
        """Verifica si la contraseña en texto plano coincide con el hash almacenado"""
        try:
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

    # ---------------------------------------------------------
    # Recuperación de contraseña
    # ---------------------------------------------------------

    def generate_reset_token(self, email: str) -> None:
        """Genera un token de restablecimiento y lo registra en el usuario."""
        try:
            user = self.collection.find_one({"email": email})
            if not user:
                logging.info(f"Solicitud de restablecimiento para email no registrado: {email}")
                return

            token = uuid.uuid4().hex
            expires = datetime.now() + timedelta(hours=1)

            self.collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"reset_token": token, "reset_token_expires": expires}}
            )

            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            reset_link = f"{frontend_url}/reset-password?token={token}"
            logging.info(f"Enlace de restablecimiento para {email}: {reset_link}")
        except Exception as e:
            logging.error(f"Error generando token de restablecimiento: {str(e)}")

    def reset_password(self, token: str, new_password: str) -> Tuple[bool, str]:
        """Actualiza la contraseña usando un token de restablecimiento."""
        try:
            user = self.collection.find_one({"reset_token": token})
            if not user:
                return False, "Token inválido"

            expires = user.get("reset_token_expires")
            if not expires or expires < datetime.now():
                return False, "Token expirado"

            hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            self.collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {"password": hashed},
                    "$unset": {"reset_token": "", "reset_token_expires": ""}
                }
            )
            return True, "Contraseña actualizada"
        except Exception as e:
            logging.error(f"Error restableciendo contraseña: {str(e)}")
            return False, str(e)
