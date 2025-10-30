from bson import ObjectId
from datetime import datetime
from typing import Dict, Any, Optional, List

class Class:
    """
    Modelo para representar una clase.
    Una clase está asociada a una materia, sección, período académico y nivel.
    """
    def __init__(
        self,
        institute_id: ObjectId,
        subject_id: ObjectId,
        section_id: ObjectId,
        academic_period_id: ObjectId,
        level_id: ObjectId,
        name: str,
        access_code: str,
        workspace_id: Optional[ObjectId] = None,
        workspace_type: Optional[str] = None,
        schedule: Optional[Any] = None,
        created_by: Optional[ObjectId] = None,
        created_at: Optional[datetime] = None,
        status: str = "active",
        settings: Optional[Dict[str, Any]] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.institute_id = institute_id
        self.workspace_id = workspace_id
        self.workspace_type = workspace_type
        self.subject_id = subject_id
        self.section_id = section_id
        self.academic_period_id = academic_period_id
        self.level_id = level_id
        self.name = name
        self.access_code = access_code
        self.schedule = schedule
        self.created_by = created_by
        self.created_at = created_at or datetime.now()
        self.status = status
        self.settings = settings or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        data = {
            "_id": self._id,
            "institute_id": self.institute_id,
            "workspace_id": self.workspace_id,
            "workspace_type": self.workspace_type,
            "subject_id": self.subject_id,
            "section_id": self.section_id,
            "academic_period_id": self.academic_period_id,
            "level_id": self.level_id,
            "name": self.name,
            "access_code": self.access_code,
            "schedule": self.schedule,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "status": self.status,
            "settings": self.settings
        }
        # Eliminar claves con None para mantener compatibilidad con datos previos
        return {k: v for k, v in data.items() if v is not None}

class ClassMember:
    """
    Modelo para representar un miembro de una clase.
    Un miembro puede ser un profesor o un estudiante.
    """
    def __init__(
        self,
        class_id: ObjectId,
        user_id: ObjectId,
        role: str,
        joined_at: Optional[datetime] = None,
        status: str = "active",
        last_access: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.class_id = class_id
        self.user_id = user_id
        self.role = role
        self.joined_at = joined_at or datetime.now()
        self.status = status
        self.last_access = last_access

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "class_id": self.class_id,
            "user_id": self.user_id,
            "role": self.role,
            "joined_at": self.joined_at,
            "status": self.status,
            "last_access": self.last_access
        }

# La clase ClassContent fue eliminada porque es redundante con StudentIndividualContent
# en el dominio student_individual_content

class Subperiod:
    """
    Modelo para representar un subperíodo dentro de una clase.
    Un subperíodo tiene una fecha de inicio y fin, y puede contener actividades.
    """
    def __init__(
        self,
        class_id: ObjectId,
        name: str,
        start_date: str,
        end_date: str,
        status: str = "active",
        workspace_id: Optional[ObjectId] = None,
        institute_id: Optional[ObjectId] = None,
        workspace_type: Optional[str] = None,
        created_by: Optional[ObjectId] = None,
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.class_id = class_id
        self.workspace_id = workspace_id
        self.institute_id = institute_id
        self.workspace_type = workspace_type
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.status = status
        self.created_by = created_by
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        data = {
            "_id": self._id,
            "class_id": self.class_id,
            "workspace_id": self.workspace_id,
            "institute_id": self.institute_id,
            "workspace_type": self.workspace_type,
            "name": self.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at
        }
        return {k: v for k, v in data.items() if v is not None}