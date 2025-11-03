from typing import Tuple, List, Dict, Optional, Union, Any
from bson import ObjectId
from datetime import datetime

import json
import logging

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.cascade_deletion_service import CascadeDeletionService
from .models import (
    AcademicPeriod,
    Section,
    Subject
)

logger = logging.getLogger(__name__)


def _apply_aliases(source: Dict[str, Any], alias_map: Dict[str, str]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in source.items():
        canonical = alias_map.get(key, key)
        if canonical not in normalized or normalized[canonical] is None:
            normalized[canonical] = value
    return normalized


def _parse_iso_datetime(value: Union[str, datetime], field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            if candidate.endswith('Z'):
                candidate = candidate[:-1] + '+00:00'
            try:
                return datetime.fromisoformat(candidate)
            except ValueError as exc:
                raise ValueError(f"El campo '{field_name}' debe tener formato ISO 8601 valido") from exc
    raise ValueError(f"El campo '{field_name}' debe ser una fecha valida")


def _coerce_int(value: Union[str, int], field_name: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"El campo '{field_name}' debe ser numerico") from exc
    raise ValueError(f"El campo '{field_name}' debe ser numerico")


def _ensure_list(value: Union[str, List[Any]], field_name: str) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        cleaned = value.replace('\r', '').strip()
        if not cleaned:
            return []
        if '\n' in cleaned:
            return [item.strip() for item in cleaned.split('\n') if item.strip()]
        return [item.strip() for item in cleaned.split(',') if item.strip()]
    raise ValueError(f"El campo '{field_name}' debe ser una lista")


class PeriodService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="academic_periods")

    def _normalize_period_payload(self, period_data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
        alias_map = {
            'levelId': 'level_id',
            'levelID': 'level_id',
            'startDate': 'start_date',
            'endDate': 'end_date',
            'period_name': 'name',
            'periodName': 'name',
            'periodType': 'type',
            'period_type': 'type',
            'order_index': 'order'
        }
        allowed_fields = {'level_id', 'name', 'type', 'start_date', 'end_date', 'order', 'created_at', '_id'}
        cleaned = _apply_aliases(period_data, alias_map)
        normalized = {k: v for k, v in cleaned.items() if v is not None and k in allowed_fields}

        if not partial:
            required = ['level_id', 'name', 'type', 'start_date', 'end_date', 'order']
            missing = [field for field in required if field not in normalized]
            if missing:
                raise ValueError("Faltan campos requeridos: {0}".format(', '.join(missing)))

        if 'level_id' in normalized:
            normalized['level_id'] = str(normalized['level_id'])
        if 'order' in normalized:
            normalized['order'] = _coerce_int(normalized['order'], 'order')
        for date_field in ('start_date', 'end_date'):
            if date_field in normalized:
                normalized[date_field] = _parse_iso_datetime(normalized[date_field], date_field)

        return normalized

    def create_period(self, period_data: dict) -> Tuple[bool, str]:
        try:
            normalized = self._normalize_period_payload(period_data)
            period = AcademicPeriod(**normalized)
            result = self.collection.insert_one(period.to_dict())
            return True, str(result.inserted_id)
        except ValueError as err:
            return False, str(err)
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
            normalized = self._normalize_period_payload(updates, partial=True)

            if 'level_id' in normalized:
                normalized['level_id'] = ObjectId(normalized['level_id'])

            result = self.collection.update_one(
                {"_id": ObjectId(period_id)},
                {"$set": normalized}
            )

            if result.modified_count > 0:
                return True, "Período académico actualizado correctamente"
            return False, "No se realizaron cambios"
        except ValueError as err:
            return False, str(err)
        except Exception as e:
            return False, str(e)
            
    def delete_period(self, period_id: str, cascade: bool = False) -> Tuple[bool, str]:
        try:
            # Verificar si existen clases asociadas a este período
            classes_with_period = self.db.classes.count_documents({
                "academic_period_id": ObjectId(period_id)
            })
            
            if classes_with_period > 0:
                if not cascade:
                    return False, f"No se puede eliminar el período porque está siendo usado por {classes_with_period} clases"
                
                cascade_service = CascadeDeletionService()
                class_ids = [
                    str(class_doc["_id"])
                    for class_doc in self.db.classes.find({"academic_period_id": ObjectId(period_id)}, {"_id": 1})
                ]

                for class_id in class_ids:
                    cascade_result = cascade_service.delete_with_cascade('classes', class_id)
                    if not cascade_result.get('success', False):
                        return False, f"Error al eliminar clases asociadas al período {period_id}: {cascade_result.get('error', 'desconocido')}"
            
            # Si no hay dependencias, eliminar el período
            result = self.collection.delete_one({"_id": ObjectId(period_id)})
            
            if result.deleted_count > 0:
                return True, "Período académico eliminado correctamente"
            return False, "No se encontró el período académico"
        except Exception as e:
            return False, str(e)

class SectionService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="sections")

    def _normalize_section_payload(self, section_data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
        alias_map = {
            'levelId': 'level_id',
            'levelID': 'level_id',
            'section_code': 'code',
            'sectionCode': 'code',
            'code': 'code',
            'capacity': 'capacity',
            'max_capacity': 'capacity'
        }
        allowed_fields = {'level_id', 'code', 'capacity', 'schedule', 'created_at', '_id'}
        cleaned = _apply_aliases(section_data, alias_map)
        normalized = {k: v for k, v in cleaned.items() if v is not None and k in allowed_fields}

        if not partial:
            required = ['level_id', 'code', 'capacity']
            missing = [field for field in required if field not in normalized]
            if missing:
                raise ValueError("Faltan campos requeridos: {0}".format(', '.join(missing)))

        if 'level_id' in normalized:
            normalized['level_id'] = str(normalized['level_id'])
        if 'capacity' in normalized:
            normalized['capacity'] = _coerce_int(normalized['capacity'], 'capacity')
        if 'schedule' in normalized:
            schedule_value = normalized['schedule']
            if isinstance(schedule_value, str):
                try:
                    normalized['schedule'] = json.loads(schedule_value)
                except json.JSONDecodeError:
                    logger.warning('create_section: schedule recibido no es JSON valido, se ignorara el valor')
                    normalized.pop('schedule')
            elif not isinstance(schedule_value, dict):
                logger.warning('create_section: schedule debe ser un objeto, se ignorara el valor provisto')
                normalized.pop('schedule')

        return normalized

    def create_section(self, section_data: dict) -> Tuple[bool, str]:
        try:
            normalized = self._normalize_section_payload(section_data)

            # Verificar si ya existe una seccion con el mismo codigo
            existing = self.collection.find_one({
                "level_id": ObjectId(normalized["level_id"]),
                "code": normalized["code"]
            })

            if existing:
                return False, "Ya existe una seccion con este codigo en el nivel especificado"

            section = Section(**normalized)
            result = self.collection.insert_one(section.to_dict())
            return True, str(result.inserted_id)
        except ValueError as err:
            return False, str(err)
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
            normalized = self._normalize_section_payload(updates, partial=True)

            if 'level_id' in normalized:
                normalized['level_id'] = ObjectId(normalized['level_id'])

            result = self.collection.update_one(
                {"_id": ObjectId(section_id)},
                {"$set": normalized}
            )

            if result.modified_count > 0:
                return True, "Seccion actualizada correctamente"
            return False, "No se realizaron cambios"
        except ValueError as err:
            return False, str(err)
        except Exception as e:
            return False, str(e)
            
    def delete_section(self, section_id: str, cascade: bool = False) -> Tuple[bool, str]:
        try:
            # Verificar si existen clases asociadas a esta sección
            classes_with_section = self.db.classes.count_documents({
                "section_id": ObjectId(section_id)
            })
            
            if classes_with_section > 0:
                if not cascade:
                    return False, f"No se puede eliminar la sección porque está siendo usada por {classes_with_section} clases"
                
                cascade_service = CascadeDeletionService()
                class_ids = [
                    str(class_doc["_id"])
                    for class_doc in self.db.classes.find({"section_id": ObjectId(section_id)}, {"_id": 1})
                ]

                for class_id in class_ids:
                    cascade_result = cascade_service.delete_with_cascade('classes', class_id)
                    if not cascade_result.get('success', False):
                        return False, f"Error al eliminar clases asociadas a la sección {section_id}: {cascade_result.get('error', 'desconocido')}"
            
            # Si no hay dependencias, eliminar la sección
            result = self.collection.delete_one({"_id": ObjectId(section_id)})
            
            if result.deleted_count > 0:
                return True, "Sección eliminada correctamente"
            return False, "No se encontró la sección"
        except Exception as e:
            return False, str(e)

class SubjectService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="subjects")

    def _normalize_subject_payload(self, subject_data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
        alias_map = {
            'levelId': 'level_id',
            'levelID': 'level_id',
            'subject_name': 'name',
            'nombre': 'name',
            'subject_code': 'code',
            'subjectCode': 'code',
            'code': 'code',
            'creditos': 'credits',
            'credits': 'credits',
            'competencias': 'competencies',
            'competency_list': 'competencies',
            'is_required': 'required'
        }
        allowed_fields = {'level_id', 'name', 'code', 'credits', 'competencies', 'required', 'created_at', '_id'}
        cleaned = _apply_aliases(subject_data, alias_map)
        normalized = {k: v for k, v in cleaned.items() if v is not None and k in allowed_fields}

        if not partial:
            required_fields = ['level_id', 'name', 'code', 'credits', 'competencies']
            missing = [field for field in required_fields if field not in normalized]
            if missing:
                raise ValueError("Faltan campos requeridos: {0}".format(', '.join(missing)))

        if 'level_id' in normalized:
            normalized['level_id'] = str(normalized['level_id'])
        if 'credits' in normalized:
            normalized['credits'] = _coerce_int(normalized['credits'], 'credits')
        if 'competencies' in normalized:
            normalized['competencies'] = _ensure_list(normalized['competencies'], 'competencies')
        if 'required' in normalized and isinstance(normalized['required'], str):
            normalized['required'] = normalized['required'].strip().lower() in {'true', '1', 'yes', 'si'}

        return normalized

    def create_subject(self, subject_data: dict) -> Tuple[bool, str]:
        try:
            normalized = self._normalize_subject_payload(subject_data)
            subject = Subject(**normalized)
            result = self.collection.insert_one(subject.to_dict())
            return True, str(result.inserted_id)
        except ValueError as err:
            return False, str(err)
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
            normalized = self._normalize_subject_payload(updates, partial=True)

            if 'level_id' in normalized:
                normalized['level_id'] = ObjectId(normalized['level_id'])

            result = self.collection.update_one(
                {"_id": ObjectId(subject_id)},
                {"$set": normalized}
            )

            if result.modified_count > 0:
                return True, "Materia actualizada correctamente"
            return False, "No se realizaron cambios"
        except ValueError as err:
            return False, str(err)
        except Exception as e:
            return False, str(e)
            
    def delete_subject(self, subject_id: str, cascade: bool = False) -> Tuple[bool, str]:
        try:
            # Verificar si existen clases asociadas a esta materia
            classes_with_subject = self.db.classes.count_documents({
                "subject_id": ObjectId(subject_id)
            })
            
            if classes_with_subject > 0:
                if not cascade:
                    return False, f"No se puede eliminar la materia porque está siendo usada por {classes_with_subject} clases"
                
                cascade_service = CascadeDeletionService()
                class_ids = [
                    str(class_doc["_id"])
                    for class_doc in self.db.classes.find({"subject_id": ObjectId(subject_id)}, {"_id": 1})
                ]

                for class_id in class_ids:
                    cascade_result = cascade_service.delete_with_cascade('classes', class_id)
                    if not cascade_result.get('success', False):
                        return False, f"Error al eliminar clases asociadas a la materia {subject_id}: {cascade_result.get('error', 'desconocido')}"
            
            # Si no hay dependencias, eliminar la materia
            result = self.collection.delete_one({"_id": ObjectId(subject_id)})
            
            if result.deleted_count > 0:
                return True, "Materia eliminada correctamente"
            return False, "No se encontró la materia"
        except Exception as e:
            return False, str(e)
