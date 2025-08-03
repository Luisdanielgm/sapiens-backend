from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional, Any

class Institute:
    """
    Modelo para representar un instituto educativo.
    Un instituto tiene información básica.
    """
    def __init__(
        self, 
        name: str, 
        address: str, 
        phone: str,
        email: str,
        website: str,
        status: str = "pending",
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.address = address
        self.phone = phone
        self.email = email
        self.website = website
        self.status = status
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "name": self.name,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "status": self.status,
            "created_at": self.created_at
        }

class EducationalProgram:
    """
    Modelo para representar un programa educativo.
    Un programa educativo pertenece a un instituto y tiene detalles como tipo, modalidad y duración.
    """
    def __init__(
        self,
        name: str,
        institute_id: str,
        type: str,
        modality: str,
        description: str,
        duration: Dict[str, Any],
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.institute_id = ObjectId(institute_id)
        self.type = type
        self.modality = modality
        self.description = description
        self.duration = duration
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "name": self.name,
            "institute_id": self.institute_id,
            "type": self.type,
            "modality": self.modality,
            "description": self.description,
            "duration": self.duration,
            "created_at": self.created_at
        }

class Level:
    """
    Modelo para representar un nivel educativo.
    Un nivel pertenece a un programa educativo y tiene un orden.
    """
    def __init__(
        self,
        name: str,
        description: str,
        program_id: str,
        order: int = 1,
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.name = name
        self.description = description
        self.program_id = ObjectId(program_id)
        self.order = order
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "name": self.name,
            "description": self.description,
            "program_id": self.program_id,
            "order": self.order,
            "created_at": self.created_at
        }

class InstituteMember:
    """
    Modelo para representar un miembro de un instituto.
    Un miembro tiene un rol y permisos específicos dentro del instituto.
    """
    def __init__(
        self,
        institute_id: str,
        user_id: str,
        role: str,
        permissions: Optional[Dict[str, Any]] = None,
        workspace_type: str = "INSTITUTE",
        workspace_name: Optional[str] = None,
        class_id: Optional[str] = None,
        joined_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.institute_id = ObjectId(institute_id)
        self.user_id = ObjectId(user_id)
        self.role = role
        self.permissions = permissions or {}
        self.workspace_type = workspace_type
        self.workspace_name = workspace_name
        self.class_id = ObjectId(class_id) if class_id else None
        self.joined_at = joined_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "institute_id": self.institute_id,
            "user_id": self.user_id,
            "role": self.role,
            "permissions": self.permissions,
            "workspace_type": self.workspace_type,
            "workspace_name": self.workspace_name,
            "joined_at": self.joined_at,
        }
        if self.class_id:
            base_dict["class_id"] = self.class_id