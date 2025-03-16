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

    def get_class_details(self, class_id: str) -> Optional[Dict]:
        try:
            class_data = self.collection.find_one({"_id": ObjectId(class_id)})
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
        try:
            # Verificar que la clase existe
            class_data = self.collection.find_one({"_id": ObjectId(class_id)})
            if not class_data:
                return False, "Clase no encontrada"
                
            # Actualizar la clase
            result = self.collection.update_one(
                {"_id": ObjectId(class_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                return True, "Clase actualizada exitosamente"
            return False, "No se realizaron cambios"
        except Exception as e:
            return False, str(e)

    def get_classes_by_level(self, level_id: str) -> List[Dict]:
        """
        Obtiene todas las clases de un nivel específico
        
        Args:
            level_id: ID del nivel educativo
            
        Returns:
            List[Dict]: Lista de clases con información detallada
        """
        try:
            # Obtener todas las clases del nivel
            classes = list(self.collection.find({"level_id": ObjectId(level_id)}))
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
            print(f"Error al obtener clases del nivel: {str(e)}")
            return []

class MembershipService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="classroom_members")

    def add_member(self, class_id: str, user_id: str, role: str) -> Tuple[bool, str]:
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
            if role not in ["teacher", "student"]:
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

    def get_class_members(self, class_id: str) -> List[Dict]:
        try:
            # Obtener todos los miembros
            members = list(self.collection.find({
                "class_id": ObjectId(class_id)
            }))
            
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

    def get_classes_by_teacher(self, teacher_id_or_email: str) -> List[Dict]:
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
                "role": "teacher"
            }))
            
            # Obtener detalles de cada clase
            class_ids = [m["class_id"] for m in memberships]
            classes = list(self.db.classes.find({
                "_id": {"$in": class_ids}
            }))
            
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

    def get_classes_by_student(self, student_id_or_email: str) -> List[Dict]:
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
                "role": "student"
            }))
            
            # Obtener detalles de cada clase
            class_ids = [m["class_id"] for m in memberships]
            classes = list(self.db.classes.find({
                "_id": {"$in": class_ids}
            }))
            
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
                "role": "student"
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