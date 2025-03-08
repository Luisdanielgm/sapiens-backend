from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime

from src.shared.database import get_db
from src.shared.standardization import BaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import (
    AcademicPeriod,
    Section,
    Subject
)

class PeriodService(BaseService):
    def __init__(self):
        super().__init__(collection_name="academic_periods")
        self.db = get_db()

    def create_period(self, period_data: dict) -> Tuple[bool, str]:
        try:
            period = AcademicPeriod(**period_data)
            result = self.collection.insert_one(period.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_level_periods(self, level_id: str) -> List[Dict]:
        try:
            periods = list(self.collection.find(
                {"level_id": ObjectId(level_id)}
            ).sort("order", 1))

            for period in periods:
                period["_id"] = str(period["_id"])
                period["level_id"] = str(period["level_id"])
                
            return periods
        except Exception as e:
            print(f"Error al obtener períodos académicos: {str(e)}")
            return []
            
    def get_period_by_id(self, period_id: str) -> Optional[Dict]:
        """
        Obtiene un período académico por su ID
        """
        try:
            # Usar el método get_by_id de BaseService
            period = self.get_by_id(period_id)
            if period and "level_id" in period and period["level_id"]:
                period["level_id"] = str(period["level_id"])
            return period
        except AppException as e:
            print(f"Error al obtener período académico: {str(e)}")
            return None
            
    def update_period(self, period_id: str, updates: dict) -> Tuple[bool, str]:
        try:
            # Convertir level_id a ObjectId si existe en las actualizaciones
            if 'level_id' in updates:
                updates['level_id'] = ObjectId(updates['level_id'])
                
            result = self.collection.update_one(
                {"_id": ObjectId(period_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Período académico actualizado correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)
            
    def delete_period(self, period_id: str) -> Tuple[bool, str]:
        try:
            # Verificar si existen clases asociadas a este período
            classes_with_period = self.db.classes.count_documents({
                "academic_period_id": ObjectId(period_id)
            })
            
            if classes_with_period > 0:
                return False, f"No se puede eliminar el período porque está siendo usado por {classes_with_period} clases"
            
            # Si no hay dependencias, eliminar el período
            result = self.collection.delete_one({"_id": ObjectId(period_id)})
            
            if result.deleted_count > 0:
                return True, "Período académico eliminado correctamente"
            return False, "No se encontró el período académico"
        except Exception as e:
            return False, str(e)

class SectionService(BaseService):
    def __init__(self):
        super().__init__(collection_name="sections")
        self.db = get_db()
        
    def create_section(self, section_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar si ya existe una sección con el mismo código
            existing = self.collection.find_one({
                "level_id": ObjectId(section_data["level_id"]),
                "code": section_data["code"]
            })
            
            if existing:
                return False, "Ya existe una sección con este código en el nivel especificado"
                
            section = Section(**section_data)
            result = self.collection.insert_one(section.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
            
    def get_level_sections(self, level_id: str) -> List[Dict]:
        try:
            sections = list(self.collection.find({"level_id": ObjectId(level_id)}))
            
            for section in sections:
                section["_id"] = str(section["_id"])
                section["level_id"] = str(section["level_id"])
                
            return sections
        except Exception as e:
            print(f"Error al obtener secciones: {str(e)}")
            return []
            
    def get_section_by_id(self, section_id: str) -> Optional[Dict]:
        try:
            section = self.collection.find_one({"_id": ObjectId(section_id)})
            if section:
                section["_id"] = str(section["_id"])
                section["level_id"] = str(section["level_id"])
            return section
        except Exception as e:
            print(f"Error al obtener sección: {str(e)}")
            return None
            
    def update_section(self, section_id: str, updates: dict) -> Tuple[bool, str]:
        try:
            # Convertir level_id a ObjectId si existe en las actualizaciones
            if 'level_id' in updates:
                updates['level_id'] = ObjectId(updates['level_id'])
                
            result = self.collection.update_one(
                {"_id": ObjectId(section_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Sección actualizada correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)
            
    def delete_section(self, section_id: str) -> Tuple[bool, str]:
        try:
            # Verificar si existen clases asociadas a esta sección
            classes_with_section = self.db.classes.count_documents({
                "section_id": ObjectId(section_id)
            })
            
            if classes_with_section > 0:
                return False, f"No se puede eliminar la sección porque está siendo usada por {classes_with_section} clases"
            
            # Si no hay dependencias, eliminar la sección
            result = self.collection.delete_one({"_id": ObjectId(section_id)})
            
            if result.deleted_count > 0:
                return True, "Sección eliminada correctamente"
            return False, "No se encontró la sección"
        except Exception as e:
            return False, str(e)

class SubjectService(BaseService):
    def __init__(self):
        super().__init__(collection_name="subjects")
        self.db = get_db()
        
    def create_subject(self, subject_data: dict) -> Tuple[bool, str]:
        try:
            subject = Subject(**subject_data)
            result = self.collection.insert_one(subject.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
            
    def get_level_subjects(self, level_id: str) -> List[Dict]:
        try:
            subjects = list(self.collection.find({"level_id": ObjectId(level_id)}))
            
            for subject in subjects:
                subject["_id"] = str(subject["_id"])
                subject["level_id"] = str(subject["level_id"])
                
            return subjects
        except Exception as e:
            print(f"Error al obtener materias: {str(e)}")
            return []
            
    def get_subject_details(self, subject_id: str) -> Optional[Dict]:
        try:
            subject = self.collection.find_one({"_id": ObjectId(subject_id)})
            
            if not subject:
                return None
                
            # Convertir IDs de ObjectId a string
            subject["_id"] = str(subject["_id"])
            subject["level_id"] = str(subject["level_id"])
            
            # Obtener nivel asociado
            level = self.db.levels.find_one({"_id": ObjectId(subject["level_id"])})
            if level:
                subject["level"] = {
                    "id": str(level["_id"]),
                    "name": level.get("name", ""),
                    "code": level.get("code", "")
                }
                
            return subject
        except Exception as e:
            print(f"Error al obtener detalles de la materia: {str(e)}")
            return None
            
    def update_subject(self, subject_id: str, updates: dict) -> Tuple[bool, str]:
        try:
            # Convertir level_id a ObjectId si existe en las actualizaciones
            if 'level_id' in updates:
                updates['level_id'] = ObjectId(updates['level_id'])
                
            result = self.collection.update_one(
                {"_id": ObjectId(subject_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Materia actualizada correctamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)
            
    def delete_subject(self, subject_id: str) -> Tuple[bool, str]:
        try:
            # Verificar si existen clases asociadas a esta materia
            classes_with_subject = self.db.classes.count_documents({
                "subject_id": ObjectId(subject_id)
            })
            
            if classes_with_subject > 0:
                return False, f"No se puede eliminar la materia porque está siendo usada por {classes_with_subject} clases"
            
            # Si no hay dependencias, eliminar la materia
            result = self.collection.delete_one({"_id": ObjectId(subject_id)})
            
            if result.deleted_count > 0:
                return True, "Materia eliminada correctamente"
            return False, "No se encontró la materia"
        except Exception as e:
            return False, str(e)