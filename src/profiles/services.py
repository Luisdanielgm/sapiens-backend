from typing import Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.profiles.models import TeacherProfile, StudentProfile, AdminProfile


class ProfileService(VerificationBaseService):
    """
    Servicio para gestionar los perfiles específicos de los diferentes roles de usuario.
    Incluye funcionalidad para crear, actualizar y obtener perfiles de profesores, estudiantes y administradores.
    """
    def __init__(self):
        # Inicializamos con una colección para que BaseService funcione correctamente
        # Pero mantenemos flexibilidad para trabajar con múltiples colecciones
        super().__init__(collection_name="profiles")
    
    def _get_user_id(self, user_id_or_email: str) -> Optional[ObjectId]:
        """
        Obtiene el ID de usuario a partir del ID o email proporcionado.
        
        Args:
            user_id_or_email: ID o email del usuario
            
        Returns:
            ObjectId: ID del usuario si se encuentra, None en caso contrario
        """
        if ObjectId.is_valid(user_id_or_email):
            user = self.db.users.find_one({"_id": ObjectId(user_id_or_email)})
        else:
            user = self.db.users.find_one({"email": user_id_or_email})
        
        return user["_id"] if user else None
    
    def get_teacher_profile(self, user_id_or_email: str) -> Optional[Dict]:
        """
        Obtiene el perfil de profesor para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario profesor
            
        Returns:
            Dict: Información del perfil de profesor si existe, None en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return None
            
        profile = self.db.teacher_profiles.find_one({"user_id": user_id})
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
    
    def update_teacher_profile(self, user_id_or_email: str, profile_data: Dict) -> None:
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
                
                teacher_profile = TeacherProfile(**profile_data)
                self.db.teacher_profiles.insert_one(teacher_profile.to_dict())
        except AppException:
            raise
        except Exception as e:
            raise AppException(f"Error al actualizar perfil de profesor: {str(e)}", AppException.BAD_REQUEST)
    
    def get_student_profile(self, user_id_or_email: str) -> Optional[Dict]:
        """
        Obtiene el perfil de estudiante para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario estudiante
            
        Returns:
            Dict: Información del perfil de estudiante si existe, None en caso contrario
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            return None
            
        profile = self.db.student_profiles.find_one({"user_id": user_id})
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
    
    def update_student_profile(self, user_id_or_email: str, profile_data: Dict) -> None:
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
                result = self.db.student_profiles.update_one(
                    {"user_id": user_id},
                    {"$set": profile_data}
                )
                
                if result.modified_count == 0:
                    raise AppException("No se realizaron cambios al perfil", AppException.BAD_REQUEST)
            else:
                # Crear un nuevo perfil
                profile_data["user_id"] = user_id
                profile_data["created_at"] = datetime.now()
                
                student_profile = StudentProfile(**profile_data)
                self.db.student_profiles.insert_one(student_profile.to_dict())
        except AppException:
            raise
        except Exception as e:
            raise AppException(f"Error al actualizar perfil de estudiante: {str(e)}", AppException.BAD_REQUEST)
    
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
    
    def update_admin_profile(self, user_id_or_email: str, profile_data: Dict) -> None:
        """
        Actualiza el perfil de administrador para un usuario específico.
        
        Args:
            user_id_or_email: ID o email del usuario administrador
            profile_data: Datos del perfil a actualizar
            
        Raises:
            AppException: Si el usuario no existe o si ocurre un error durante la actualización
        """
        user_id = self._get_user_id(user_id_or_email)
        if not user_id:
            raise AppException(f"Usuario no encontrado: {user_id_or_email}", AppException.NOT_FOUND)
            
        # Verificar si ya existe un perfil
        profile = self.db.admin_profiles.find_one({"user_id": user_id})
        
        try:
            if profile:
                # Actualizar perfil existente
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
                
                admin_profile = AdminProfile(**profile_data)
                self.db.admin_profiles.insert_one(admin_profile.to_dict())
        except AppException:
            raise
        except Exception as e:
            raise AppException(f"Error al actualizar perfil de administrador: {str(e)}", AppException.BAD_REQUEST)

    def check_user_exists(self, user_id_or_email: str) -> bool:
        """
        Verifica si un usuario existe basado en su ID o email
        
        Args:
            user_id_or_email: ID o email del usuario
            
        Returns:
            bool: True si el usuario existe, False en caso contrario
        """
        try:
            user_id = self._get_user_id(user_id_or_email)
            return user_id is not None
        except Exception:
            return False 