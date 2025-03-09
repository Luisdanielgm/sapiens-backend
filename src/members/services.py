from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import ROLES
from src.shared.exceptions import AppException
from src.shared.validators import is_valid_object_id, validate_object_id
from src.shared.standardization import VerificationBaseService, ErrorCodes
from .models import InstituteMember, ClassMember

class MembershipService(VerificationBaseService):
    def __init__(self):
        # Inicializamos con la colección de miembros del instituto por defecto
        super().__init__(collection_name="institute_members")

    # ========== INSTITUTO MEMBERS ==========
    def add_institute_member(self, member_data: dict) -> str:
        """
        Añade un miembro al instituto
        
        Args:
            member_data: Datos del miembro a añadir
            
        Returns:
            str: ID del miembro creado
            
        Raises:
            AppException: Si hay problemas con los datos o el instituto/usuario
        """
        # Validar IDs
        if not is_valid_object_id(member_data.get('institute_id')):
            raise AppException("ID de instituto inválido", ErrorCodes.INVALID_ID)
            
        if not is_valid_object_id(member_data.get('user_id')):
            raise AppException("ID de usuario inválido", ErrorCodes.INVALID_ID)
        
        # Verificar que el instituto existe
        institute = get_db().institutes.find_one(
            {"_id": ObjectId(member_data['institute_id'])}
        )
        if not institute:
            raise AppException("Instituto no encontrado", ErrorCodes.INSTITUTE_NOT_FOUND)

        # Verificar que el usuario no sea ya miembro
        existing_member = self.collection.find_one({
            "institute_id": ObjectId(member_data['institute_id']),
            "user_id": ObjectId(member_data['user_id'])
        })
        if existing_member:
            raise AppException("El usuario ya es miembro del instituto", ErrorCodes.ALREADY_EXISTS)

        # Crear y guardar el nuevo miembro
        member = InstituteMember(**member_data)
        result = self.collection.insert_one(member.to_dict())
        return str(result.inserted_id)

    def get_institute_members(self, institute_id: str, role: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todos los miembros de un instituto, opcionalmente filtrados por rol
        
        Args:
            institute_id: ID del instituto
            role: Rol para filtrar (opcional)
            
        Returns:
            List[Dict]: Lista de miembros
            
        Raises:
            AppException: Si el ID del instituto es inválido
        """
        validate_object_id(institute_id, "ID de instituto")
        
        query = {"institute_id": ObjectId(institute_id)}
        if role:
            query["role"] = role
        
        members = list(self.collection.find(query))
        
        # Unir con información de usuarios para obtener nombres, emails, etc.
        for member in members:
            member["_id"] = str(member["_id"])
            member["institute_id"] = str(member["institute_id"])
            member["user_id"] = str(member["user_id"])
            
            user = get_db().users.find_one({"_id": ObjectId(member["user_id"])})
            if user:
                member["user"] = {
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "picture": user.get("picture", "")
                }
                
        return members

    def update_institute_member(self, member_id: str, update_data: dict) -> None:
        """
        Actualiza la información de un miembro del instituto
        
        Args:
            member_id: ID del miembro a actualizar
            update_data: Datos a actualizar
            
        Raises:
            AppException: Si hay problemas con los datos o el miembro no existe
        """
        # Validar ID
        validate_object_id(member_id)
        
        result = self.collection.update_one(
            {"_id": ObjectId(member_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise AppException("Miembro no encontrado", ErrorCodes.NOT_FOUND)
            
        if result.modified_count == 0 and result.matched_count > 0:
            # El documento existe pero no se realizaron cambios
            # No es un error, pero podemos informarlo
            pass

    def check_institute_member_exists(self, institute_id: str, user_id: str) -> bool:
        """
        Verifica si un usuario es miembro de un instituto
        
        Args:
            institute_id: ID del instituto
            user_id: ID del usuario
            
        Returns:
            bool: True si el usuario es miembro del instituto, False en caso contrario
        """
        try:
            member = self.collection.find_one({
                "institute_id": ObjectId(institute_id),
                "user_id": ObjectId(user_id)
            })
            return member is not None
        except Exception:
            return False

    def remove_institute_member(self, institute_id: str, user_id: str) -> None:
        """
        Elimina un miembro del instituto
        
        Args:
            institute_id: ID del instituto
            user_id: ID del usuario a eliminar
            
        Raises:
            AppException: Si hay problemas con los datos o el miembro no existe
        """
        # Validar IDs
        validate_object_id(institute_id)
        validate_object_id(user_id)
        
        # Verificar primero si existe
        if not self.check_institute_member_exists(institute_id, user_id):
            raise AppException("Miembro no encontrado", ErrorCodes.NOT_FOUND)
        
        result = self.collection.delete_one({
            "institute_id": ObjectId(institute_id),
            "user_id": ObjectId(user_id)
        })

    # ========== CLASS MEMBERS ==========
    def add_class_member(self, member_data: dict) -> Tuple[bool, str]:
        """
        Añade un miembro a una clase
        Verifica que el usuario sea miembro del instituto al que pertenece la clase
        """
        try:
            # Verificar que la clase existe
            class_obj = get_db().classes.find_one(
                {"_id": ObjectId(member_data['class_id'])}
            )
            if not class_obj:
                return False, "Clase no encontrada"

            # Obtener el instituto al que pertenece la clase
            class_institute_id = None
            
            # Buscar información académica relacionada con la clase
            subject = get_db().subjects.find_one({"_id": class_obj.get("subject_id")})
            if subject:
                level = get_db().levels.find_one({"_id": subject.get("level_id")})
                if level:
                    program = get_db().educational_programs.find_one({"_id": level.get("program_id")})
                    if program:
                        class_institute_id = program.get("institute_id")
            
            if not class_institute_id:
                return False, "No se pudo determinar el instituto de la clase"
                
            # Verificar que el usuario sea miembro del instituto
            is_institute_member = self.collection.find_one({
                "institute_id": class_institute_id,
                "user_id": ObjectId(member_data['user_id'])
            })
            
            if not is_institute_member:
                return False, "El usuario debe ser miembro del instituto para unirse a una clase"

            # Verificar que el usuario no sea ya miembro
            existing_member = get_db().class_members.find_one({
                "class_id": ObjectId(member_data['class_id']),
                "user_id": ObjectId(member_data['user_id'])
            })
            if existing_member:
                return False, "El usuario ya es miembro de la clase"

            # Si el rol es profesor, verificar que no haya otro profesor asignado
            if member_data['role'] == 'teacher':
                existing_teacher = get_db().class_members.find_one({
                    "class_id": ObjectId(member_data['class_id']),
                    "role": "teacher"
                })
                if existing_teacher:
                    return False, "La clase ya tiene un profesor asignado"

            member = ClassMember(**member_data)
            result = get_db().class_members.insert_one(member.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_class_members(self, class_id: str, role: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todos los miembros de una clase, opcionalmente filtrados por rol
        """
        try:
            query = {"class_id": ObjectId(class_id)}
            if role:
                query["role"] = role
                
            members = list(get_db().class_members.find(query))
            return members
        except Exception as e:
            print(f"Error al obtener miembros: {str(e)}")
            return []

    def update_class_member(self, member_id: str, update_data: dict) -> Tuple[bool, str]:
        """
        Actualiza la información de un miembro de la clase
        """
        try:
            result = get_db().class_members.update_one(
                {"_id": ObjectId(member_id)},
                {"$set": update_data}
            )
            if result.modified_count == 0:
                return False, "No se encontró el miembro o no se realizaron cambios"
            return True, "Miembro actualizado correctamente"
        except Exception as e:
            return False, str(e)

    def remove_class_member(self, class_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Elimina un miembro de la clase
        """
        try:
            result = get_db().class_members.delete_one({
                "class_id": ObjectId(class_id),
                "user_id": ObjectId(user_id)
            })
            if result.deleted_count == 0:
                return False, "No se encontró el miembro"
            return True, "Miembro eliminado correctamente"
        except Exception as e:
            return False, str(e)

    # ========== UTILIDADES ==========
    def get_user_institutes(self, user_id: str) -> List[Dict]:
        """
        Obtiene todos los institutos de los que un usuario es miembro
        """
        try:
            memberships = list(self.collection.find({"user_id": ObjectId(user_id)}))
            institute_ids = [membership["institute_id"] for membership in memberships]
            
            institutes = list(get_db().institutes.find({"_id": {"$in": institute_ids}}))
            return institutes
        except Exception as e:
            print(f"Error al obtener institutos: {str(e)}")
            return []

    def get_user_classes(self, user_id: str) -> List[Dict]:
        """
        Obtiene todas las clases de las que un usuario es miembro
        """
        try:
            memberships = list(get_db().class_members.find({"user_id": ObjectId(user_id)}))
            class_ids = [membership["class_id"] for membership in memberships]
            
            classes = list(get_db().classes.find({"_id": {"$in": class_ids}}))
            return classes
        except Exception as e:
            print(f"Error al obtener clases: {str(e)}")
            return [] 