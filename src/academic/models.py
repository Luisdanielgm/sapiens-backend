from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional, Any

class AcademicPeriod:
    """
    Modelo para representar un período académico.
    Un período académico pertenece a un nivel y tiene un tipo, fechas de inicio y fin, y un orden.
    """
    def __init__(
        self,
        level_id: str,
        name: str,
        type: str,
        start_date: datetime,
        end_date: datetime,
        order: int,
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.level_id = ObjectId(level_id)
        self.name = name
        self.type = type
        self.start_date = start_date
        self.end_date = end_date
        self.order = order
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "level_id": self.level_id,
            "name": self.name,
            "type": self.type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "order": self.order,
            "created_at": self.created_at
        }
    
class Section:
    """
    Modelo para representar una sección.
    Una sección pertenece a un nivel, tiene un código y capacidad máxima de estudiantes.
    """
    def __init__(
        self,
        level_id: str,
        code: str,
        capacity: int,
        schedule: Optional[Dict] = None,
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.level_id = ObjectId(level_id)
        self.code = code
        self.capacity = capacity
        self.schedule = schedule or {}
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "level_id": self.level_id,
            "code": self.code,
            "capacity": self.capacity,
            "schedule": self.schedule,
            "created_at": self.created_at
        }

class Subject:
    """
    Modelo para representar una materia.
    Una materia pertenece a un nivel, tiene un código, créditos y competencias.
    """
    def __init__(
        self,
        level_id: str,
        name: str,
        code: str,
        credits: int,
        competencies: List[str],
        required: bool = True,
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.level_id = ObjectId(level_id)
        self.name = name
        self.code = code
        self.credits = credits
        self.competencies = competencies
        self.required = required
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        return {
            "_id": self._id,
            "level_id": self.level_id,
            "name": self.name,
            "code": self.code,
            "credits": self.credits,
            "competencies": self.competencies,
            "required": self.required,
            "created_at": self.created_at
        }