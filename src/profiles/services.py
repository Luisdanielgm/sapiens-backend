from typing import Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
import json

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.logging import log_error, log_info, log_warning
from src.profiles.models import TeacherProfile, StudentProfile, AdminProfile, CognitiveProfile, InstituteAdminProfile, InstituteProfile


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


class ProfileService(VerificationBaseService):
    """
    Servicio para gestionar los perfiles específicos de los diferentes roles de usuario.
    Incluye funcionalidad para crear, actualizar y obtener perfiles de profesores, estudiantes y administradores.
    """
    def __init__(self):
        super().__init__(collection_name="profiles")
    
    def _get_user_id(self, user_id_or_email: str) -> Optional[ObjectId]:
        """
        Obtiene el ID de usuario a partir del ID o email proporcionado.
        
        Args:
            user_id_or_email: ID o email del usuario
            
        Returns:
            ObjectId: ID del usuario si se encuentra, None en caso contrario
        """
        try:
            if ObjectId.is_valid(user_id_or_email):
                user = self.db.users.find_one({"_id": ObjectId(user_id_or_email)})
            else:
                user = self.db.users.find_one({"email": user_id_or_email})
            
            if user and "_id" in user:
                return user["_id"]
            return None
        except Exception as e:
            log_error(f"Error al obtener ID de usuario para '{user_id_or_email}'", e, "profiles.services")
            return None
    
    def get_user_role(self, user_id_or_email: str) -> Optional[str]:
        """
        Obtiene el rol del usuario.
        
        Args:
            user_id_or_email: ID o email del usuario
            
        Returns:
            str: Rol del usuario si se encuentra, None en caso contrario
        """
        try:
            if ObjectId.is_valid(user_id_or_email):
                user = self.db.users.find_one({"_id": ObjectId(user_id_or_email)})
            else:
                user = self.db.users.find_one({"email": user_id_or_email})
            
            if user and "role" in user:
                return user["role"]
            return None
        except Exception as e:
            log_error(f"Error al obtener rol de usuario para '{user_id_or_email}'", e, "profiles.services")
            return None
    
    #
    # MÉTODOS PARA PERFIL DE PROFESOR
    #
    
    def create_teacher_profile(self, user_id_or_email: str, profile_data: Dict) -> Tuple[bool, str]:
        """
        Crea un nuevo perfil de profesor
        
        Args:
            user_id_or_email: ID o email del usuario profesor
            profile_data: Datos del perfil a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del perfil)
        """
        try:
            # Verificar si el usuario existe y es profesor
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False, f"Usuario no encontrado: {user_id_or_email}"
            
            user_role = self.get_user_role(user_id_or_email)
            if user_role != "TEACHER":
                return False, f"El usuario no es un profesor: {user_id_or_email}"
            
            # Verificar si ya existe un perfil
            existing_profile = self.db.teacher_profiles.find_one({"user_id": user_id})
            if existing_profile:
                return False, f"Ya existe un perfil para este profesor: {user_id_or_email}"
            
            # Crear un nuevo perfil
            profile_data["user_id"] = user_id
            teacher_profile = TeacherProfile(**profile_data)
            result = self.db.teacher_profiles.insert_one(teacher_profile.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear perfil de profesor: {str(e)}", e, "profiles.services")
            return False, str(e)
    
    def get_teacher_profile(self, user_id_or_email: str, workspace_info: Dict = None) -> Optional[Dict]:
        """
        Obtiene el perfil de profesor para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario profesor
            workspace_info: Información del workspace actual (opcional)
            
        Returns:
            Dict: Información del perfil de profesor si existe, None en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return None
        
        # Construir filtro base
        filter_query = {"user_id": user_id}
        
        # Aplicar filtrado por workspace si se proporciona
        if workspace_info:
            workspace_type = workspace_info.get('workspace_type')
            workspace_id = workspace_info.get('workspace_id')
            
            if workspace_type == 'INDIVIDUAL_TEACHER':
                # En workspaces individuales, filtrar por workspace_id
                filter_query["workspace_id"] = ObjectId(workspace_id)
            elif workspace_type == 'INSTITUTE':
                # En workspaces institucionales, filtrar por institute_id
                institute_id = workspace_info.get('institute_id')
                if institute_id:
                    filter_query["institute_id"] = ObjectId(institute_id)
            
        profile = self.db.teacher_profiles.find_one(filter_query)
        if not profile:
            return None
            
        # Convertir ObjectId a string para serialización
        profile["_id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        
        # Obtener información del usuario asociado
        user = self.db.users.find_one({"_id": user_id})
        if user:
            profile["user"] = {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "picture": user.get("picture", "")
            }
        
        # Agregar información del workspace si está disponible
        if workspace_info:
            profile["workspace_context"] = {
                "workspace_type": workspace_info.get('workspace_type'),
                "workspace_name": workspace_info.get('workspace_name')
            }
            
        return profile
    
    def update_teacher_profile(self, user_id_or_email: str, profile_data: Dict) -> bool:
        """
        Actualiza o crea un perfil de profesor
        
        Args:
            user_id_or_email: ID o email del usuario profesor
            profile_data: Datos del perfil a actualizar
            
        Raises:
            AppException: Si el usuario no existe o si ocurre un error durante la actualización
        """
        if not self.check_user_exists(user_id_or_email):
            raise AppException(f"Usuario no encontrado: {user_id_or_email}", AppException.NOT_FOUND)
        
        user_id = self._get_user_id(user_id_or_email)
        
        # Verificar si ya existe un perfil
        profile = self.db.teacher_profiles.find_one({"user_id": user_id})
        
        try:
            if profile:
                # Actualizar perfil existente
                profile_data["updated_at"] = datetime.now()
                result = self.db.teacher_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": profile_data}
                )
                
                if result.modified_count == 0:
                    raise AppException("No se realizaron cambios al perfil", AppException.BAD_REQUEST)
            else:
                # Crear un nuevo perfil
                profile_data["user_id"] = user_id
                profile_data["created_at"] = datetime.now()
                profile_data["updated_at"] = datetime.now()
                
                teacher_profile = TeacherProfile(**profile_data)
                self.db.teacher_profiles.insert_one(teacher_profile.to_dict())
            
            return True
        except AppException:
            raise
        except Exception as e:
            log_error(f"Error al actualizar perfil de profesor: {str(e)}", e, "profiles.services")
            raise AppException(f"Error al actualizar perfil de profesor: {str(e)}", AppException.BAD_REQUEST)
    
    def delete_teacher_profile(self, user_id_or_email: str) -> bool:
        """
        Elimina el perfil de profesor para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario profesor
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return False
            
        result = self.db.teacher_profiles.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    #
    # MÉTODOS PARA PERFIL DE ESTUDIANTE
    #
    
    def create_student_profile(self, user_id_or_email: str, profile_data: Dict) -> Tuple[bool, str]:
        """
        Crea un nuevo perfil de estudiante
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            profile_data: Datos del perfil a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del perfil)
        """
        try:
            # Verificar si el usuario existe y es estudiante
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False, f"Usuario no encontrado: {user_id_or_email}"
            
            # Permitir que todos los roles puedan crear perfiles cognitivos
            user_role = self.get_user_role(user_id_or_email)
            if not user_role:
                return False, f"No se pudo determinar el rol del usuario: {user_id_or_email}"
            
            # Verificar si ya existe un perfil
            existing_profile = self.db.student_profiles.find_one({"user_id": user_id})
            if existing_profile:
                return False, f"Ya existe un perfil para este estudiante: {user_id_or_email}"
            
            # Crear un nuevo perfil
            profile_data["user_id"] = user_id
            student_profile = StudentProfile(**profile_data)
            result = self.db.student_profiles.insert_one(student_profile.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear perfil de estudiante: {str(e)}", e, "profiles.services")
            return False, str(e)
    
    def get_student_profile(self, user_id_or_email: str, workspace_info: Dict = None) -> Optional[Dict]:
        """
        Obtiene el perfil de estudiante para un usuario específico.
        Si el perfil no existe pero el usuario sí, intenta crearlo automáticamente.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            workspace_info: Información del workspace actual (opcional)
            
        Returns:
            Dict: Información del perfil de estudiante si existe, None en caso contrario
        """
        try:
            # Decodificar el email si está codificado en URL
            if '%40' in user_id_or_email:
                from urllib.parse import unquote
                decoded_id_or_email = unquote(user_id_or_email)
                log_info(f"Email codificado detectado. Original: {user_id_or_email}, Decodificado: {decoded_id_or_email}", "profiles.services")
                user_id_or_email = decoded_id_or_email
            
            log_info(f"Buscando perfil de estudiante para: {user_id_or_email}", "profiles.services")
            
            # Obtener user_id
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                log_info(f"No se encontró usuario con ID/email: {user_id_or_email}", "profiles.services")
                return None
                
            log_info(f"ID de usuario encontrado: {user_id}", "profiles.services")
            
            # Construir filtro base
            filter_query = {"user_id": user_id}
            
            # Aplicar filtrado por workspace si se proporciona
            if workspace_info:
                workspace_type = workspace_info.get('workspace_type')
                workspace_id = workspace_info.get('workspace_id')
                
                if workspace_type == 'INDIVIDUAL_STUDENT':
                    # En workspaces individuales, filtrar por workspace_id
                    filter_query["workspace_id"] = ObjectId(workspace_id)
                elif workspace_type == 'INSTITUTE':
                    # En workspaces institucionales, filtrar por institute_id
                    institute_id = workspace_info.get('institute_id')
                    if institute_id:
                        filter_query["institute_id"] = ObjectId(institute_id)
            
            # Buscar perfil con filtros aplicados
            profile = self.db.student_profiles.find_one(filter_query)
            
            # Si no se encuentra, verificar si existe un perfil pero con una representación diferente del ObjectId
            if not profile:
                log_info(f"No se encontró perfil para user_id exacto: {user_id}", "profiles.services")
                
                # Intentar buscando directamente por email
                user = self.db.users.find_one({"email": user_id_or_email})
                if user:
                    profile_by_user = self.db.student_profiles.find_one({"user_id": user["_id"]})
                    if profile_by_user:
                        log_info(f"Se encontró perfil buscando directamente por email del usuario", "profiles.services")
                        profile = profile_by_user
                
                # Si todavía no lo encuentra, intentar con el ID como string
                if not profile:
                    user_id_str = str(user_id)
                    profile_by_str = self.db.student_profiles.find_one({"user_id": user_id_str})
                    
                    if profile_by_str:
                        log_info(f"Se encontró perfil con user_id como string: {user_id_str}", "profiles.services")
                        # Corregir el perfil para que use ObjectId
                        self.db.student_profiles.update_one(
                            {"_id": profile_by_str["_id"]},
                            {"$set": {"user_id": user_id}}
                        )
                        profile = profile_by_str
                    else:
                        # Verificar si el usuario existe y es un estudiante antes de crear un perfil nuevo
                        user = self.db.users.find_one({"_id": user_id})
                        
                        if user and user.get("role") == "STUDENT":
                            log_info(f"Creando perfil de estudiante para usuario existente: {user.get('email')}", "profiles.services")
                            
                            # Crear un nuevo perfil de estudiante
                            student_profile = StudentProfile(
                                user_id=str(user_id),
                                educational_background="",
                                interests=[],
                                preferred_learning_style="visual"
                            )
                            
                            # Guardar en la colección student_profiles
                            result = self.db.student_profiles.insert_one(student_profile.to_dict())
                            
                            # Obtener el perfil recién creado
                            profile = self.db.student_profiles.find_one({"_id": result.inserted_id})
                            log_info(f"Perfil de estudiante creado con ID: {result.inserted_id}", "profiles.services")
                        else:
                            # Mostrar todos los perfiles para depuración
                            all_profiles = list(self.db.student_profiles.find())
                            log_info(f"Total de perfiles encontrados: {len(all_profiles)}", "profiles.services")
                            
                            for p in all_profiles:
                                prof_user_id = p.get('user_id')
                                log_info(f"Perfil disponible - user_id: {prof_user_id} (tipo: {type(prof_user_id)})", "profiles.services")
                            
                            log_info(f"No se pudo crear el perfil. Usuario no encontrado o no es estudiante.", "profiles.services")
                            return None
            
            if profile:
                log_info(f"Perfil encontrado con ID: {profile.get('_id')}", "profiles.services")
                
                # Convertir ObjectId a string para serialización
                profile["_id"] = str(profile["_id"])
                if isinstance(profile["user_id"], ObjectId):
                    profile["user_id"] = str(profile["user_id"])
                
                # Obtener información del usuario asociado
                user = self.db.users.find_one({"_id": user_id})
                if user:
                    profile["user"] = {
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "picture": user.get("picture", "")
                    }
                
                # Agregar información del workspace si está disponible
                if workspace_info:
                    profile["workspace_context"] = {
                        "workspace_type": workspace_info.get('workspace_type'),
                        "workspace_name": workspace_info.get('workspace_name')
                    }
                    
                return profile
            return None
        except Exception as e:
            log_error(f"Error al obtener perfil de estudiante: {str(e)}", e, "profiles.services")
            return None
    
    def update_student_profile(self, user_id_or_email: str, profile_data: Dict) -> bool:
        """
        Actualiza el perfil de estudiante para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            profile_data: Datos del perfil a actualizar
            
        Raises:
            AppException: Si el usuario no existe o si ocurre un error durante la actualización
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            raise AppException(f"Usuario no encontrado: {user_id_or_email}", AppException.NOT_FOUND)
            
        # Verificar si ya existe un perfil
        profile = self.db.student_profiles.find_one({"user_id": user_id})
        
        try:
            if profile:
                # Actualizar perfil existente
                profile_data["updated_at"] = datetime.now()
                result = self.db.student_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": profile_data}
                )
                
                if result.modified_count == 0:
                    log_info(f"No se realizaron cambios al perfil de estudiante para: {user_id_or_email}", "profiles.services")
            else:
                # Crear un nuevo perfil
                profile_data["user_id"] = user_id
                profile_data["created_at"] = datetime.now()
                profile_data["updated_at"] = datetime.now()
                
                student_profile = StudentProfile(**profile_data)
                self.db.student_profiles.insert_one(student_profile.to_dict())
                log_info(f"Perfil de estudiante creado para: {user_id_or_email}", "profiles.services")
            
            return True
        except Exception as e:
            log_error(f"Error al actualizar perfil de estudiante: {str(e)}", e, "profiles.services")
            raise AppException(f"Error al actualizar perfil de estudiante: {str(e)}", AppException.BAD_REQUEST)
    
    def delete_student_profile(self, user_id_or_email: str) -> bool:
        """
        Elimina el perfil de estudiante para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return False
            
        result = self.db.student_profiles.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    #
    # MÉTODOS PARA PERFIL DE ADMINISTRADOR
    #
    
    def create_admin_profile(self, user_id_or_email: str, profile_data: Dict) -> Tuple[bool, str]:
        """
        Crea un nuevo perfil de administrador
        
        Args:
            user_id_or_email: ID o email del usuario administrador
            profile_data: Datos del perfil a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del perfil)
        """
        try:
            # Verificar si el usuario existe y es administrador
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False, f"Usuario no encontrado: {user_id_or_email}"
            
            user_role = self.get_user_role(user_id_or_email)
            if user_role not in ["ADMIN", "INSTITUTE_ADMIN"]:
                return False, f"El usuario no es un administrador: {user_id_or_email}"
            
            # Verificar si ya existe un perfil
            existing_profile = self.db.admin_profiles.find_one({"user_id": user_id})
            if existing_profile:
                return False, f"Ya existe un perfil para este administrador: {user_id_or_email}"
            
            # Crear un nuevo perfil
            profile_data["user_id"] = user_id
            admin_profile = AdminProfile(**profile_data)
            result = self.db.admin_profiles.insert_one(admin_profile.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear perfil de administrador: {str(e)}", e, "profiles.services")
            return False, str(e)
    
    def get_admin_profile(self, user_id_or_email: str) -> Optional[Dict]:
        """
        Obtiene el perfil de administrador para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador
            
        Returns:
            Dict: Información del perfil de administrador si existe, None en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return None
            
        profile = self.db.admin_profiles.find_one({"user_id": user_id})
        if not profile:
            return None
            
        # Convertir ObjectId a string para serialización
        profile["_id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        
        # Obtener información del usuario asociado
        user = self.db.users.find_one({"_id": user_id})
        if user:
            profile["user"] = {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "picture": user.get("picture", "")
            }
            
        return profile
    
    def update_admin_profile(self, user_id_or_email: str, profile_data: Dict) -> bool:
        """
        Actualiza el perfil de administrador para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador
            profile_data: Datos del perfil a actualizar
            
        Raises:
            AppException: Si el usuario no existe o si ocurre un error durante la actualización
        """
        if not self.check_user_exists(user_id_or_email):
            raise AppException(f"Usuario no encontrado: {user_id_or_email}", AppException.NOT_FOUND)
        
        user_id = self._get_user_id(user_id_or_email)
        
        # Verificar si ya existe un perfil
        profile = self.db.admin_profiles.find_one({"user_id": user_id})
        
        try:
            if profile:
                # Actualizar perfil existente
                profile_data["updated_at"] = datetime.now()
                result = self.db.admin_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": profile_data}
                )
                
                if result.modified_count == 0:
                    raise AppException("No se realizaron cambios al perfil", AppException.BAD_REQUEST)
            else:
                # Crear un nuevo perfil
                profile_data["user_id"] = user_id
                profile_data["created_at"] = datetime.now()
                profile_data["updated_at"] = datetime.now()
                
                admin_profile = AdminProfile(**profile_data)
                self.db.admin_profiles.insert_one(admin_profile.to_dict())
            
            return True
        except AppException:
            raise
        except Exception as e:
            log_error(f"Error al actualizar perfil de administrador: {str(e)}", e, "profiles.services")
            raise AppException(f"Error al actualizar perfil de administrador: {str(e)}", AppException.BAD_REQUEST)
    
    def delete_admin_profile(self, user_id_or_email: str) -> bool:
        """
        Elimina el perfil de administrador para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return False
            
        result = self.db.admin_profiles.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    #
    # MÉTODOS PARA PERFIL COGNITIVO
    #
    
    def create_cognitive_profile(self, user_id_or_email: str, profile_data: Dict = None) -> Tuple[bool, str]:
        """
        Crea un nuevo perfil cognitivo para un estudiante.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            profile_data: Datos del perfil a crear (opcional)
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del perfil)
        """
        try:
            # Verificar si el usuario existe y es estudiante
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False, f"Usuario no encontrado: {user_id_or_email}"
            
            user_role = self.get_user_role(user_id_or_email)
            if user_role != "STUDENT":
                return False, f"El usuario no es un estudiante: {user_id_or_email}"
            
            # Verificar si ya existe un perfil cognitivo
            existing_profile = self.db.cognitive_profiles.find_one({"user_id": user_id})
            if existing_profile:
                return False, f"Ya existe un perfil cognitivo para este estudiante: {user_id_or_email}"
            
            # Crear un nuevo perfil cognitivo con valores por defecto o con los datos proporcionados
            cognitive_profile = CognitiveProfile(
                user_id=str(user_id),
                **(profile_data or {})
            )
            
            # Convertir a versión serializable
            profile_dict = cognitive_profile.to_dict()
            profile_dict_serializable = make_json_serializable(profile_dict)
            
            # Guardar el perfil cognitivo
            result = self.db.cognitive_profiles.insert_one({
                "user_id": profile_dict["user_id"],  # Mantener como ObjectId para la BD
                "learning_style": profile_dict["learning_style"],
                "diagnosis": profile_dict["diagnosis"],
                "cognitive_strengths": profile_dict["cognitive_strengths"],
                "cognitive_difficulties": profile_dict["cognitive_difficulties"],
                "personal_context": profile_dict["personal_context"],
                "recommended_strategies": profile_dict["recommended_strategies"],
                "created_at": profile_dict["created_at"],
                "updated_at": profile_dict["updated_at"],
                "profile": json.dumps(profile_dict_serializable)  # Versión serializable
            })
            
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear perfil cognitivo: {str(e)}", e, "profiles.services")
            return False, str(e)
    
    def get_cognitive_profile(self, user_id_or_email: str) -> Optional[Dict]:
        """
        Obtiene el perfil cognitivo para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            
        Returns:
            Dict: Información del perfil cognitivo si existe, None en caso contrario
        """
        try:
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return None
                
            profile = self.db.cognitive_profiles.find_one({"user_id": user_id})
            if not profile:
                return None
                
            # Convertir ObjectId a string para serialización
            profile["_id"] = str(profile["_id"])
            profile["user_id"] = str(profile["user_id"])
            
            # Cargar el perfil completo desde el campo profile si existe
            if "profile" in profile and profile["profile"]:
                try:
                    profile_data = json.loads(profile["profile"])
                    profile["profile_data"] = profile_data
                except:
                    profile["profile_data"] = {}
            
            # Obtener información del usuario asociado
            user = self.db.users.find_one({"_id": user_id})
            if user:
                profile["user"] = {
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "picture": user.get("picture", "")
                }
                
            return profile
        except Exception as e:
            log_error(f"Error al obtener perfil cognitivo: {str(e)}", e, "profiles.services")
            return None
    
    def update_cognitive_profile(self, user_id_or_email: str, profile_data: Dict) -> bool:
        """
        Actualiza el perfil cognitivo para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            profile_data: Datos del perfil a actualizar (puede ser un diccionario o un string JSON)
            
        Returns:
            bool: True si se actualizó correctamente, False en caso contrario
        """
        try:
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False
            
            # Convertir profile_data a diccionario si es string
            if isinstance(profile_data, str):
                profile_dict = json.loads(profile_data)
            else:
                profile_dict = profile_data
            
            # Crear una versión serializable para almacenar en el campo 'profile'
            profile_dict_serializable = make_json_serializable(profile_dict)
            
            # Verificar si ya existe un perfil
            existing_profile = self.db.cognitive_profiles.find_one({"user_id": user_id})
            
            # Mapeo entre camelCase y snake_case para las claves del perfil cognitivo
            field_mapping = {
                "learningStyle": "learning_style",
                "cognitiveStrengths": "cognitive_strengths",
                "cognitiveDifficulties": "cognitive_difficulties",
                "personalContext": "personal_context",
                "recommendedStrategies": "recommended_strategies"
            }
            
            if existing_profile:
                # Actualizar perfil existente
                update_data = {
                    "updated_at": datetime.now(),
                    "profile": json.dumps(profile_dict_serializable)
                }
                
                # Actualizar campos individuales desde el perfil_dict
                for camel_case_field, snake_case_field in field_mapping.items():
                    if camel_case_field in profile_dict:
                        update_data[snake_case_field] = profile_dict[camel_case_field]
                    
                # También manejar campos que ya están en snake_case
                for field in ["learning_style", "diagnosis", "cognitive_strengths", 
                              "cognitive_difficulties", "personal_context", "recommended_strategies"]:
                    if field in profile_dict:
                        update_data[field] = profile_dict[field]
                
                # Asegurar que diagnosis se actualice correctamente
                if "diagnosis" in profile_dict:
                    update_data["diagnosis"] = profile_dict["diagnosis"]
                
                result = self.db.cognitive_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": update_data}
                )
                
                return result.acknowledged
            else:
                # Crear un nuevo perfil cognitivo
                # Convertir campos de camelCase a snake_case para el nuevo perfil
                new_profile_data = {}
                
                for camel_case_field, snake_case_field in field_mapping.items():
                    if camel_case_field in profile_dict:
                        new_profile_data[snake_case_field] = profile_dict[camel_case_field]
                
                # También incluir campos que ya están en snake_case
                for field in ["learning_style", "diagnosis", "cognitive_strengths", 
                              "cognitive_difficulties", "personal_context", "recommended_strategies"]:
                    if field in profile_dict:
                        new_profile_data[field] = profile_dict[field]
                
                # Asegurar que diagnosis se incluya correctamente
                if "diagnosis" in profile_dict:
                    new_profile_data["diagnosis"] = profile_dict["diagnosis"]
                
                return self.create_cognitive_profile(user_id_or_email, new_profile_data)[0]
                
        except Exception as e:
            log_error(f"Error al actualizar perfil cognitivo: {str(e)}", e, "profiles.services")
            return False
    
    def delete_cognitive_profile(self, user_id_or_email: str) -> bool:
        """
        Elimina el perfil cognitivo para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return False
            
        result = self.db.cognitive_profiles.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    #
    # MÉTODOS GENERALES
    #
    
    def check_user_exists(self, user_id_or_email: str) -> bool:
        """
        Verifica si un usuario existe en la base de datos.
        
        Args:
            user_id_or_email: ID o email del usuario
            
        Returns:
            bool: True si el usuario existe, False en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        return user_id is not None
    
    def create_profile_for_user(self, user_id_or_email: str, user_role: str = None) -> Tuple[bool, str]:
        """
        Crea el perfil adecuado según el rol del usuario, manejando roles base y roles individuales.
        """
        if not user_role:
            user_role = self.get_user_role(user_id_or_email)
            
        if not user_role:
            return False, f"No se pudo determinar el rol del usuario: {user_id_or_email}"
            
        base_role = user_role

        if base_role == "TEACHER":
            return self.create_teacher_profile(user_id_or_email, {})
        elif base_role == "STUDENT":
            # Para estudiantes, crear tanto el perfil regular como el cognitivo
            success, message = self.create_student_profile(user_id_or_email, {})
            if not success:
                # Si el perfil ya existe (puede pasar en flujos complejos), no lo tratamos como un error fatal
                if "Ya existe un perfil" in message:
                    log_info(f"Perfil de estudiante ya existía para {user_id_or_email}. Se omite la creación.", "profiles.services")
                else:
                    return False, message
            
            # Intentar crear perfil cognitivo solo si no existe
            if not self.db.cognitive_profiles.find_one({"user_id": self._get_user_id(user_id_or_email)}):
                cognitive_success, cognitive_message = self.create_cognitive_profile(user_id_or_email)
                if not cognitive_success:
                    log_info(f"No se pudo crear el perfil cognitivo, pero se creó/verificó el perfil regular: {cognitive_message}", "profiles.services")
            
            return True, message
        elif base_role == "ADMIN":
            return self.create_admin_profile(user_id_or_email, {})
        elif base_role == "INSTITUTE_ADMIN":
            # Para administradores de instituto, primero necesitamos obtener el ID del instituto
            try:
                user_id = self._get_user_id(user_id_or_email)
                # Buscar la relación instituto-admin
                institute_member = self.db.institute_members.find_one({
                    "user_id": user_id,
                    "role": "INSTITUTE_ADMIN"
                })
                
                if not institute_member or "institute_id" not in institute_member:
                    # Si no hay relación, mostrar error, no crear perfil admin estándar
                    return False, f"No se encontró relación instituto-admin para {user_id_or_email}"
                
                institute_id = str(institute_member["institute_id"])
                
                # Crear perfil de administrador de instituto
                admin_success, admin_message = self.create_institute_admin_profile(
                    user_id_or_email, 
                    institute_id,
                    {
                        "role_in_institute": "INSTITUTE_ADMIN",
                        "responsibilities": ["Gestión general del instituto"]
                    }
                )
                
                if not admin_success:
                    return False, admin_message
                    
                # Verificar si ya existe un perfil para el instituto, si no, crearlo
                institute = self.db.institutes.find_one({"_id": ObjectId(institute_id)})
                if institute:
                    if not self.db.institute_profiles.find_one({"institute_id": ObjectId(institute_id)}):
                        # Crear perfil básico del instituto
                        institute_success, institute_message = self.create_institute_profile(
                            institute_id, 
                            institute.get("name", "Instituto sin nombre"),
                            {
                                "status": institute.get("status", "active"),
                                "created_at": institute.get("created_at", datetime.now())
                            }
                        )
                        if not institute_success:
                            log_warning(f"No se pudo crear perfil del instituto: {institute_message}", "profiles.services")
                
                return admin_success, admin_message
            except Exception as e:
                log_error(f"Error al crear perfil de administrador de instituto: {str(e)}", e, "profiles.services")
                return False, f"Error al crear perfil: {str(e)}"
        else:
            return False, f"Rol de usuario no soportado: {user_role}"
    
    def get_user_profile(self, user_id_or_email: str) -> Optional[Dict]:
        """
        Obtiene el perfil completo de un usuario, incluyendo su perfil específico según el rol.
        
        Args:
            user_id_or_email: ID o email del usuario
            
        Returns:
            Dict: Perfil completo del usuario
        """
        try:
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return None
                
            # Obtener información básica del usuario
            user = self.db.users.find_one({"_id": user_id})
            if not user:
                return None
                
            # Crear respuesta base
            profile_data = {
                "user_info": {
                    "id": str(user["_id"]),
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "role": user.get("role", ""),
                    "picture": user.get("picture", ""),
                    "status": user.get("status", "active")
                },
                "specific_profile": None,
                "cognitive_profile": None
            }
            
            # Obtener perfil específico según el rol
            role = user.get("role", "")
            if role == "TEACHER":
                specific_profile = self.get_teacher_profile(user_id_or_email)
                if specific_profile:
                    profile_data["specific_profile"] = specific_profile
            elif role == "STUDENT":
                specific_profile = self.get_student_profile(user_id_or_email)
                if specific_profile:
                    profile_data["specific_profile"] = specific_profile
                    
                # Añadir perfil cognitivo para estudiantes
                cognitive_profile = self.get_cognitive_profile(user_id_or_email)
                if cognitive_profile:
                    profile_data["cognitive_profile"] = cognitive_profile
            elif role in ["ADMIN", "INSTITUTE_ADMIN"]:
                specific_profile = self.get_admin_profile(user_id_or_email)
                if specific_profile:
                    profile_data["specific_profile"] = specific_profile
            
            return profile_data
        except Exception as e:
            log_error(f"Error al obtener perfil de usuario: {str(e)}", e, "profiles.services")
            return None
    
    #
    # MÉTODOS PARA PERFIL DE ADMINISTRADOR DE INSTITUTO
    #
    
    def create_institute_admin_profile(self, user_id_or_email: str, institute_id: str, profile_data: Dict = None) -> Tuple[bool, str]:
        """
        Crea un nuevo perfil de administrador de instituto
        
        Args:
            user_id_or_email: ID o email del usuario administrador de instituto
            institute_id: ID del instituto que administra
            profile_data: Datos adicionales del perfil a crear (opcional)
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del perfil)
        """
        try:
            # Verificar si el usuario existe y es administrador de instituto
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False, f"Usuario no encontrado: {user_id_or_email}"
            
            user_role = self.get_user_role(user_id_or_email)
            if user_role != "INSTITUTE_ADMIN":
                return False, f"El usuario no es un administrador de instituto: {user_id_or_email}"
            
            # Verificar si ya existe un perfil
            existing_profile = self.db.institute_admin_profiles.find_one({"user_id": user_id})
            if existing_profile:
                return True, str(existing_profile["_id"])  # Retornamos éxito y el ID si ya existe
            
            # Verificar que el instituto exista
            institute_obj_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
            institute = self.db.institutes.find_one({"_id": institute_obj_id})
            if not institute:
                return False, f"No se encontró el instituto con ID: {institute_id}"
            
            # Verificar relación instituto-admin si no se está creando junto con el usuario
            if not self.db.institute_members.find_one({
                "user_id": user_id, 
                "institute_id": institute_obj_id, 
                "role": "INSTITUTE_ADMIN"
            }):
                # Crear la relación si no existe
                log_info(f"Creando relación instituto-admin para usuario {user_id_or_email}", "profiles.services")
                self.db.institute_members.insert_one({
                    "institute_id": institute_obj_id,
                    "user_id": user_id,
                    "role": "INSTITUTE_ADMIN",
                    "joined_at": datetime.now()
                })
            
            # Crear un nuevo perfil con los datos proporcionados
            profile_data = profile_data or {}
            
            # Asegurar campos mínimos
            if "institute_permissions" not in profile_data:
                profile_data["institute_permissions"] = ["manage_members", "manage_courses", "view_reports"]
            if "responsibilities" not in profile_data:
                profile_data["responsibilities"] = ["Gestión general del instituto"]
                
            profile_data["user_id"] = user_id
            profile_data["institute_id"] = institute_obj_id
            profile_data["role_in_institute"] = profile_data.get("role_in_institute", "INSTITUTE_ADMIN")
            
            institute_admin_profile = InstituteAdminProfile(**profile_data)
            result = self.db.institute_admin_profiles.insert_one(institute_admin_profile.to_dict())
            
            log_info(f"Perfil de administrador de instituto creado para usuario {user_id_or_email}", "profiles.services")
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear perfil de administrador de instituto: {str(e)}", e, "profiles.services")
            return False, str(e)
    
    def get_institute_admin_profile(self, user_id_or_email: str) -> Optional[Dict]:
        """
        Obtiene el perfil de administrador de instituto para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador de instituto
            
        Returns:
            Dict: Información del perfil de administrador de instituto si existe, None en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return None
            
        profile = self.db.institute_admin_profiles.find_one({"user_id": user_id})
        if not profile:
            return None
            
        # Convertir ObjectId a string para serialización
        profile["_id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        profile["institute_id"] = str(profile["institute_id"])
        
        # Obtener información del usuario asociado
        user = self.db.users.find_one({"_id": user_id})
        if user:
            profile["user"] = {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "picture": user.get("picture", "")
            }
            
        # Obtener información del instituto asociado
        institute = self.db.institutes.find_one({"_id": profile["institute_id"]})
        if institute:
            profile["institute"] = {
                "name": institute.get("name", ""),
                "status": institute.get("status", "")
            }
            
        return profile
    
    def update_institute_admin_profile(self, user_id_or_email: str, profile_data: Dict) -> bool:
        """
        Actualiza el perfil de administrador de instituto para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador de instituto
            profile_data: Datos del perfil a actualizar
            
        Returns:
            bool: True si se actualizó correctamente, False en caso contrario
        """
        try:
            user_id = self._get_user_id(user_id_or_email)
            if not user_id:
                return False
            
            # Verificar si ya existe un perfil
            profile = self.db.institute_admin_profiles.find_one({"user_id": user_id})
            
            if profile:
                # No permitir actualizar el user_id o institute_id para mantener integridad
                if "user_id" in profile_data:
                    del profile_data["user_id"]
                
                # Actualizar perfil existente
                profile_data["updated_at"] = datetime.now()
                result = self.db.institute_admin_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": profile_data}
                )
                
                return result.modified_count > 0
            else:
                # No se puede actualizar un perfil que no existe
                log_error(f"No existe un perfil de administrador de instituto para: {user_id_or_email}", None, "profiles.services")
                return False
                
        except Exception as e:
            log_error(f"Error al actualizar perfil de administrador de instituto: {str(e)}", e, "profiles.services")
            return False
    
    def delete_institute_admin_profile(self, user_id_or_email: str) -> bool:
        """
        Elimina el perfil de administrador de instituto para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador de instituto
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return False
            
        result = self.db.institute_admin_profiles.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    #
    # MÉTODOS PARA PERFIL DE INSTITUTO
    #
    
    def create_institute_profile(self, institute_id: str, name: str, profile_data: Dict = None) -> Tuple[bool, str]:
        """
        Crea un nuevo perfil para un instituto
        
        IMPORTANTE: Este método crea un perfil para un instituto existente, NO crea el instituto en sí.
        Sigue el mismo patrón que los perfiles de usuario (student_profiles, teacher_profiles, etc.)
        donde los datos básicos están en una colección (institutes) y los datos específicos del perfil
        en otra (institute_profiles).
        
        Args:
            institute_id: ID del instituto
            name: Nombre del instituto
            profile_data: Datos adicionales del perfil a crear (opcional)
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del perfil)
        """
        try:
            # Convertir institute_id a ObjectId
            institute_obj_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
            
            # Verificar si ya existe un perfil
            existing_profile = self.db.institute_profiles.find_one({
                "institute_id": institute_obj_id
            })
            
            if existing_profile:
                return True, str(existing_profile["_id"])  # Retornamos éxito y el ID si ya existe
            
            # Verificar que el instituto exista
            institute = self.db.institutes.find_one({"_id": institute_obj_id})
            if not institute:
                return False, f"No se encontró el instituto con ID: {institute_id}"
            
            # Usar nombre de la colección institutes si no se proporciona
            if not name or name == "Instituto sin nombre":
                name = institute.get("name", "Instituto sin nombre")
            
            # Crear un nuevo perfil con los datos proporcionados
            profile_data = profile_data or {}
            
            # Establecer campos mínimos
            minimal_data = {
                "institute_id": institute_obj_id,
                "name": name,
                "status": institute.get("status", "active"),
                "created_at": institute.get("created_at", datetime.now()),
                "educational_levels": [],
                "number_of_students": 0,
                "number_of_teachers": 0
            }
            
            # Combinar datos mínimos con los proporcionados
            for key, value in minimal_data.items():
                if key not in profile_data:
                    profile_data[key] = value
            
            # Aseguramos que usamos el modelo InstituteProfile y lo guardamos en institute_profiles
            institute_profile = InstituteProfile(**profile_data)
            result = self.db.institute_profiles.insert_one(institute_profile.to_dict())
            
            log_info(f"Perfil de instituto creado para {name} (ID: {institute_id})", "profiles.services")
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al crear perfil de instituto: {str(e)}", e, "profiles.services")
            return False, str(e)
    
    def get_institute_profile(self, institute_id: str) -> Optional[Dict]:
        """
        Obtiene el perfil de un instituto específico.
        
        Args:
            institute_id: ID del instituto
            
        Returns:
            Dict: Información del perfil del instituto si existe, None en caso contrario
        """
        try:
            institute_obj_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
            profile = self.db.institute_profiles.find_one({"institute_id": institute_obj_id})
            
            if not profile:
                # Verificar si existe el instituto pero no tiene perfil
                institute = self.db.institutes.find_one({"_id": institute_obj_id})
                if not institute:
                    return None
                
                # Crear un perfil básico para el instituto
                profile_data = {
                    "institute_id": institute_obj_id,
                    "name": institute.get("name", "Instituto sin nombre"),
                    "status": institute.get("status", "active"),
                    "created_at": institute.get("created_at", datetime.now())
                }
                
                institute_profile = InstituteProfile(**profile_data)
                result = self.db.institute_profiles.insert_one(institute_profile.to_dict())
                
                # Obtener el perfil recién creado
                profile = self.db.institute_profiles.find_one({"_id": result.inserted_id})
                if not profile:
                    return None
            
            # Convertir ObjectId a string para serialización
            profile["_id"] = str(profile["_id"])
            profile["institute_id"] = str(profile["institute_id"])
            
            # Obtener estadísticas adicionales
            try:
                # Contar miembros del instituto
                member_count = self.db.institute_members.count_documents({
                    "institute_id": institute_obj_id
                })
                
                # Contar clases del instituto
                class_count = self.db.classes.count_documents({
                    "institute_id": institute_obj_id
                })
                
                profile["statistics"] = {
                    "total_members": member_count,
                    "total_classes": class_count
                }
            except Exception as stats_e:
                log_error(f"Error al obtener estadísticas del instituto: {str(stats_e)}", stats_e, "profiles.services")
                
            return profile
        except Exception as e:
            log_error(f"Error al obtener perfil de instituto: {str(e)}", e, "profiles.services")
            return None
    
    def update_institute_profile(self, institute_id: str, profile_data: Dict) -> bool:
        """
        Actualiza el perfil de un instituto específico.
        
        Args:
            institute_id: ID del instituto
            profile_data: Datos del perfil a actualizar
            
        Returns:
            bool: True si se actualizó correctamente, False en caso contrario
        """
        try:
            institute_obj_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
            
            # Verificar si ya existe un perfil
            profile = self.db.institute_profiles.find_one({"institute_id": institute_obj_id})
            
            if profile:
                # No permitir actualizar el institute_id para mantener integridad
                if "institute_id" in profile_data:
                    del profile_data["institute_id"]
                
                # Actualizar perfil existente
                profile_data["updated_at"] = datetime.now()
                result = self.db.institute_profiles.update_one(
                    {"institute_id": institute_obj_id},
                    {"$set": profile_data}
                )
                
                return result.modified_count > 0
            else:
                # Si no existe un perfil, intentar crear uno
                if "name" not in profile_data:
                    # Obtener el nombre del instituto de la colección institutes
                    institute = self.db.institutes.find_one({"_id": institute_obj_id})
                    if not institute:
                        return False
                    profile_data["name"] = institute.get("name", "Instituto sin nombre")
                
                profile_data["institute_id"] = institute_obj_id
                institute_profile = InstituteProfile(**profile_data)
                result = self.db.institute_profiles.insert_one(institute_profile.to_dict())
                
                return result.acknowledged
                
        except Exception as e:
            log_error(f"Error al actualizar perfil de instituto: {str(e)}", e, "profiles.services")
            return False
    
    def delete_institute_profile(self, institute_id: str) -> bool:
        """
        Elimina el perfil de un instituto específico.
        
        Args:
            institute_id: ID del instituto
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        try:
            institute_obj_id = ObjectId(institute_id) if isinstance(institute_id, str) else institute_id
            result = self.db.institute_profiles.delete_one({"institute_id": institute_obj_id})
            return result.deleted_count > 0
        except Exception as e:
            log_error(f"Error al eliminar perfil de instituto: {str(e)}", e, "profiles.services")
            return False