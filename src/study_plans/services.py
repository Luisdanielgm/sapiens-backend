from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime
import json

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
import logging
from src.shared.validators import validate_object_id
from .models import (
    StudyPlanPerSubject,
    StudyPlanAssignment,
    Module,
    Topic,
    Evaluation,
    EvaluationResult
)

class StudyPlanService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plans_per_subject")

    def create_study_plan(self, plan_data: dict) -> str:
        """
        Crea un nuevo plan de estudios.
        
        Args:
            plan_data: Datos del plan de estudios
            
        Returns:
            ID del plan de estudios creado
            
        Raises:
            AppException: Si ocurre un error durante la creación
        """
        try:
            # Primero obtener el ID del usuario usando el email
            user = get_db().users.find_one({"email": plan_data['author_id']})
            if not user:
                raise AppException("Usuario no encontrado", AppException.NOT_FOUND)
            
            # Reemplazar el email por el ID del usuario
            plan_data['author_id'] = str(user['_id'])
            
            study_plan = StudyPlanPerSubject(**plan_data)
            result = self.collection.insert_one(study_plan.to_dict())
            return str(result.inserted_id)
        except AppException:
            # Re-lanzar excepciones AppException
            raise
        except Exception as e:
            raise AppException(f"Error al crear plan de estudios: {str(e)}", AppException.BAD_REQUEST)

    def update_study_plan(self, plan_id: str, update_data: dict) -> None:
        """
        Actualiza un plan de estudios existente.
        
        Args:
            plan_id: ID del plan de estudios a actualizar
            update_data: Datos a actualizar
            
        Raises:
            AppException: Si ocurre un error durante la actualización
        """
        try:
            # Verificar que el plan existe
            plan = self.collection.find_one({"_id": ObjectId(plan_id)})
            if not plan:
                raise AppException("Plan de estudios no encontrado", AppException.NOT_FOUND)
            
            # No permitir actualizar planes aprobados
            if plan.get("status") == "approved" and "status" not in update_data:
                raise AppException("No se puede modificar un plan aprobado", AppException.FORBIDDEN)
            
            result = self.collection.update_one(
                {"_id": ObjectId(plan_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                raise AppException("No se realizaron cambios", AppException.BAD_REQUEST)
        except AppException:
            # Re-lanzar excepciones AppException
            raise
        except Exception as e:
            raise AppException(f"Error al actualizar plan: {str(e)}", AppException.BAD_REQUEST)

    def delete_study_plan(self, plan_id: str) -> None:
        """
        Elimina un plan de estudios y todos sus componentes asociados.
        
        Args:
            plan_id: ID del plan de estudios a eliminar
            
        Raises:
            AppException: Si el plan no existe, si tiene asignaciones activas o si
                         ocurre un error durante la eliminación
        """
        # Validar el ID de forma estandarizada
        validate_object_id(plan_id)
        
        # Verificar si hay asignaciones activas
        assignments = get_db().study_plan_assignments.find_one({
            "study_plan_id": ObjectId(plan_id),
            "is_active": True
        })
        
        if assignments:
            raise AppException("No se puede eliminar un plan con asignaciones activas", AppException.FORBIDDEN)
        
        try:
            # Obtener todos los módulos del plan
            modules = list(get_db().modules.find({"study_plan_id": ObjectId(plan_id)}))
            module_ids = [module["_id"] for module in modules]
            
            # Inicializar contadores para el resumen
            total_modules_deleted = 0
            total_topics_deleted = 0
            total_evaluations_deleted = 0
            
            # 1. Eliminar todos los temas asociados a los módulos
            if module_ids:
                topics_result = get_db().topics.delete_many({"module_id": {"$in": module_ids}})
                total_topics_deleted = topics_result.deleted_count
                
                # 2. Eliminar todas las evaluaciones asociadas a los módulos
                evaluations_result = get_db().evaluations.delete_many({"module_id": {"$in": module_ids}})
                total_evaluations_deleted = evaluations_result.deleted_count
                
                # 3. Eliminar los módulos
                modules_result = get_db().modules.delete_many({"_id": {"$in": module_ids}})
                total_modules_deleted = modules_result.deleted_count
            
            # 4. Eliminar el plan en sí
            plan_result = self.collection.delete_one({"_id": ObjectId(plan_id)})
            
            if plan_result.deleted_count == 0:
                raise AppException("Plan de estudios no encontrado", AppException.NOT_FOUND)
            
        except AppException:
            raise
        except Exception as e:
            raise AppException(f"Error al eliminar plan de estudios: {str(e)}", AppException.BAD_REQUEST)

    def list_study_plans(self) -> List[Dict]:
        try:
            plans = list(self.collection.find())
            # Convertir ObjectId a string
            for plan in plans:
                plan["_id"] = str(plan["_id"])
                # Asegurarnos de que author_id también se convierta a string si es ObjectId
                if "author_id" in plan and isinstance(plan["author_id"], ObjectId):
                    plan["author_id"] = str(plan["author_id"])
            
            return plans
        except Exception as e:
            logging.error(f"Error al listar planes: {str(e)}")
            return []

    def approve_study_plan(self, plan_id: str) -> bool:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(plan_id)},
                {
                    "$set": {
                        "status": "approved",
                        "approval_date": datetime.now()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logging.error(f"Error al aprobar plan: {str(e)}")
            return False

    def get_study_plan(self, plan_id: str) -> Optional[Dict]:
        try:
            plan = self.collection.find_one({"_id": ObjectId(plan_id)})
            if not plan:
                return None

            # Convertir _id a string para que sea JSON serializable
            plan["_id"] = str(plan["_id"])
            
            # Obtener módulos asociados
            modules = list(get_db().modules.find({"study_plan_id": ObjectId(plan_id)}))
            
            # Para cada módulo, obtener sus temas y evaluaciones
            for module in modules:
                # Convertir ObjectId a string
                module["_id"] = str(module["_id"])
                module["study_plan_id"] = str(module["study_plan_id"])
                
                # Obtener topics y convertir sus ObjectId
                topics = list(get_db().topics.find({"module_id": ObjectId(module["_id"])}))
                for topic in topics:
                    topic["_id"] = str(topic["_id"])
                    topic["module_id"] = str(topic["module_id"])
                
                module["topics"] = topics
                
                # Obtener evaluaciones y convertir sus ObjectId
                evaluations = list(get_db().evaluations.find({"module_id": ObjectId(module["_id"])}))
                for evaluation in evaluations:
                    evaluation["_id"] = str(evaluation["_id"])
                    evaluation["module_id"] = str(evaluation["module_id"])
                
                module["evaluations"] = evaluations

            plan["modules"] = modules
            return plan
        except Exception as e:
            logging.error(f"Error al obtener plan de estudio: {str(e)}")
            return None

class StudyPlanAssignmentService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plan_assignments")

    def check_class_exists(self, class_id: str) -> bool:
        """
        Verifica si una clase existe
        
        Args:
            class_id: ID de la clase
            
        Returns:
            bool: True si la clase existe, False en caso contrario
        """
        try:
            class_doc = get_db().classes.find_one({"_id": ObjectId(class_id)})
            return class_doc is not None
        except Exception:
            return False
            
    def check_study_plan_exists(self, plan_id: str) -> bool:
        """
        Verifica si un plan de estudios existe
        
        Args:
            plan_id: ID del plan de estudios
            
        Returns:
            bool: True si el plan existe, False en caso contrario
        """
        try:
            plan = get_db().study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
            return plan is not None
        except Exception:
            return False
            
    def check_subperiod_exists(self, subperiod_id: str) -> bool:
        """
        Verifica si un subperiodo existe
        
        Args:
            subperiod_id: ID del subperiodo
            
        Returns:
            bool: True si el subperiodo existe, False en caso contrario
        """
        try:
            subperiod = get_db().subperiods.find_one({"_id": ObjectId(subperiod_id)})
            return subperiod is not None
        except Exception:
            return False
    
    def assign_plan_to_class(self, assignment_data: dict) -> str:
        """
        Asigna un plan de estudios a una clase durante un subperiodo específico
        
        Args:
            assignment_data: Datos de la asignación
            
        Returns:
            str: ID de la asignación creada
            
        Raises:
            AppException: Si hay errores en los datos o restricciones de negocio
        """
        try:
            # Convertir IDs a ObjectId
            study_plan_id = ObjectId(assignment_data['study_plan_id'])
            class_id = ObjectId(assignment_data['class_id'])
            subperiod_id = ObjectId(assignment_data['subperiod_id'])
            assigned_by = ObjectId(assignment_data['assigned_by'])
                
            # Verificar que la clase existe
            if not self.check_class_exists(assignment_data['class_id']):
                raise AppException("La clase no existe", AppException.NOT_FOUND)
                
            # Verificar que el plan existe
            if not self.check_study_plan_exists(assignment_data['study_plan_id']):
                raise AppException("El plan de estudios no existe", AppException.NOT_FOUND)
                
            # Verificar que el subperiodo existe
            if not self.check_subperiod_exists(assignment_data['subperiod_id']):
                raise AppException("El subperiodo no existe", AppException.NOT_FOUND)
                
            # Verificar si ya existe una asignación activa para esta clase y subperiodo
            existing_assignment = self.collection.find_one({
                "class_id": class_id,
                "subperiod_id": subperiod_id,
                "is_active": True
            })
            
            if existing_assignment:
                raise AppException("Ya existe un plan asignado para esta clase en este subperiodo", AppException.CONFLICT)
                
            # Crear la asignación
            assignment = StudyPlanAssignment(
                study_plan_id=study_plan_id,
                class_id=class_id,
                subperiod_id=subperiod_id,
                assigned_by=assigned_by,
                is_active=True
            )
            
            result = self.collection.insert_one(assignment.to_dict())
            return str(result.inserted_id)
            
        except AppException:
            raise
        except Exception as e:
            raise AppException(f"Error al asignar plan: {str(e)}", AppException.BAD_REQUEST)
            
    def update_assignment(self, assignment_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(assignment_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Asignación actualizada"
            return False, "No se pudo actualizar la asignación"
        except Exception as e:
            return False, str(e)
            
    def get_assignment(self, assignment_id: str) -> Optional[Dict]:
        try:
            assignment = self.collection.find_one({
                "_id": ObjectId(assignment_id)
            })
            
            if not assignment:
                return None
                
            # Convertir ObjectIds a strings
            assignment['_id'] = str(assignment['_id'])
            assignment['study_plan_id'] = str(assignment['study_plan_id'])
            assignment['class_id'] = str(assignment['class_id'])
            assignment['subperiod_id'] = str(assignment['subperiod_id'])
            
            return assignment
        except Exception:
            return None
            
    def list_assignments(self, filters: Dict = None) -> List[Dict]:
        try:
            query = {}
            
            if filters:
                for key, value in filters.items():
                    if key in ['class_id', 'subperiod_id', 'study_plan_id'] and value:
                        query[key] = ObjectId(value)
            
            assignments = list(self.collection.find(query))
            
            # Convertir ObjectIds a strings
            for assignment in assignments:
                assignment['_id'] = str(assignment['_id'])
                assignment['study_plan_id'] = str(assignment['study_plan_id'])
                assignment['class_id'] = str(assignment['class_id'])
                assignment['subperiod_id'] = str(assignment['subperiod_id'])
                
            return assignments
        except Exception:
            return []

    def remove_plan_assignment(self, assignment_id: str) -> None:
        """
        Desactiva una asignación de plan de estudios.
        
        Args:
            assignment_id: ID de la asignación a desactivar
            
        Raises:
            AppException: Si la asignación no existe o si ocurre un error
        """
        try:
            # Validar ID
            validate_object_id(assignment_id)
                
            # Verificar que la asignación existe
            assignment = self.collection.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                raise AppException("Asignación no encontrada", AppException.NOT_FOUND)
                
            # Desactivar la asignación (mejor que eliminarla para mantener historial)
            result = self.collection.update_one(
                {"_id": ObjectId(assignment_id)},
                {"$set": {"is_active": False, "removed_at": datetime.now()}}
            )
            
            if result.modified_count == 0:
                raise AppException("No se pudo desactivar la asignación", AppException.BAD_REQUEST)
                
        except AppException:
            raise
        except Exception as e:
            raise AppException(f"Error al remover asignación: {str(e)}", AppException.BAD_REQUEST)

class ModuleService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plan_modules")

    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que existe el plan de estudio
            study_plan_id = module_data.get('study_plan_id')
            study_plan = get_db().study_plans_per_subject.find_one({"_id": ObjectId(study_plan_id)})
            if not study_plan:
                return False, "Plan de estudio no encontrado"
            
            # Crear el módulo
            module_data['study_plan_id'] = ObjectId(study_plan_id)
            module_data['created_at'] = datetime.now()
            module_data['updated_at'] = datetime.now()
            
            module = Module(**module_data)
            result = self.collection.insert_one(module.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
    
    def update_module(self, module_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el módulo existe
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Actualizar timestamp
            update_data['updated_at'] = datetime.now()
            
            # Actualizar el módulo
            result = self.collection.update_one(
                {"_id": ObjectId(module_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Módulo actualizado exitosamente"
            return False, "No se pudo actualizar el módulo"
        except Exception as e:
            return False, str(e)
    
    def delete_module(self, module_id: str) -> Tuple[bool, str]:
        try:
            # Verificar que el módulo existe
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Eliminar los temas asociados
            topic_service = TopicService()
            topics = topic_service.get_module_topics(module_id)
            for topic in topics:
                topic_service.delete_topic(topic['_id'])
            
            # Eliminar el módulo
            result = self.collection.delete_one({"_id": ObjectId(module_id)})
            
            if result.deleted_count > 0:
                return True, "Módulo eliminado exitosamente"
            return False, "No se pudo eliminar el módulo"
        except Exception as e:
            return False, str(e)
    
    def get_module(self, module_id: str) -> Optional[Dict]:
        try:
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return None
            
            # Convertir ObjectId a string
            module['_id'] = str(module['_id'])
            module['study_plan_id'] = str(module['study_plan_id'])
            
            # Obtener temas del módulo
            topic_service = TopicService()
            module['topics'] = topic_service.get_module_topics(module_id)
            
            return module
        except Exception as e:
            return None

class TopicService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plan_topics")

    def create_topic(self, topic_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que existe el módulo
            module_id = topic_data.get('module_id')
            module = get_db().study_plan_modules.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Crear el tema
            topic_data['module_id'] = ObjectId(module_id)
            topic_data['created_at'] = datetime.now()
            topic_data['updated_at'] = datetime.now()
            
            topic = Topic(**topic_data)
            result = self.collection.insert_one(topic.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
    
    def update_topic(self, topic_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el tema existe
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, "Tema no encontrado"
            
            # Actualizar timestamp
            update_data['updated_at'] = datetime.now()
            
            # Actualizar el tema
            result = self.collection.update_one(
                {"_id": ObjectId(topic_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Tema actualizado exitosamente"
            return False, "No se pudo actualizar el tema"
        except Exception as e:
            return False, str(e)
    
    def delete_topic(self, topic_id: str) -> Tuple[bool, str]:
        try:
            # Verificar que el tema existe
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, "Tema no encontrado"
            
            # Eliminar el tema
            result = self.collection.delete_one({"_id": ObjectId(topic_id)})
            
            if result.deleted_count > 0:
                return True, "Tema eliminado exitosamente"
            return False, "No se pudo eliminar el tema"
        except Exception as e:
            return False, str(e)
    
    def get_topic(self, topic_id: str) -> Optional[Dict]:
        try:
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return None
            
            # Convertir ObjectId a string
            topic['_id'] = str(topic['_id'])
            topic['module_id'] = str(topic['module_id'])
            
            return topic
        except Exception as e:
            return None
    
    def get_module_topics(self, module_id: str) -> List[Dict]:
        try:
            topics = list(self.collection.find({"module_id": ObjectId(module_id)}))
            
            # Convertir ObjectId a string en cada tema
            for topic in topics:
                topic['_id'] = str(topic['_id'])
                topic['module_id'] = str(topic['module_id'])
            
            return topics
        except Exception as e:
            return []
    
    def update_theory_content(self, topic_id: str, theory_content: str) -> Tuple[bool, str]:
        try:
            # Actualizar el contenido teórico
            result = self.collection.update_one(
                {"_id": ObjectId(topic_id)},
                {
                    "$set": {
                        "theory_content": theory_content,
                        "updated_at": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                return True, "Contenido teórico actualizado exitosamente"
            return False, "No se pudo actualizar el contenido teórico"
        except Exception as e:
            return False, str(e)
    
    def get_theory_content(self, topic_id: str) -> Optional[Dict]:
        try:
            # Obtener solo el contenido teórico
            topic = self.collection.find_one(
                {"_id": ObjectId(topic_id)},
                {"theory_content": 1}
            )
            
            if not topic:
                return None
            
            return {"topic_id": str(topic["_id"]), "theory_content": topic.get("theory_content", "")}
        except Exception as e:
            return None
    
    def delete_theory_content(self, topic_id: str) -> Tuple[bool, str]:
        try:
            # Eliminar el contenido teórico
            result = self.collection.update_one(
                {"_id": ObjectId(topic_id)},
                {
                    "$unset": {"theory_content": ""},
                    "$set": {"updated_at": datetime.now()}
                }
            )
            
            if result.modified_count > 0:
                return True, "Contenido teórico eliminado exitosamente"
            return False, "No se pudo eliminar el contenido teórico"
        except Exception as e:
            return False, str(e)

class EvaluationService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plan_evaluations")

    def create_evaluation(self, evaluation_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que existe el módulo
            module_id = evaluation_data.get('module_id')
            module = get_db().study_plan_modules.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Crear la evaluación
            evaluation_data['module_id'] = ObjectId(module_id)
            evaluation_data['created_at'] = datetime.now()
            evaluation_data['updated_at'] = datetime.now()
            
            evaluation = Evaluation(**evaluation_data)
            result = self.collection.insert_one(evaluation.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
    
    def update_evaluation(self, evaluation_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la evaluación existe
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return False, "Evaluación no encontrada"
            
            # Actualizar timestamp
            update_data['updated_at'] = datetime.now()
            
            # Actualizar la evaluación
            result = self.collection.update_one(
                {"_id": ObjectId(evaluation_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Evaluación actualizada exitosamente"
            return False, "No se pudo actualizar la evaluación"
        except Exception as e:
            return False, str(e)
    
    def delete_evaluation(self, evaluation_id: str) -> Tuple[bool, str]:
        try:
            # Verificar que la evaluación existe
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return False, "Evaluación no encontrada"
            
            # Eliminar resultados de la evaluación
            get_db().evaluation_results.delete_many({"evaluation_id": ObjectId(evaluation_id)})
            
            # Eliminar la evaluación
            result = self.collection.delete_one({"_id": ObjectId(evaluation_id)})
            
            if result.deleted_count > 0:
                return True, "Evaluación eliminada exitosamente"
            return False, "No se pudo eliminar la evaluación"
        except Exception as e:
            return False, str(e)
    
    def get_evaluation(self, evaluation_id: str) -> Optional[Dict]:
        try:
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return None
            
            # Convertir ObjectId a string
            evaluation['_id'] = str(evaluation['_id'])
            evaluation['module_id'] = str(evaluation['module_id'])
            
            return evaluation
        except Exception as e:
            return None
    
    def record_result(self, result_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que la evaluación existe
            evaluation_id = result_data.get('evaluation_id')
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return False, "Evaluación no encontrada"
            
            # Validar que el estudiante existe
            student_id = result_data.get('student_id')
            student = get_db().users.find_one({"_id": ObjectId(student_id)})
            if not student:
                return False, "Estudiante no encontrado"
            
            # Verificar si ya existe un resultado para esta evaluación y estudiante
            existing_result = get_db().evaluation_results.find_one({
                "evaluation_id": ObjectId(evaluation_id),
                "student_id": ObjectId(student_id)
            })
            
            result_data['evaluation_id'] = ObjectId(evaluation_id)
            result_data['student_id'] = ObjectId(student_id)
            result_data['recorded_at'] = datetime.now()
            
            evaluation_result = EvaluationResult(**result_data)
            
            if existing_result:
                # Actualizar resultado existente
                result = get_db().evaluation_results.update_one(
                    {"_id": existing_result["_id"]},
                    {"$set": evaluation_result.to_dict()}
                )
                return True, str(existing_result["_id"])
            else:
                # Crear nuevo resultado
                result = get_db().evaluation_results.insert_one(evaluation_result.to_dict())
                return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
    
    def update_result(self, result_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Actualizar timestamp
            update_data['recorded_at'] = datetime.now()
            
            # Actualizar el resultado
            result = get_db().evaluation_results.update_one(
                {"_id": ObjectId(result_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Resultado actualizado exitosamente"
            return False, "No se pudo actualizar el resultado"
        except Exception as e:
            return False, str(e)
    
    def delete_result(self, result_id: str) -> Tuple[bool, str]:
        try:
            # Eliminar el resultado
            result = get_db().evaluation_results.delete_one({"_id": ObjectId(result_id)})
            
            if result.deleted_count > 0:
                return True, "Resultado eliminado exitosamente"
            return False, "No se pudo eliminar el resultado"
        except Exception as e:
            return False, str(e)
    
    def get_student_results(self, student_id: str) -> List[Dict]:
        try:
            # Obtener resultados del estudiante
            results = list(get_db().evaluation_results.find({"student_id": ObjectId(student_id)}))
            
            # Enriquecer con datos de evaluaciones
            enriched_results = []
            for result in results:
                # Convertir ObjectId a string
                result['_id'] = str(result['_id'])
                result['evaluation_id'] = str(result['evaluation_id'])
                result['student_id'] = str(result['student_id'])
                
                # Obtener detalles de la evaluación
                evaluation = self.collection.find_one({"_id": ObjectId(result['evaluation_id'])})
                if evaluation:
                    result['evaluation'] = {
                        "title": evaluation.get("title", ""),
                        "description": evaluation.get("description", ""),
                        "weight": evaluation.get("weight", 0),
                        "module_id": str(evaluation.get("module_id", ""))
                    }
                    
                    # Obtener detalles del módulo
                    module = get_db().study_plan_modules.find_one({"_id": evaluation.get("module_id")})
                    if module:
                        result['module'] = {
                            "name": module.get("name", ""),
                            "study_plan_id": str(module.get("study_plan_id", ""))
                        }
                
                enriched_results.append(result)
            
            return enriched_results
        except Exception as e:
            return []
