from typing import Tuple, List, Dict, Optional, Union
from bson import ObjectId
from flask import g
from pymongo.errors import PyMongoError
from datetime import datetime

from src.shared.database import get_db
from src.shared.constants import STATUS, ROLES
from src.shared.standardization import ErrorCodes, VerificationBaseService
from src.shared.exceptions import AppException
from .models import Class, ClassMember, Subperiod
from src.student_individual_content.models import StudentIndividualContent

class ClassService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="classes")

    def check_section_exists(self, section_id: str) -> bool:
        """
        Verifica si una sección existe
        
        Args:
            section_id: ID de la sección
            
        Returns:
            bool: True si la sección existe, False en caso contrario
        """
        try:
            section = self.db.sections.find_one({"_id": ObjectId(section_id)})
            return section is not None
        except Exception:
            return False

    def check_subject_exists(self, subject_id: str) -> bool:
        """
        Verifica si una materia existe
        
        Args:
            subject_id: ID de la materia
            
        Returns:
            bool: True si la materia existe, False en caso contrario
        """
        try:
            subject = self.db.subjects.find_one({"_id": ObjectId(subject_id)})
            return subject is not None
        except Exception:
            return False

    def check_academic_period_exists(self, academic_period_id: str) -> bool:
        """
        Verifica si un período académico existe
        
        Args:
            academic_period_id: ID del período académico
            
        Returns:
            bool: True si el período académico existe, False en caso contrario
        """
        try:
            academic_period = self.db.academic_periods.find_one({"_id": ObjectId(academic_period_id)})
            return academic_period is not None
        except Exception:
            return False

    def check_level_exists(self, level_id: str) -> bool:
        """
        Verifica si un nivel educativo existe
        
        Args:
            level_id: ID del nivel educativo
            
        Returns:
            bool: True si el nivel educativo existe, False en caso contrario
        """
        try:
            level = self.db.levels.find_one({"_id": ObjectId(level_id)})
            return level is not None
        except Exception:
            return False

    def create_class(self, class_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la sección, materia, período académico y nivel existan
            if not self.check_section_exists(class_data['section_id']):
                return False, "Sección no encontrada"
            
            if not self.check_subject_exists(class_data['subject_id']):
                return False, "Materia no encontrada"
            
            if not self.check_academic_period_exists(class_data['academic_period_id']):
                return False, "Período académico no encontrado"
            
            if not self.check_level_exists(class_data['level_id']):
                return False, "Nivel educativo no encontrado"

            # Crear la clase
            class_instance = Class(**class_data)
            result = self.collection.insert_one(class_instance.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_class_details(self, class_id: str, workspace_info: dict = None) -> Optional[Dict]:
        try:
            # Crear filtro base
            filter_query = {"_id": ObjectId(class_id)}
            
            # Aplicar filtro de workspace si está disponible
            if workspace_info and workspace_info.get('workspace_id'):
                workspace_type = workspace_info.get('workspace_type')

                # Tratar workspace_type ausente como institucional por defecto
                if workspace_type == 'INSTITUTE' or not workspace_type:
                    # Para workspaces de instituto, buscar por workspace_id O por institute_id
                    # (para compatibilidad con clases existentes sin workspace_id)
                    filter_query = {
                        "_id": ObjectId(class_id),
                        "$or": [
                            {"workspace_id": ObjectId(workspace_info['workspace_id'])},
                            {
                                "workspace_id": {"$exists": False},
                                "institute_id": ObjectId(workspace_info.get('institute_id'))
                            }
                        ]
                    }
                else:
                    # Para workspaces individuales, mantener filtro estricto
                    filter_query["workspace_id"] = ObjectId(workspace_info['workspace_id'])
            
            class_data = self.collection.find_one(filter_query)
            if not class_data:
                return None

            # Obtener información relacionada
            subject = self.db.subjects.find_one({"_id": class_data["subject_id"]})
            section = self.db.sections.find_one({"_id": class_data["section_id"]})

            # Agregar información adicional
            class_data["subject"] = subject
            class_data["section"] = section

            # Convertir ObjectIds a strings
            class_data["_id"] = str(class_data["_id"])
            class_data["subject_id"] = str(class_data["subject_id"])
            class_data["section_id"] = str(class_data["section_id"])
            class_data["institute_id"] = str(class_data["institute_id"])
            class_data["academic_period_id"] = str(class_data["academic_period_id"])
            class_data["level_id"] = str(class_data["level_id"])
            
            if subject:
                class_data["subject"]["_id"] = str(subject["_id"])
            if section:
                class_data["section"]["_id"] = str(section["_id"])

            return class_data
        except Exception as e:
            print(f"Error al obtener detalles de la clase: {str(e)}")
            return None

    def update_class(self, class_id: str, updates: dict) -> Tuple[bool, str]:
        """
        Actualiza una clase existente.
        
        Args:
            class_id: ID de la clase a actualizar
            updates: Diccionario con los campos a actualizar
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Verificar que la clase existe
            class_data = self.collection.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False, "Clase no encontrada"
            
            # Validar campos permitidos
            allowed_fields = {'name', 'access_code', 'status', 'settings', 'section_id', 'subject_id', 'academic_period_id'}
            invalid_fields = set(updates.keys()) - allowed_fields
            if invalid_fields:
                return False, f"Campos no permitidos: {', '.join(invalid_fields)}"
            
            # Validar valores
            if 'status' in updates and updates['status'] not in ['active', 'inactive']:
                return False, "Estado no válido. Debe ser 'active' o 'inactive'"
            
            if 'settings' in updates and not isinstance(updates['settings'], dict):
                return False, "El campo 'settings' debe ser un objeto"

            # Validar existencia de entidades relacionadas si se actualizan
            if 'section_id' in updates:
                if not self.check_section_exists(updates['section_id']):
                    return False, "La sección especificada no existe"
                updates['section_id'] = ObjectId(updates['section_id'])

            if 'subject_id' in updates:
                if not self.check_subject_exists(updates['subject_id']):
                    return False, "La materia especificada no existe"
                updates['subject_id'] = ObjectId(updates['subject_id'])

            if 'academic_period_id' in updates:
                if not self.check_academic_period_exists(updates['academic_period_id']):
                    return False, "El período académico especificado no existe"
                updates['academic_period_id'] = ObjectId(updates['academic_period_id'])
            
            # Verificar si hay cambios reales comparando con los valores actuales
            needs_update = False
            for field, new_value in updates.items():
                current_value = class_data.get(field)
                if isinstance(current_value, ObjectId):
                    current_value = str(current_value)
                if isinstance(new_value, ObjectId):
                    new_value = str(new_value)
                if current_value != new_value:
                    needs_update = True
                    break
            
            if not needs_update:
                return True, "No se requirieron cambios, los valores son idénticos"
                
            # Actualizar la clase
            result = self.collection.update_one(
                {"_id": ObjectId(class_id)},
                {"$set": updates}
            )
            
            # Verificar si hubo cambios
            if result.matched_count == 0:
                return False, "Clase no encontrada"
            
            if result.modified_count == 0:
                return False, "No se pudo actualizar la clase"
                
            return True, "Clase actualizada exitosamente"
            
        except Exception as e:
            print(f"Error al actualizar clase: {str(e)}")
            return False, str(e)

    def get_classes_by_level(self, level_id: str, workspace_info: dict = None) -> List[Dict]:
        """
        Obtiene todas las clases de un nivel específico con información detallada
        
        Args:
            level_id: ID del nivel educativo
            
        Returns:
            List[Dict]: Lista de clases con información detallada incluyendo:
                - Nombre de la materia
                - Código de la sección
                - Nombre del período académico
                - Información del horario de la sección
        """
        try:
            # Crear filtro base
            filter_query = {"level_id": ObjectId(level_id)}

            # Aplicar filtro de workspace si está disponible
            if workspace_info and workspace_info.get('workspace_id'):
                workspace_type = workspace_info.get('workspace_type')

                # Tratar workspace_type ausente como institucional por defecto
                if workspace_type == 'INSTITUTE' or not workspace_type:
                    # Para workspaces de instituto, buscar por workspace_id O por institute_id
                    # (para compatibilidad con clases existentes sin workspace_id)
                    filter_query = {
                        "level_id": ObjectId(level_id),
                        "$or": [
                            {"workspace_id": ObjectId(workspace_info['workspace_id'])},
                            {
                                "workspace_id": {"$exists": False},
                                "institute_id": ObjectId(workspace_info.get('institute_id'))
                            }
                        ]
                    }
                else:
                    # Para workspaces individuales, mantener filtro estricto
                    filter_query["workspace_id"] = ObjectId(workspace_info['workspace_id'])
            
            # Obtener todas las clases del nivel
            classes = list(self.collection.find(filter_query))

            # Logging de depuración para entender por qué no hay resultados
            try:
                import logging
                logging.getLogger(__name__).info(
                    f"get_classes_by_level: level_id={level_id}, workspace_info={{'workspace_id': {workspace_info.get('workspace_id') if workspace_info else None}, 'workspace_type': {workspace_info.get('workspace_type') if workspace_info else None}, 'institute_id': {workspace_info.get('institute_id') if workspace_info else None}}}, filter={filter_query}, count={len(classes)}"
                )
            except Exception:
                pass
            result = []
            
            for class_item in classes:
                # Obtener información relacionada
                subject = self.db.subjects.find_one({"_id": ObjectId(class_item["subject_id"])})
                section = self.db.sections.find_one({"_id": ObjectId(class_item["section_id"])})
                academic_period = self.db.academic_periods.find_one({"_id": ObjectId(class_item["academic_period_id"])})
                
                # Convertir ObjectIds a strings
                class_data = {
                    "_id": str(class_item["_id"]),
                    "name": class_item["name"],
                    "subject_id": str(class_item["subject_id"]),
                    "section_id": str(class_item["section_id"]),
                    "institute_id": str(class_item["institute_id"]),
                    "academic_period_id": str(class_item["academic_period_id"]),
                    "level_id": str(class_item["level_id"]),
                    "access_code": class_item.get("access_code"),
                    "status": class_item.get("status", "active"),
                    "settings": class_item.get("settings", {}),
                    "created_by": str(class_item["created_by"]) if "created_by" in class_item else None,
                    "created_at": class_item["created_at"].isoformat() if "created_at" in class_item else None
                }
                
                # Agregar información del subject
                if subject:
                    class_data.update({
                        "subject_name": subject.get("name"),
                        "subject_code": subject.get("code"),
                        "subject_credits": subject.get("credits")
                    })
                    
                # Agregar información de la sección
                if section:
                    class_data.update({
                        "section_code": section.get("code"),
                        "section_capacity": section.get("capacity"),
                        "section_schedule": section.get("schedule", {})
                    })
                
                # Agregar información del período académico
                if academic_period:
                    class_data.update({
                        "period_name": academic_period.get("name"),
                        "period_type": academic_period.get("type"),
                        "period_start_date": academic_period.get("start_date"),
                        "period_end_date": academic_period.get("end_date")
                    })
                
                result.append(class_data)
                
            return result
        except Exception as e:
            print(f"Error al obtener clases del nivel: {str(e)}")
            return []

    def delete_class(self, class_id: str) -> Tuple[bool, str]:
        """
        Elimina una clase si no tiene miembros o subperiodos asociados.
        
        Args:
            class_id: ID de la clase a eliminar
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Validar que la clase existe
            class_data = self.collection.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False, "Clase no encontrada"

            # Verificar si hay miembros asociados
            members_count = self.db.class_members.count_documents({
                "class_id": ObjectId(class_id)
            })
            
            if members_count > 0:
                return False, f"No se puede eliminar la clase porque tiene {members_count} miembros asociados"

            # Verificar si hay subperiodos asociados
            subperiods_count = self.db.subperiods.count_documents({
                "class_id": ObjectId(class_id)
            })
            
            if subperiods_count > 0:
                return False, f"No se puede eliminar la clase porque tiene {subperiods_count} subperiodos asociados"

            # Si no hay dependencias, eliminar la clase
            result = self.collection.delete_one({"_id": ObjectId(class_id)})
            
            if result.deleted_count > 0:
                return True, "Clase eliminada correctamente"
            return False, "No se pudo eliminar la clase"
            
        except Exception as e:
            print(f"Error al eliminar clase: {str(e)}")
            return False, str(e)

class MembershipService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="class_members")

    def add_member(self, class_id: str, user_id: str, role: str, workspace_info: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Agrega un miembro a una clase
        
        Args:
            class_id: ID de la clase
            user_id: ID del usuario
            role: Rol a asignar ('TEACHER' o 'STUDENT')
            workspace_info: Información del workspace actual (opcional, para validaciones futuras)
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje o ID del miembro)
        """
        try:
            # Verificar que la clase existe
            class_data = self.db.classes.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False, "Clase no encontrada"
                
            # Verificar que el usuario existe
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return False, "Usuario no encontrado"
                
            # Verificar que el rol es válido para miembros de clase
            if role not in ["TEACHER", "STUDENT"]:
                return False, "Rol no válido para miembros de clase"
                
            # Verificar si ya es miembro
            existing_member = self.collection.find_one({
                "class_id": ObjectId(class_id),
                "user_id": ObjectId(user_id)
            })
            if existing_member:
                # Si ya existe pero con rol diferente, actualizar
                if existing_member.get("role") != role:
                    self.collection.update_one(
                        {"_id": existing_member["_id"]},
                        {"$set": {"role": role}}
                    )
                    return True, f"Rol de miembro actualizado a {role}"
                return False, "El usuario ya es miembro de esta clase con el mismo rol"
                
            # Crear nueva membresía
            member = ClassMember(
                class_id=ObjectId(class_id),
                user_id=ObjectId(user_id),
                role=role
            )
            result = self.collection.insert_one(member.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_class_members(self, class_id: str, role: str = None) -> List[Dict]:
        try:
            # Crear el filtro base
            filter_query = {"class_id": ObjectId(class_id)}
            
            # Agregar filtro de rol si se proporciona
            if role:
                filter_query["role"] = role
            
            # Obtener los miembros que coinciden con el filtro
            members = list(self.collection.find(filter_query))
            
            # Enriquecer con información del usuario
            for member in members:
                user = self.db.users.find_one({"_id": member["user_id"]})
                if user:
                    member["user"] = {
                        "id": str(user["_id"]),
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "picture": user.get("picture", "")
                    }
                
                # Convertir ObjectIds a strings
                member["_id"] = str(member["_id"])
                member["class_id"] = str(member["class_id"])
                member["user_id"] = str(member["user_id"])
                
            return members
        except Exception as e:
            print(f"Error al obtener miembros de la clase: {str(e)}")
            return []

    def get_classes_by_teacher(self, teacher_id_or_email: str, workspace_type: str = None, workspace_user_id: str = None, class_id: str = None) -> List[Dict]:
        try:
            # Determinar si es email o ID
            if "@" in teacher_id_or_email:
                teacher = self.db.users.find_one({"email": teacher_id_or_email})
                if not teacher:
                    return []
                teacher_id = teacher["_id"]
            else:
                teacher_id = ObjectId(teacher_id_or_email)
                
            # Obtener membresías del profesor
            memberships = list(self.collection.find({
                "user_id": teacher_id,
                "role": "TEACHER"
            }))
            
            # Obtener detalles de cada clase
            class_ids = [m["class_id"] for m in memberships]
            query = {"_id": {"$in": class_ids}}
            
            # Aplicar filtros de workspace si es necesario
            if workspace_type and workspace_user_id:
                from src.workspaces.services import WorkspaceService
                workspace_service = WorkspaceService()
                query = workspace_service.apply_workspace_filters(query, workspace_type, workspace_user_id, class_id)
            
            classes = list(self.db.classes.find(query))
            
            # Procesar resultados
            result = []
            for class_item in classes:
                # Obtener información relacionada
                subject = self.db.subjects.find_one({"_id": class_item["subject_id"]})
                section = self.db.sections.find_one({"_id": class_item["section_id"]})
                
                # Convertir ObjectIds a strings
                class_item["_id"] = str(class_item["_id"])
                class_item["subject_id"] = str(class_item["subject_id"])
                class_item["section_id"] = str(class_item["section_id"])
                class_item["institute_id"] = str(class_item["institute_id"])
                class_item["academic_period_id"] = str(class_item["academic_period_id"])
                class_item["level_id"] = str(class_item["level_id"])
                
                # Agregar información del subject
                if subject:
                    class_item["subject_name"] = subject.get("name", "")
                    
                # Agregar información de la sección
                if section:
                    class_item["section_name"] = section.get("name", "")
                
                result.append(class_item)
                
            return result
        except Exception as e:
            print(f"Error al obtener clases del profesor: {str(e)}")
            return []

    def get_classes_by_student(self, student_id_or_email: str, workspace_type: str = None, workspace_user_id: str = None, class_id: str = None) -> List[Dict]:
        try:
            # Determinar si es email o ID
            if "@" in student_id_or_email:
                student = self.db.users.find_one({"email": student_id_or_email})
                if not student:
                    return []
                student_id = student["_id"]
            else:
                student_id = ObjectId(student_id_or_email)
                
            # Obtener membresías del estudiante
            memberships = list(self.collection.find({
                "user_id": student_id,
                "role": "STUDENT"
            }))
            
            # Obtener detalles de cada clase
            class_ids = [m["class_id"] for m in memberships]
            query = {"_id": {"$in": class_ids}}
            
            # Aplicar filtros de workspace si es necesario
            if workspace_type and workspace_user_id:
                from src.workspaces.services import WorkspaceService
                workspace_service = WorkspaceService()
                query = workspace_service.apply_workspace_filters(query, workspace_type, workspace_user_id, class_id)
            
            classes = list(self.db.classes.find(query))
            
            # Procesar resultados
            result = []
            for class_item in classes:
                # Obtener información relacionada
                subject = self.db.subjects.find_one({"_id": class_item["subject_id"]})
                section = self.db.sections.find_one({"_id": class_item["section_id"]})
                
                # Convertir ObjectIds a strings
                class_item["_id"] = str(class_item["_id"])
                class_item["subject_id"] = str(class_item["subject_id"])
                class_item["section_id"] = str(class_item["section_id"])
                class_item["institute_id"] = str(class_item["institute_id"])
                class_item["academic_period_id"] = str(class_item["academic_period_id"])
                class_item["level_id"] = str(class_item["level_id"])
                
                # Agregar información del subject
                if subject:
                    class_item["subject_name"] = subject.get("name", "")
                    
                # Agregar información de la sección
                if section:
                    class_item["section_name"] = section.get("name", "")
                
                result.append(class_item)
                
            return result
        except Exception as e:
            print(f"Error al obtener clases del estudiante: {str(e)}")
            return []

    def get_class_students(self, class_id: str) -> List[Dict]:
        try:
            # Obtener todos los miembros estudiantes
            members = list(self.collection.find({
                "class_id": ObjectId(class_id),
                "role": "STUDENT"
            }))
            
            # Enriquecer con información del usuario
            students = []
            for member in members:
                user = self.db.users.find_one({"_id": member["user_id"]})
                if user:
                    student = {
                        "id": str(user["_id"]),
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "picture": user.get("picture", ""),
                        "member_id": str(member["_id"]),
                        "joined_at": member.get("joined_at", datetime.now()).isoformat()
                    }
                    
                    # Obtener perfil cognitivo si existe
                    cognitive_profile = self.db.cognitive_profiles.find_one({"user_id": user["_id"]})
                    if cognitive_profile:
                        student["cognitive_profile"] = {
                            "learning_style": cognitive_profile.get("learning_style", None),
                            "intelligence_type": cognitive_profile.get("intelligence_type", None),
                            "personality_type": cognitive_profile.get("personality_type", None)
                        }
                    
                    students.append(student)
                
            return students
        except Exception as e:
            print(f"Error al obtener estudiantes de la clase: {str(e)}")
            return []

    def remove_member(self, class_id: str, member_id: str, workspace_info: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Elimina un miembro de una clase
        
        Args:
            class_id: ID de la clase
            member_id: ID del miembro a eliminar
            workspace_info: Información del workspace actual (opcional)
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Verificar que la clase existe
            class_data = self.db.classes.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False, "Clase no encontrada"
                
            # Verificar que el miembro existe
            member = self.collection.find_one({
                "_id": ObjectId(member_id),
                "class_id": ObjectId(class_id)
            })
            
            if not member:
                return False, "Miembro no encontrado en la clase especificada"
                
            # Eliminar el miembro
            result = self.collection.delete_one({
                "_id": ObjectId(member_id),
                "class_id": ObjectId(class_id)
            })
            
            if result.deleted_count > 0:
                return True, "Miembro eliminado correctamente"
            return False, "No se pudo eliminar el miembro"
        except Exception as e:
            print(f"Error al eliminar miembro: {str(e)}")
            return False, str(e)
    
    def add_member_by_email(self, class_id: str, email: str, role: str, workspace_info: Optional[Dict] = None) -> Tuple[bool, Union[str, Dict]]:
        """
        Agrega un miembro a una clase mediante su email
        
        Args:
            class_id: ID de la clase
            email: Email del usuario
            role: Rol a asignar ('TEACHER' o 'STUDENT')
            workspace_info: Información del workspace actual (opcional, para validaciones futuras)
            
        Returns:
            Tuple[bool, Union[str, Dict]]: (Éxito, Mensaje o datos)
        """
        try:
            # Verificar que la clase existe
            class_data = self.db.classes.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False, "Clase no encontrada"
                
            # Buscar al usuario por email
            user = self.db.users.find_one({"email": email})
            if not user:
                return False, f"No se encontró ningún usuario con el email {email}"
                
            user_id = str(user["_id"])
            
            # Verificar que el rol es válido para miembros de clase
            if role not in ["TEACHER", "STUDENT"]:
                return False, "Rol no válido para miembros de clase"
                
            # Verificar si ya es miembro
            existing_member = self.collection.find_one({
                "class_id": ObjectId(class_id),
                "user_id": ObjectId(user_id)
            })
            
            if existing_member:
                # Si ya existe pero con rol diferente, actualizar
                if existing_member.get("role") != role:
                    self.collection.update_one(
                        {"_id": existing_member["_id"]},
                        {"$set": {"role": role}}
                    )
                    return True, {
                        "id": str(existing_member["_id"]),
                        "message": f"Rol de miembro actualizado a {role}",
                        "user_info": {
                            "id": user_id,
                            "name": user.get("name", ""),
                            "email": email
                        }
                    }
                return False, f"El usuario ya es miembro de esta clase con el rol de {role}"
                
            # Crear nueva membresía
            member = ClassMember(
                class_id=ObjectId(class_id),
                user_id=ObjectId(user_id),
                role=role
            )
            result = self.collection.insert_one(member.to_dict())
            
            return True, {
                "id": str(result.inserted_id),
                "user_info": {
                    "id": user_id,
                    "name": user.get("name", ""),
                    "email": email
                }
            }
        except Exception as e:
            print(f"Error al agregar miembro por email: {str(e)}")
            return False, str(e)

class SubperiodService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="subperiods")

    def create_subperiod(self, subperiod_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la clase existe
            class_data = self.db.classes.find_one({"_id": ObjectId(subperiod_data["class_id"])})
            if not class_data:
                return False, "Clase no encontrada"
                
            subperiod = Subperiod(**subperiod_data)
            result = self.collection.insert_one(subperiod.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_class_subperiods(self, class_id: str) -> List[Dict]:
        try:
            # Obtener todos los subperiodos
            subperiods = list(self.collection.find({
                "class_id": ObjectId(class_id)
            }).sort("start_date", 1))
            
            # Procesar resultados
            for subperiod in subperiods:
                subperiod["_id"] = str(subperiod["_id"])
                subperiod["class_id"] = str(subperiod["class_id"])
                
            return subperiods
        except Exception as e:
            print(f"Error al obtener subperiodos de la clase: {str(e)}")
            return []
    
    def update_subperiod(self, subperiod_id: str, update_data: dict) -> Tuple[bool, str]:
        """
        Actualiza un subperiodo existente.
        
        Args:
            subperiod_id: ID del subperiodo a actualizar
            update_data: Datos a actualizar
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Verificar que el subperiodo existe
            subperiod = self.collection.find_one({"_id": ObjectId(subperiod_id)})
            if not subperiod:
                return False, "Subperiodo no encontrado"
            
            # Eliminar campos no actualizables
            if "_id" in update_data:
                del update_data["_id"]
            if "class_id" in update_data:
                del update_data["class_id"]
            if "created_by" in update_data:
                del update_data["created_by"]
            if "created_at" in update_data:
                del update_data["created_at"]
            
            # Actualizar el subperiodo
            result = self.collection.update_one(
                {"_id": ObjectId(subperiod_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Subperiodo actualizado correctamente"
            return False, "No se realizaron cambios en el subperiodo"
        except Exception as e:
            print(f"Error al actualizar subperiodo: {str(e)}")
            return False, str(e)
    
    def delete_subperiod(self, subperiod_id: str) -> Tuple[bool, str]:
        """
        Elimina un subperiodo existente.
        
        Args:
            subperiod_id: ID del subperiodo a eliminar
            
        Returns:
            Tuple[bool, str]: (Éxito, Mensaje)
        """
        try:
            # Verificar que el subperiodo existe
            subperiod = self.collection.find_one({"_id": ObjectId(subperiod_id)})
            if not subperiod:
                return False, "Subperiodo no encontrado"
            
            # Verificar si hay contenido asociado al subperiodo
            # Esto dependerá de cómo estén estructurados los datos en tu aplicación
            # Por ejemplo, si los contenidos o actividades están vinculados a subperiodos
            # Puedes verificar en las colecciones correspondientes
            
            # Eliminar el subperiodo
            result = self.collection.delete_one({"_id": ObjectId(subperiod_id)})
            
            if result.deleted_count > 0:
                return True, "Subperiodo eliminado correctamente"
            return False, "No se pudo eliminar el subperiodo"
        except Exception as e:
            print(f"Error al eliminar subperiodo: {str(e)}")
            return False, str(e)