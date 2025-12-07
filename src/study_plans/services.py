from typing import Tuple, List, Dict, Optional, Any, Union
from bson import ObjectId
from datetime import datetime, timedelta
import json
import re
import logging
from src.shared.validators import validate_object_id
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.database import get_db
from src.shared.cascade_deletion_service import CascadeDeletionService
from src.classes.services import ClassService
from src.study_plans.models import (
    StudyPlanPerSubject, StudyPlanAssignment, Module, Topic
)
from src.evaluations.models import (
    Evaluation, EvaluationResource, EvaluationRubric, EvaluationSubmission
)
from src.content.models import (
    TopicContent, ContentType, ContentTypes
)
from src.resources.services import ResourceService, ResourceFolderService
from src.content.services import ContentService
# from src.content.services import ContentResultService  # No existe aún
from src.virtual.services import ContentChangeDetector
from src.shared.logging import log_error
import inspect # <--- Añadir import

class StudyPlanService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="study_plans_per_subject")

    def create_study_plan(self, plan_data: dict, workspace_info: Dict = None) -> str:
        """
        Crea un nuevo plan de estudios.
        
        Args:
            plan_data: Datos del plan de estudios
            workspace_info: Información del workspace actual (opcional)
            
        Returns:
            ID del plan de estudios creado
            
        Raises:
            AppException: Si ocurre un error durante la creación
        """
        try:
            # Si author_id es un email, convertirlo a ObjectId
            if isinstance(plan_data['author_id'], str) and '@' in plan_data['author_id']:
                user = get_db().users.find_one({"email": plan_data['author_id']})
                if not user:
                    raise AppException("Usuario no encontrado", AppException.NOT_FOUND)
                plan_data['author_id'] = str(user['_id'])
            
            # Agregar información del workspace si está disponible
            if workspace_info:
                workspace_type = workspace_info.get('workspace_type')
                workspace_id = workspace_info.get('workspace_id')
                
                if workspace_type == 'INDIVIDUAL_TEACHER':
                    plan_data['workspace_id'] = ObjectId(workspace_id)
                    plan_data['workspace_type'] = workspace_type
                elif workspace_type == 'INSTITUTE':
                    institute_id = workspace_info.get('institute_id')
                    if institute_id:
                        plan_data['institute_id'] = ObjectId(institute_id)
                    plan_data['workspace_type'] = workspace_type
            
            study_plan = StudyPlanPerSubject(**plan_data)
            result = self.collection.insert_one(study_plan.to_dict())
            return str(result.inserted_id)
        except AppException:
            # Re-lanzar excepciones AppException
            raise
        except Exception as e:
            raise AppException(f"Error al crear plan de estudios: {str(e)}", AppException.BAD_REQUEST)

    def create_personal_study_plan(self, user_id: str, workspace_id: str, 
                                   title: str, description: str = "", 
                                   objectives: Optional[List[str]] = None) -> str:
        """
        Crea un plan de estudio personal en la colección unificada.
        """
        try:
            plan_data = {
                "version": "1.0",
                "name": title,
                "description": description,
                "author_id": str(user_id),
                "workspace_id": str(workspace_id),
                "workspace_type": "INDIVIDUAL_STUDENT",
                "is_personal": True,
                "objectives": objectives or [],
                "institute_id": None,
                "subject_id": None,
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            study_plan = StudyPlanPerSubject(**plan_data)
            result = self.collection.insert_one(study_plan.to_dict())
            return str(result.inserted_id)
        except Exception as e:
            raise AppException(f"Error al crear plan personal: {str(e)}", AppException.BAD_REQUEST)

    def list_personal_study_plans_by_workspace(self, workspace_id: str, user_id: Optional[str] = None) -> List[Dict]:
        """Lista planes personales de un workspace (opcionalmente filtrados por autor)."""
        try:
            query: Dict[str, Any] = {
                "is_personal": True,
                "workspace_id": ObjectId(workspace_id)
            }
            if user_id:
                query["author_id"] = ObjectId(user_id)
            plans = list(self.collection.find(query).sort("created_at", -1))
            for plan in plans:
                plan["_id"] = str(plan["_id"])
                # serializar ids
                if isinstance(plan.get("author_id"), ObjectId):
                    plan["author_id"] = str(plan["author_id"])
                if isinstance(plan.get("workspace_id"), ObjectId):
                    plan["workspace_id"] = str(plan["workspace_id"])
            return plans
        except Exception as e:
            logging.error(f"Error al listar planes personales: {str(e)}")
            return []

    def list_study_plans(
        self,
        email: Optional[str] = None,
        institute_id: Optional[str] = None,
        workspace_info: Dict = None
    ) -> List[Dict]:
        """Devuelve los planes de estudio filtrados por autor, instituto y workspace."""
        try:
            query = {}

            if email:
                user = get_db().users.find_one({"email": email})
                if user:
                    query["author_id"] = ObjectId(user["_id"])

            if institute_id:
                try:
                    query["institute_id"] = ObjectId(institute_id)
                except Exception:
                    logging.error(
                        "institute_id inválido en list_study_plans: %s", institute_id
                    )
            
            # Aplicar filtrado por workspace solo si workspace_id no es None
            if workspace_info:
                workspace_type = workspace_info.get('workspace_type')
                workspace_id = workspace_info.get('workspace_id')
                
                # Solo aplicar filtros de workspace si workspace_id es válido
                if workspace_id:  # CORRECCIÓN: Verificar que workspace_id no sea None
                    if workspace_type == 'INDIVIDUAL_TEACHER':
                        # En workspaces individuales de profesor, filtrar por workspace_id
                        query["workspace_id"] = ObjectId(workspace_id)
                    elif workspace_type == 'INSTITUTE':
                        # En workspaces institucionales, filtrar por institute_id
                        institute_id = workspace_info.get('institute_id')
                        if institute_id:
                            query["institute_id"] = ObjectId(institute_id)
                    elif workspace_type == 'INDIVIDUAL_STUDENT':
                        # En workspace individual de estudiante: planes personales del usuario
                        query["workspace_id"] = ObjectId(workspace_id)
                        query["is_personal"] = True
                # Si workspace_id es None, no aplicar filtros de workspace
                # Esto permite que usuarios sin workspace asignado vean sus planes

            plans = list(self.collection.find(query))

            for plan in plans:
                plan["_id"] = str(plan["_id"])
                if "author_id" in plan and isinstance(plan["author_id"], ObjectId):
                    plan["author_id"] = str(plan["author_id"])
                if "institute_id" in plan and isinstance(plan["institute_id"], ObjectId):
                    plan["institute_id"] = str(plan["institute_id"])
                if "workspace_id" in plan and isinstance(plan["workspace_id"], ObjectId):
                    plan["workspace_id"] = str(plan["workspace_id"])

            return plans
        except Exception as e:
            logging.error(f"Error al listar planes: {str(e)}")
            return []

    def get_study_plan(self, plan_id: str, workspace_info: Dict = None) -> Optional[Dict]:
        try:
            plan = self.collection.find_one({"_id": ObjectId(plan_id)})
            if not plan:
                return None

            # Convertir _id a string para que sea JSON serializable
            plan["_id"] = str(plan["_id"])
            if isinstance(plan.get("author_id"), ObjectId):
                plan["author_id"] = str(plan["author_id"])
            if isinstance(plan.get("workspace_id"), ObjectId):
                plan["workspace_id"] = str(plan["workspace_id"])
            if isinstance(plan.get("institute_id"), ObjectId):
                plan["institute_id"] = str(plan["institute_id"])
            
            # Obtener módulos asociados
            modules = list(get_db().modules.find({"study_plan_id": ObjectId(plan_id)}))
            
            # Para cada módulo, obtener sus temas y evaluaciones
            for module in modules:
                # Convertir ObjectId a string
                module["_id"] = str(module["_id"])
                module["study_plan_id"] = str(module["study_plan_id"])
                
                # Rellenar date_start y date_end si faltan (para registros antiguos)
                if 'date_start' not in module or module.get('date_start') is None:
                    module['date_start'] = module.get('created_at')
                if 'date_end' not in module or module.get('date_end') is None:
                    module['date_end'] = module.get('created_at')
                
                # Obtener temas relacionados
                topics = list(get_db().topics.find({"module_id": ObjectId(module["_id"])}))
                for topic in topics:
                    topic["_id"] = str(topic["_id"])
                    topic["module_id"] = str(topic["module_id"])
                    
                    # Rellenar date_start y date_end si faltan en el topic
                    if 'date_start' not in topic or topic.get('date_start') is None:
                        topic['date_start'] = topic.get('created_at')
                    if 'date_end' not in topic or topic.get('date_end') is None:
                        topic['date_end'] = topic.get('created_at')
                
                module["topics"] = topics
                
                # Obtener evaluaciones asociadas a los temas del módulo
                module_topic_ids = [ObjectId(t["_id"]) for t in topics]
                evaluations = []
                if module_topic_ids:
                    evaluations = list(get_db().evaluations.find({"topic_ids": {"$in": module_topic_ids}}))
                
                # Prevenir duplicados si una evaluación está en múltiples temas del mismo módulo
                unique_evaluations = {str(e["_id"]): e for e in evaluations}.values()

                for evaluation in unique_evaluations:
                    evaluation["_id"] = str(evaluation["_id"])
                    evaluation["topic_ids"] = [str(tid) for tid in evaluation["topic_ids"]]
                
                module["evaluations"] = list(unique_evaluations)

            plan["modules"] = modules
            
            # Agregar información del workspace si está disponible
            if workspace_info:
                plan["workspace_context"] = {
                    "workspace_type": workspace_info.get('workspace_type'),
                    "workspace_name": workspace_info.get('workspace_name')
                }
            
            return plan
        except Exception as e:
            logging.error(f"Error al obtener plan de estudio: {str(e)}")
            return None

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

    def delete_study_plan(self, plan_id: str, cascade: bool = False) -> Tuple[bool, str]:
        """
        Elimina un plan de estudios. Si cascade=True, elimina también los módulos, temas,
        asignaciones y cualquier entidad dependiente registrada en CascadeDeletionService.
        """
        validate_object_id(plan_id)
        db = get_db()

        plan = self.collection.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            return False, "Plan de estudios no encontrado"

        assignments_count = db.study_plan_assignments.count_documents({"study_plan_id": ObjectId(plan_id)})
        modules_count = db.modules.count_documents({"study_plan_id": ObjectId(plan_id)})

        if not cascade:
            if assignments_count > 0:
                return False, f"No se puede eliminar el plan porque tiene {assignments_count} asignación(es) activas"
            if modules_count > 0:
                return False, f"No se puede eliminar el plan porque tiene {modules_count} módulo(s) asociados"

            result = self.collection.delete_one({"_id": ObjectId(plan_id)})
            if result.deleted_count > 0:
                return True, "Plan de estudios eliminado correctamente"
            return False, "No se pudo eliminar el plan de estudios"

        cascade_service = CascadeDeletionService()

        try:
            cascade_result = cascade_service.delete_with_cascade('study_plans', plan_id)
        except Exception as exc:
            logging.error(f"Error al ejecutar eliminación en cascada del plan {plan_id}: {exc}")
            return False, "Error al eliminar el plan de estudios en cascada"

        if not cascade_result.get('success', False):
            return False, cascade_result.get('error', 'No se pudo eliminar el plan de estudios')

        total_deleted = cascade_result.get('total_deleted', 1)
        dependencies_deleted = max(total_deleted - 1, 0)
        if dependencies_deleted > 0:
            return True, f"Plan de estudios eliminado junto con {dependencies_deleted} dependencias"
        return True, "Plan de estudios eliminado correctamente"

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
            
            # Buscar el usuario por email si se proporciona email
            if isinstance(assignment_data['assigned_by'], str) and '@' in assignment_data['assigned_by']:
                user = get_db().users.find_one({"email": assignment_data['assigned_by']})
                if not user:
                    raise AppException("Usuario no encontrado", AppException.NOT_FOUND)
                assigned_by = user['_id']
            else:
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
            # Convertir posibles IDs a ObjectId
            if 'study_plan_id' in update_data and isinstance(update_data['study_plan_id'], str):
                update_data['study_plan_id'] = ObjectId(update_data['study_plan_id'])
            if 'class_id' in update_data and isinstance(update_data['class_id'], str):
                update_data['class_id'] = ObjectId(update_data['class_id'])
            if 'subperiod_id' in update_data and isinstance(update_data['subperiod_id'], str):
                update_data['subperiod_id'] = ObjectId(update_data['subperiod_id'])
            if 'assigned_by' in update_data and isinstance(update_data['assigned_by'], str):
                update_data['assigned_by'] = ObjectId(update_data['assigned_by'])
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

    def get_class_assigned_plan(self, class_id: str, subperiod_id: str) -> Optional[Dict]:
        """
        Obtiene el plan de estudios asignado a una clase durante un subperiodo específico
        
        Args:
            class_id: ID de la clase
            subperiod_id: ID del subperiodo
            
        Returns:
            Dict: Datos del plan asignado o None si no hay
        """
        try:
            # Convertir IDs a ObjectId
            class_id_obj = ObjectId(class_id)
            subperiod_id_obj = ObjectId(subperiod_id)
            
            # Buscar asignación activa
            assignment = self.collection.find_one({
                "class_id": class_id_obj,
                "subperiod_id": subperiod_id_obj,
                "is_active": True
            })
            
            if not assignment:
                return None
                
            # Convertir ObjectIds a strings
            assignment['_id'] = str(assignment['_id'])
            assignment['study_plan_id'] = str(assignment['study_plan_id'])
            assignment['class_id'] = str(assignment['class_id'])
            assignment['subperiod_id'] = str(assignment['subperiod_id'])
            assignment['assigned_by'] = str(assignment['assigned_by'])
            
            # Obtener detalles del plan asignado
            study_plan = get_db().study_plans_per_subject.find_one({"_id": ObjectId(assignment['study_plan_id'])})
            if study_plan:
                study_plan['_id'] = str(study_plan['_id'])
                if 'author_id' in study_plan and isinstance(study_plan['author_id'], ObjectId):
                    study_plan['author_id'] = str(study_plan['author_id'])
                assignment['study_plan'] = study_plan
                
            return assignment
        except Exception as e:
            logging.error(f"Error al obtener plan asignado: {str(e)}")
            return None
            
    def list_plan_assignments(self, plan_id: str = None) -> List[Dict]:
        """
        Lista todas las asignaciones de planes, opcionalmente filtrando por plan
        
        Args:
            plan_id: ID del plan para filtrar (opcional)
            
        Returns:
            List[Dict]: Lista de asignaciones
        """
        try:
            query = {"is_active": True}
            if plan_id:
                query["study_plan_id"] = ObjectId(plan_id)
                
            assignments = list(self.collection.find(query))
            
            # Convertir ObjectIds a strings
            for assignment in assignments:
                assignment['_id'] = str(assignment['_id'])
                assignment['study_plan_id'] = str(assignment['study_plan_id'])
                assignment['class_id'] = str(assignment['class_id'])
                assignment['subperiod_id'] = str(assignment['subperiod_id'])
                assignment['assigned_by'] = str(assignment['assigned_by'])
                
                # Obtener información básica de la clase
                class_doc = get_db().classes.find_one({"_id": ObjectId(assignment['class_id'])})
                if class_doc:
                    assignment['class_info'] = {
                        "name": class_doc.get("name", ""),
                        "section": class_doc.get("section", "")
                    }
                    
                # Obtener nombre del plan
                plan = get_db().study_plans_per_subject.find_one({"_id": ObjectId(assignment['study_plan_id'])})
                if plan:
                    assignment['plan_name'] = plan.get("name", "Plan sin nombre")
                    
            return assignments
        except Exception as e:
            logging.error(f"Error al listar asignaciones: {str(e)}")
            return []

class ModuleService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="modules")

    def get_module_details(self, module_id: str) -> Optional[Dict]:
        """
        Obtiene los detalles de un módulo junto con sus temas y evaluaciones.
        
        Args:
            module_id: ID del módulo a consultar
            
        Returns:
            Diccionario con detalles del módulo, sus temas y evaluaciones, o None si no existe
        """
        try:
            # Validar el ID
            validate_object_id(module_id)
            
            # Obtener el módulo
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return None
                
            # Rellenar date_start y date_end si faltan (para registros antiguos)
            if 'date_start' not in module or module.get('date_start') is None:
                module['date_start'] = module.get('created_at')
            if 'date_end' not in module or module.get('date_end') is None:
                module['date_end'] = module.get('created_at')
            
            # Obtener temas relacionados
            topics = list(get_db().topics.find({"module_id": ObjectId(module_id)}))
            
            # Obtener evaluaciones relacionadas a los temas
            topic_ids = [t["_id"] for t in topics]
            evaluations = []
            if topic_ids:
                evaluations = list(get_db().evaluations.find({"topic_ids": {"$in": topic_ids}}))
            
            # Agregar temas y evaluaciones al módulo
            module['topics'] = topics
            module['evaluations'] = evaluations
            
            return module
        except Exception as e:
            logging.error(f"Error al obtener detalles del módulo: {str(e)}")
            return None
            
    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que existe el plan de estudio
            study_plan_id = module_data.get('study_plan_id')
            study_plan = get_db().study_plans_per_subject.find_one({"_id": ObjectId(study_plan_id)})
            if not study_plan:
                return False, "Plan de estudio no encontrado"
            
            # Crear una copia de los datos para no modificarlos directamente
            module_dict = {
                "study_plan_id": ObjectId(study_plan_id),
                "name": module_data.get('name'),
                "learning_outcomes": module_data.get('learning_outcomes')
                # evaluation_rubric se manejará a continuación
            }
            
            # ---- Inicio: Manejo de evaluation_rubric ----
            rubric = module_data.get('evaluation_rubric')
            if isinstance(rubric, str):
                try:
                    rubric = json.loads(rubric)
                    logging.info(f"Parsed evaluation_rubric string to dict for study plan {study_plan_id}")
                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse evaluation_rubric string for study plan {study_plan_id}. Using empty dict.")
                    rubric = {}
            # Asegurar que sea un dict, default a {} si es None o no es dict tras posible parseo
            if not isinstance(rubric, dict):
                 logging.warning(f"evaluation_rubric is not a dict for study plan {study_plan_id}. Type: {type(rubric)}. Using empty dict.")
                 rubric = {}
            module_dict["evaluation_rubric"] = rubric
            # ---- Fin: Manejo de evaluation_rubric ----
            
            # Agregar parseo de date_start y date_end
            date_start = module_data.get('date_start')
            if isinstance(date_start, str):
                date_start = datetime.fromisoformat(date_start)
            date_end = module_data.get('date_end')
            if isinstance(date_end, str):
                date_end = datetime.fromisoformat(date_end)
            module_dict['date_start'] = date_start
            module_dict['date_end'] = date_end
            
            # Crear el módulo con parámetros exactos
            module = Module(**module_dict)
            
            # Obtener el diccionario del módulo y agregar timestamps
            module_to_insert = module.to_dict()
            module_to_insert['created_at'] = datetime.now()
            module_to_insert['updated_at'] = datetime.now()
            
            result = self.collection.insert_one(module_to_insert)
            
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
    
    def update_module(self, module_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el módulo existe
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Convertir study_plan_id a ObjectId si se actualiza
            if 'study_plan_id' in update_data and isinstance(update_data['study_plan_id'], str):
                update_data['study_plan_id'] = ObjectId(update_data['study_plan_id'])

            # ---- Inicio: Manejo de evaluation_rubric en actualización ----
            if 'evaluation_rubric' in update_data:
                rubric = update_data['evaluation_rubric']
                if isinstance(rubric, str):
                    try:
                        update_data['evaluation_rubric'] = json.loads(rubric)
                        logging.info(f"Parsed evaluation_rubric string to dict during update for module {module_id}")
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to parse evaluation_rubric string during update for module {module_id}. Setting empty dict.")
                        update_data['evaluation_rubric'] = {}
                # Asegurar que sea un dict si no era string o tras parseo
                elif not isinstance(rubric, dict):
                     logging.warning(f"evaluation_rubric is not a dict during update for module {module_id}. Type: {type(rubric)}. Setting empty dict.")
                     update_data['evaluation_rubric'] = {}
            # ---- Fin: Manejo de evaluation_rubric en actualización ----

            # Manejar date_start y date_end: parsear o crear si no existen
            if 'date_start' in update_data:
                if isinstance(update_data['date_start'], str):
                    update_data['date_start'] = datetime.fromisoformat(update_data['date_start'])
            elif 'date_start' not in module or module.get('date_start') is None:
                update_data['date_start'] = module.get('created_at')

            if 'date_end' in update_data:
                if isinstance(update_data['date_end'], str):
                    update_data['date_end'] = datetime.fromisoformat(update_data['date_end'])
            elif 'date_end' not in module or module.get('date_end') is None:
                update_data['date_end'] = module.get('created_at')
            
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
    
    def delete_module(self, module_id: str, cascade: bool = False) -> Tuple[bool, str]:
        try:
            validate_object_id(module_id)
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"

            db = get_db()
            topics_count = db.topics.count_documents({"module_id": ObjectId(module_id)})
            virtual_modules_count = db.virtual_modules.count_documents({"module_id": ObjectId(module_id)})
            generation_tasks_count = db.virtual_generation_tasks.count_documents({"module_id": ObjectId(module_id)})

            if not cascade:
                if topics_count > 0 or virtual_modules_count > 0 or generation_tasks_count > 0:
                    return False, (
                        "No se puede eliminar el módulo porque tiene dependencias: "
                        f"{topics_count} tema(s), {virtual_modules_count} módulo(s) virtual(es) "
                        f"y {generation_tasks_count} tarea(s) de generación."
                    )

                result = self.collection.delete_one({"_id": ObjectId(module_id)})
                if result.deleted_count > 0:
                    return True, "Módulo eliminado exitosamente"
                return False, "No se pudo eliminar el módulo"

            cascade_service = CascadeDeletionService()
            cascade_result = cascade_service.delete_with_cascade('modules', module_id)
            if not cascade_result.get('success', False):
                return False, cascade_result.get('error', 'No se pudo eliminar el módulo en cascada')

            total_deleted = cascade_result.get('total_deleted', 1)
            dependencies_deleted = max(total_deleted - 1, 0)
            if dependencies_deleted > 0:
                return True, f"Módulo eliminado junto con {dependencies_deleted} dependencias"
            return True, "Módulo eliminado exitosamente"
        except Exception as e:
            logging.error(f"Error al eliminar módulo {module_id}: {e}")
            return False, str(e)
    
    def get_module(self, module_id: str) -> Optional[Dict]:
        try:
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return None
            
            # Rellenar date_start y date_end si faltan en get_module
            if 'date_start' not in module or module.get('date_start') is None:
                module['date_start'] = module.get('created_at')
            if 'date_end' not in module or module.get('date_end') is None:
                module['date_end'] = module.get('created_at')
            
            # Convertir ObjectId a string
            module['_id'] = str(module['_id'])
            module['study_plan_id'] = str(module['study_plan_id'])
            
            # Obtener temas del módulo
            topic_service = TopicService()
            module['topics'] = topic_service.get_module_topics(module_id)
            
            return module
        except Exception as e:
            return None

    def check_slides_completeness_for_module(self, module_id: str) -> Dict:
        """
        Verifica la completitud de las diapositivas de todos los temas de un módulo.
        
        Args:
            module_id: ID del módulo
            
        Returns:
            Dict con estadísticas detalladas sobre el estado de las diapositivas
        """
        try:
            validate_object_id(module_id, "ID de módulo")
            db = get_db()
            
            # Obtener todos los temas del módulo
            topics = list(db.topics.find({"module_id": ObjectId(module_id)}))
            topic_ids = [t["_id"] for t in topics]
            
            if not topic_ids:
                return {
                    "total_topics": 0,
                    "topics_with_slides": 0,
                    "slides_by_status": {},
                    "topics_needing_attention": [],
                    "completion_percentage": 0.0,
                    "slides_statistics": {
                        "total_slides": 0,
                        "skeleton": 0,
                        "html_ready": 0,
                        "narrative_ready": 0
                    }
                }
            
            # Consultar todas las diapositivas del módulo
            slides_query = {
                "topic_id": {"$in": topic_ids},
                "content_type": "slide",
                "status": {"$ne": "deleted"}
            }
            
            slides = list(db.topic_contents.find(slides_query, {
                "topic_id": 1,
                "status": 1,
                "content.content_html": 1,
                "content.narrative_text": 1,
                "content.full_text": 1
            }))
            
            # Estadísticas por estado
            slides_by_status = {}
            topics_with_slides = set()
            topics_needing_attention = []
            
            for slide in slides:
                status = slide.get("status", "draft")
                slides_by_status[status] = slides_by_status.get(status, 0) + 1
                topics_with_slides.add(str(slide["topic_id"]))
            
            # Verificar cada tema para identificar los que necesitan atención
            for topic in topics:
                topic_id_str = str(topic["_id"])
                topic_slides = [s for s in slides if str(s["topic_id"]) == topic_id_str]
                
                if not topic_slides:
                    topics_needing_attention.append({
                        "topic_id": topic_id_str,
                        "topic_name": topic.get("name", "Sin nombre"),
                        "issue": "no_slides",
                        "description": "No tiene diapositivas"
                    })
                    continue
                
                # Verificar completitud de diapositivas
                narrative_ready_count = len([s for s in topic_slides if s.get("status") == "narrative_ready"])
                html_ready_count = len([s for s in topic_slides if s.get("status") == "html_ready"])
                skeleton_count = len([s for s in topic_slides if s.get("status") == "skeleton"])
                
                issues = []
                if skeleton_count > 0:
                    issues.append(f"{skeleton_count} diapositivas sin HTML")
                if html_ready_count > 0:
                    issues.append(f"{html_ready_count} diapositivas sin narrativa")
                
                if issues:
                    topics_needing_attention.append({
                        "topic_id": topic_id_str,
                        "topic_name": topic.get("name", "Sin nombre"),
                        "issue": "incomplete_slides",
                        "description": ", ".join(issues),
                        "slides_count": len(topic_slides),
                        "narrative_ready": narrative_ready_count,
                        "html_ready": html_ready_count,
                        "skeleton": skeleton_count
                    })
            
            # Calcular porcentaje de completitud
            total_slides = len(slides)
            narrative_ready_slides = slides_by_status.get("narrative_ready", 0)
            completion_percentage = (narrative_ready_slides / total_slides * 100) if total_slides > 0 else 0.0
            
            return {
                "total_topics": len(topics),
                "topics_with_slides": len(topics_with_slides),
                "slides_by_status": slides_by_status,
                "topics_needing_attention": topics_needing_attention,
                "completion_percentage": round(completion_percentage, 2),
                "slides_statistics": {
                    "total_slides": total_slides,
                    "skeleton": slides_by_status.get("skeleton", 0),
                    "html_ready": slides_by_status.get("html_ready", 0),
                    "narrative_ready": slides_by_status.get("narrative_ready", 0)
                }
            }
            
        except Exception as e:
            logging.error(f"Error verificando completitud de diapositivas para módulo {module_id}: {str(e)}")
            return {
                "total_topics": 0,
                "topics_with_slides": 0,
                "slides_by_status": {},
                "topics_needing_attention": [],
                "completion_percentage": 0.0,
                "slides_statistics": {
                    "total_slides": 0,
                    "skeleton": 0,
                    "html_ready": 0,
                    "narrative_ready": 0
                }
            }

    def get_virtualization_readiness(self, module_id: str) -> Dict:
        """
        Verifica requisitos para virtualización y sugiere acciones.
        Integra verificación de diapositivas con HTML y narrativa.
        Implementa lógica automática para marcar Topic.published=true.
        """
        validate_object_id(module_id, "ID de módulo")
        module = self.collection.find_one({"_id": ObjectId(module_id)})
        if not module:
            raise AppException("Módulo no encontrado", AppException.NOT_FOUND)
        
        db = get_db()
        # Obtener temas del módulo
        topics = list(db.topics.find({"module_id": ObjectId(module_id)}))
        total_topics = len(topics)
        
        # Obtener estadísticas de diapositivas
        slides_stats = self.check_slides_completeness_for_module(module_id)
        
        # Conteo de temas publicados/no publicados
        published_topics = list(db.topics.find({"module_id": ObjectId(module_id), "published": True}))
        published_topics_count = len(published_topics)
        unpublished_topics_count = total_topics - published_topics_count
        
        # Análisis de contenido teórico y recursos
        missing_theory = [t for t in topics if not t.get("theory_content")]
        missing_resources = [t for t in topics if not t.get("resources") or len(t.get("resources")) == 0]
        
        # Conteo de evaluaciones
        topic_ids = [t["_id"] for t in topics]
        eval_count = 0
        if topic_ids:
            eval_count = db.evaluations.count_documents({"topic_ids": {"$in": topic_ids}})
        
        # Lógica automática para marcar Topic.published=true
        topics_auto_published = 0
        for topic in topics:
            topic_id = topic["_id"]
            
            # Verificar criterios para auto-publicación:
            # 1) theory_content presente
            has_theory = bool(topic.get("theory_content"))
            
            # 2) al menos una diapositiva en estado 'narrative_ready'
            narrative_ready_slides = db.topic_contents.count_documents({
                "topic_id": topic_id,
                "content_type": "slide",
                "status": "narrative_ready"
            })
            has_complete_slides = narrative_ready_slides > 0
            
            # 3) al menos una evaluación/quiz asociada
            has_evaluation = db.evaluations.count_documents({"topic_ids": topic_id}) > 0
            
            # Si cumple todos los criterios y no está publicado, publicarlo automáticamente
            if has_theory and has_complete_slides and has_evaluation and not topic.get("published", False):
                try:
                    db.topics.update_one(
                        {"_id": topic_id},
                        {
                            "$set": {
                                "published": True,
                                "auto_published_at": datetime.now(),
                                "updated_at": datetime.now()
                            }
                        }
                    )
                    topics_auto_published += 1
                    logging.info(f"Tema {topic_id} marcado automáticamente como publicado")
                except Exception as e:
                    logging.error(f"Error auto-publicando tema {topic_id}: {str(e)}")
        
        # Recalcular temas publicados después de auto-publicación
        if topics_auto_published > 0:
            published_topics = list(db.topics.find({"module_id": ObjectId(module_id), "published": True}))
            published_topics_count = len(published_topics)
            unpublished_topics_count = total_topics - published_topics_count
        
        # Calcular content_completeness_score considerando teoría y diapositivas
        content_completeness_score = 0
        if total_topics > 0:
            topics_with_theory = total_topics - len(missing_theory)
            
            # Contar temas con diapositivas completas (narrative_ready)
            topics_with_complete_slides = 0
            for topic in topics:
                narrative_ready_count = db.topic_contents.count_documents({
                    "topic_id": topic["_id"],
                    "content_type": "slide",
                    "status": "narrative_ready"
                })
                if narrative_ready_count > 0:
                    topics_with_complete_slides += 1
            
            # Nueva fórmula: (temas_con_teoría + temas_con_diapositivas_completas) / (total_temas * 2) * 100
            content_completeness_score = int(((topics_with_theory + topics_with_complete_slides) / (total_topics * 2)) * 100)
            
            # Actualizar el score en el módulo si ha cambiado
            current_score = module.get("content_completeness_score", 0)
            if current_score != content_completeness_score:
                self.collection.update_one(
                    {"_id": ObjectId(module_id)},
                    {
                        "$set": {
                            "content_completeness_score": content_completeness_score,
                            "last_content_update": datetime.now()
                        }
                    }
                )
        
        # Preparar detalles de cheques incluyendo estadísticas de diapositivas
        checks = {
            "total_topics": total_topics,
            "published_topics_count": published_topics_count,
            "unpublished_topics_count": unpublished_topics_count,
            "missing_theory_count": len(missing_theory),
            "missing_resources_count": len(missing_resources),
            "evaluations_count": eval_count,
            "content_completeness_score": content_completeness_score,
            "topics_auto_published": topics_auto_published,
            "slides_statistics": slides_stats["slides_statistics"],
            "slides_completion_percentage": slides_stats["completion_percentage"],
            "topics_with_complete_slides": len([t for t in topics if db.topic_contents.count_documents({
                "topic_id": t["_id"],
                "content_type": "slide", 
                "status": "narrative_ready"
            }) > 0])
        }
        
        # Generar sugerencias incluyendo recomendaciones específicas sobre diapositivas
        suggestions = []
        
        # Sugerencias sobre publicación
        if unpublished_topics_count > 0:
            suggestions.append(f"{unpublished_topics_count} temas sin publicar")
        
        if topics_auto_published > 0:
            suggestions.append(f"{topics_auto_published} temas fueron publicados automáticamente")
        
        # Sugerencias básicas
        if total_topics == 0:
            suggestions.append("Agregar al menos un tema al módulo")
        else:
            if checks["missing_theory_count"] > 0:
                suggestions.append(f"{checks['missing_theory_count']} temas sin contenido teórico")
            if checks["missing_resources_count"] > 0:
                suggestions.append(f"{checks['missing_resources_count']} temas sin recursos asociados")
        
        # Sugerencias específicas sobre diapositivas
        skeleton_count = slides_stats["slides_statistics"]["skeleton"]
        html_ready_count = slides_stats["slides_statistics"]["html_ready"]
        topics_without_slides = total_topics - slides_stats["topics_with_slides"]
        
        if topics_without_slides > 0:
            suggestions.append(f"{topics_without_slides} temas sin diapositivas")
        if skeleton_count > 0:
            suggestions.append(f"{skeleton_count} diapositivas sin HTML")
        if html_ready_count > 0:
            suggestions.append(f"{html_ready_count} diapositivas sin narrativa")
        
        # Sugerencias sobre evaluaciones
        if eval_count == 0:
            suggestions.append("Agregar al menos una evaluación al módulo")
        
        # Determinar si está listo para virtualización
        # Ahora considera que todos los temas publicados tengan diapositivas completas
        ready = all([
            checks["published_topics_count"] > 0,
            checks["missing_theory_count"] == 0,
            checks["missing_resources_count"] == 0,
            eval_count > 0,
            slides_stats["completion_percentage"] >= 80.0  # Al menos 80% de diapositivas completas
        ])
        
        return {
            "ready": ready, 
            "checks": checks, 
            "suggestions": suggestions,
            "slides_details": slides_stats
        }

class TopicService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="topics")
        # El servicio de vinculación de recursos de temas ya no es necesario
        # self.topic_resource_service = TopicResourceService()

    def create_topic(self, topic_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que existe el módulo
            module_id = topic_data.get('module_id')
            module = get_db().modules.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Extraer recursos externos si existen para procesarlos después
            external_resources = topic_data.pop('resources', [])
            
            # Crear el tema con los datos restantes
            topic = Topic(
                module_id=module_id,
                name=topic_data.get("name"),
                difficulty=topic_data.get("difficulty"),
                date_start=datetime.fromisoformat(topic_data.get('date_start')) if isinstance(topic_data.get('date_start'), str) else topic_data.get('date_start'),
                date_end=datetime.fromisoformat(topic_data.get('date_end')) if isinstance(topic_data.get('date_end'), str) else topic_data.get('date_end'),
                theory_content=topic_data.get("theory_content", ""),
                published=topic_data.get("published", False)
            )
            
            topic_to_insert = topic.to_dict()
            topic_to_insert['updated_at'] = datetime.now()
            
            result = self.collection.insert_one(topic_to_insert)
            topic_id = str(result.inserted_id)
            
            # Procesar recursos externos como TopicContent
            if external_resources:
                topic_content_service = TopicContentService()
                
                # Obtener el creator_id del plan de estudio para asignarlo a los contenidos
                creator_id = None
                study_plan = get_db().study_plans_per_subject.find_one({"_id": module.get("study_plan_id")})
                if study_plan:
                    creator_id = str(study_plan.get("author_id"))

                for resource in external_resources:
                    content_type = resource.get("resource_type", "link").lower()
                    if content_type not in [ContentTypes.LINK, ContentTypes.DOCUMENTS, ContentTypes.IMAGE]:
                        content_type = ContentTypes.LINK # Default a link

                    content_data = {
                        "topic_id": topic_id,
                        "content_type": content_type,
                        "title": resource.get("title", "Recurso"),
                        "description": resource.get("description", ""),
                        "content_data": {"url": resource.get("url", "")},
                        "tags": resource.get("tags", []),
                        "status": "active",
                        "creator_id": creator_id
                    }
                    try:
                        topic_content_service.create_content(content_data)
                    except Exception as e_content:
                        logging.error(f"Error creando TopicContent para el recurso '{resource.get('title')}': {e_content}")

            return True, topic_id
        except Exception as e:
            logging.error(f"Error al crear topic: {str(e)}")
            return False, str(e)
    
    def update_topic(self, topic_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el tema existe
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, "Tema no encontrado"
            
            # Convertir module_id a ObjectId si se actualiza
            if 'module_id' in update_data and isinstance(update_data['module_id'], str):
                update_data['module_id'] = ObjectId(update_data['module_id'])
            
            # Manejar date_start y date_end: parsear o crear si no existen
            if 'date_start' in update_data:
                if isinstance(update_data['date_start'], str):
                    update_data['date_start'] = datetime.fromisoformat(update_data['date_start'])
            elif 'date_start' not in topic or topic.get('date_start') is None:
                update_data['date_start'] = topic.get('created_at')

            if 'date_end' in update_data:
                if isinstance(update_data['date_end'], str):
                    update_data['date_end'] = datetime.fromisoformat(update_data['date_end'])
            elif 'date_end' not in topic or topic.get('date_end') is None:
                update_data['date_end'] = topic.get('created_at')
            
            # Actualizar timestamp
            update_data['updated_at'] = datetime.now()
            
            # Actualizar el tema
            result = self.collection.update_one(
                {"_id": ObjectId(topic_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                # Disparar detección de cambios y encolar actualizaciones
                module_id = str(topic.get("module_id"))
                if module_id:
                    try:
                        change_detector = ContentChangeDetector()
                        change_info = change_detector.detect_changes(module_id)
                        if change_info.get("has_changes"):
                            change_detector.schedule_incremental_updates(module_id, change_info)
                            logging.info(f"Cambios detectados en el módulo {module_id} tras actualizar el tema {topic_id}. Actualizaciones encoladas.")
                    except Exception as e:
                        logging.error(f"Error en el proceso de detección de cambios para el módulo {module_id}: {e}")

                return True, "Tema actualizado exitosamente"
            return False, "No se pudo actualizar el tema"
        except Exception as e:
            return False, str(e)
    
    def delete_topic(self, topic_id: str, cascade: bool = False) -> Tuple[bool, str]:
        """
        Elimina un tema. Si cascade=True, elimina también los contenidos, evaluaciones,
        recursos y entidades virtuales asociadas siguiendo las reglas del CascadeDeletionService.
        """
        try:
            validate_object_id(topic_id)
            topic_id_obj = ObjectId(topic_id)
            db = get_db()

            topic = self.collection.find_one({"_id": topic_id_obj})
            if not topic:
                return False, "Tema no encontrado"

            contents_count = db.topic_contents.count_documents({"topic_id": topic_id_obj})
            virtual_topics_count = db.virtual_topics.count_documents({"topic_id": topic_id_obj})
            evaluations = list(db.evaluations.find({"topic_ids": topic_id_obj}, {"_id": 1, "topic_ids": 1}))

            if not cascade:
                if contents_count > 0 or virtual_topics_count > 0 or len(evaluations) > 0:
                    return False, (
                        "No se puede eliminar el tema porque tiene dependencias: "
                        f"{contents_count} contenido(s), {virtual_topics_count} instancia(s) virtual(es) "
                        f"y {len(evaluations)} evaluación(es) asociadas."
                    )

                result = self.collection.delete_one({"_id": topic_id_obj})
                if result.deleted_count > 0:
                    return True, "Tema eliminado exitosamente"
                return False, "No se pudo eliminar el tema"

            cascade_service = CascadeDeletionService()

            # Ajustar evaluaciones para evitar eliminar evaluaciones compartidas
            for evaluation in evaluations:
                topic_ids = evaluation.get("topic_ids", [])
                if len(topic_ids) > 1:
                    db.evaluations.update_one(
                        {"_id": evaluation["_id"]},
                        {"$pull": {"topic_ids": topic_id_obj}}
                    )
                else:
                    cascade_service.delete_with_cascade('evaluations', str(evaluation["_id"]))

            cascade_result = cascade_service.delete_with_cascade('topics', topic_id)
            if not cascade_result.get('success', False):
                return False, cascade_result.get('error', 'No se pudo eliminar el tema en cascada')

            total_deleted = cascade_result.get('total_deleted', 1)
            dependencies_deleted = max(total_deleted - 1, 0)
            if dependencies_deleted > 0:
                return True, f"Tema eliminado junto con {dependencies_deleted} dependencias"
            return True, "Tema eliminado exitosamente"

        except Exception as e:
            logging.error(f"Error al eliminar el tema {topic_id}: {e}")
            return False, f"Error interno al eliminar el tema: {str(e)}"
    
    def get_topic(self, topic_id: str) -> Optional[Dict]:
        try:
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return None
            
            # Convertir ObjectId a string
            topic['_id'] = str(topic['_id'])
            topic['module_id'] = str(topic['module_id'])
            
            # Rellenar date_start y date_end si faltan en get_topic
            if 'date_start' not in topic or topic.get('date_start') is None:
                topic['date_start'] = topic.get('created_at')
            if 'date_end' not in topic or topic.get('date_end') is None:
                topic['date_end'] = topic.get('created_at')

            return topic
        except Exception as e:
            logging.error(f"Error al obtener tema: {str(e)}")
            return None
    
    def get_module_topics(self, module_id: str) -> List[Dict]:
        try:
            topics = list(self.collection.find({"module_id": ObjectId(module_id)}))
            
            # Convertir ObjectId a string en cada tema
            for topic in topics:
                topic['_id'] = str(topic['_id'])
                topic['module_id'] = str(topic['module_id'])
                
                # Rellenar date_start y date_end si faltan en lista de topics
                if 'date_start' not in topic or topic.get('date_start') is None:
                    topic['date_start'] = topic.get('created_at')
                if 'date_end' not in topic or topic.get('date_end') is None:
                    topic['date_end'] = topic.get('created_at')
            
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
                elif result.matched_count > 0 and result.modified_count == 0:
                    logging.info(f"update_theory_content: Sin cambios en el contenido teórico para topic {topic_id}")
                    return True, "Sin cambios en el contenido teórico"
                else:
                    return False, "Tema no encontrado"
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
    
    def get_topic_theory_content(self, topic_id: str) -> Optional[str]:
        """
        Obtiene solo el contenido teórico de un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Contenido teórico o None si no existe el tema
        """
        try:
            # Obtener solo el contenido teórico
            topic = self.collection.find_one(
                {"_id": ObjectId(topic_id)},
                {"theory_content": 1}
            )
            
            if not topic:
                return None
            
            # Devolver solo el texto del contenido teórico
            return topic.get("theory_content", "")
        except Exception as e:
            logging.error(f"Error al obtener contenido teórico: {str(e)}")
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
            
    def delete_topic_theory_content(self, topic_id: str) -> Tuple[bool, str]:
        """
        Elimina el contenido teórico de un tema.
        """
        # Reutilizamos el método delete_theory_content
        return self.delete_theory_content(topic_id)

    def get_topic_content_by_type(self, topic_id: str, content_type: str) -> Optional[List[Dict]]:
        """
        Obtiene todos los contenidos de un tema según su tipo.
        """
        try:
            contents = list(self.collection.find({
                "topic_id": ObjectId(topic_id),
                "content_type": content_type
            }))
            # Convertir ObjectId a str para serialización
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
            return contents
        except Exception as e:
            logging.error(f"Error al obtener contenidos por tipo: {str(e)}")
            return None

    def validate_theory_content_integrity(self, topic_id: str) -> Dict[str, Any]:
        """
        Valida la integridad de los datos de contenido teórico entre Topic.theory_content
        y cualquier TopicContent de tipo 'text' existente.

        Args:
            topic_id: ID del tema a validar

        Returns:
            Dict con información de integridad y inconsistencias encontradas
        """
        try:
            validate_object_id(topic_id)

            # Obtener el tema
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return {
                    "valid": False,
                    "error": "Tema no encontrado",
                    "topic_id": topic_id
                }

            # Obtener theory_content del Topic
            topic_theory_content = topic.get("theory_content", "")
            has_topic_theory = bool(topic_theory_content and topic_theory_content.strip())

            # Buscar TopicContent de tipo 'text'
            db = get_db()
            text_contents = list(db.topic_contents.find({
                "topic_id": ObjectId(topic_id),
                "content_type": "text"
            }))

            # Analizar inconsistencias
            inconsistencies = []
            recommendations = []

            if has_topic_theory and text_contents:
                inconsistencies.append({
                    "type": "redundant_text_content",
                    "description": f"Existen {len(text_contents)} TopicContent de tipo 'text' cuando ya hay theory_content en Topic",
                    "severity": "warning",
                    "count": len(text_contents)
                })
                recommendations.append("Ejecutar cleanup_redundant_text_content() para eliminar duplicados")

            if not has_topic_theory and not text_contents:
                inconsistencies.append({
                    "type": "no_theoretical_content",
                    "description": "No hay contenido teórico ni en Topic.theory_content ni en TopicContent",
                    "severity": "info"
                })

            # Verificar contenidos '[object Object]' en theory_content
            if has_topic_theory and topic_theory_content in ['[object Object]', '[Object object]', 'undefined', 'null']:
                inconsistencies.append({
                    "type": "invalid_theory_content",
                    "description": f"theory_content contiene valor inválido: '{topic_theory_content}'",
                    "severity": "error"
                })
                recommendations.append("Actualizar theory_content con contenido válido")

            # Verificar duplicación de contenido con lógica mejorada
            if has_topic_theory and text_contents:
                for text_content in text_contents:
                    # Enhanced duplicate extraction logic - try fields in order
                    content_text = ""

                    # Try 'content' field first
                    if "content" in text_content and text_content["content"] is not None:
                        content_text = str(text_content["content"])
                    # Try 'content_text' field next
                    elif "content_text" in text_content and text_content["content_text"] is not None:
                        content_text = str(text_content["content_text"])
                    # Try 'content_data.text' if content_data is a dict
                    elif "content_data" in text_content and isinstance(text_content["content_data"], dict):
                        content_data = text_content["content_data"]
                        if "text" in content_data and content_data["text"] is not None:
                            content_text = str(content_data["text"])

                    # Compare with topic theory content
                    if content_text == topic_theory_content:
                        inconsistencies.append({
                            "type": "exact_duplicate",
                            "description": f"TopicContent {text_content['_id']} tiene contenido idéntico a theory_content",
                            "severity": "warning",
                            "content_id": str(text_content["_id"])
                        })

            # Determinar estado general
            has_errors = any(inc["severity"] == "error" for inc in inconsistencies)
            has_warnings = any(inc["severity"] == "warning" for inc in inconsistencies)

            return {
                "valid": not has_errors,
                "topic_id": topic_id,
                "has_topic_theory_content": has_topic_theory,
                "topic_theory_content_length": len(topic_theory_content) if has_topic_theory else 0,
                "text_content_count": len(text_contents),
                "inconsistencies": inconsistencies,
                "recommendations": recommendations,
                "summary": {
                    "errors": len([inc for inc in inconsistencies if inc["severity"] == "error"]),
                    "warnings": len([inc for inc in inconsistencies if inc["severity"] == "warning"]),
                    "info": len([inc for inc in inconsistencies if inc["severity"] == "info"])
                }
            }

        except Exception as e:
            logging.error(f"validate_theory_content_integrity: Error para topic {topic_id}: {str(e)}")
            return {
                "valid": False,
                "error": f"Error en validación: {str(e)}",
                "topic_id": topic_id
            }

    def check_publish_prerequisites(self, topic_id: str) -> Dict[str, Any]:
        """
        Verifica si un tema cumple con los requisitos para ser publicado.

        Args:
            topic_id: ID del tema a verificar

        Returns:
            Diccionario con información sobre los requisitos de publicación:
            - meets_requirements: bool, indica si cumple todos los requisitos
            - missing_requirements: list, lista de requisitos faltantes
            - has_theory: bool, si tiene contenido teórico
            - has_complete_slides: bool, si tiene diapositivas completas
            - narrative_ready_slides: int, cantidad de diapositivas narrativas listas
            - has_evaluation: bool, si tiene evaluaciones asociadas
        """
        try:
            from bson import ObjectId
            from bson.errors import InvalidId

            # Validar ID
            try:
                topic_obj_id = ObjectId(topic_id)
            except InvalidId:
                return {
                    "meets_requirements": False,
                    "error": "ID de topic inválido",
                    "topic_id": topic_id
                }

            # Obtener el tema
            topic = self.collection.find_one({"_id": topic_obj_id})
            if not topic:
                return {
                    "meets_requirements": False,
                    "error": "Tema no encontrado",
                    "topic_id": topic_id
                }

            db = get_db()

            # Evaluar condiciones
            has_theory = bool(topic.get("theory_content"))

            # Contar diapositivas en estado narrative_ready
            narrative_ready_count = db.topic_contents.count_documents({
                "topic_id": topic_obj_id,
                "content_type": "slide",
                "status": "narrative_ready"
            })
            has_complete_slides = narrative_ready_count > 0

            # Verificar si tiene evaluaciones asociadas
            has_evaluation = db.evaluations.count_documents({"topic_ids": topic_obj_id}) > 0

            # Identificar requisitos faltantes
            missing_requirements = []
            if not has_theory:
                missing_requirements.append("theory_content")
            if not has_complete_slides:
                missing_requirements.append("narrative_ready_slide")
            if not has_evaluation:
                missing_requirements.append("evaluation_quiz")

            meets_requirements = len(missing_requirements) == 0

            return {
                "meets_requirements": meets_requirements,
                "missing_requirements": missing_requirements,
                "has_theory": has_theory,
                "has_complete_slides": has_complete_slides,
                "narrative_ready_slides": narrative_ready_count,
                "has_evaluation": has_evaluation,
                "already_published": bool(topic.get("published", False)),
                "topic_id": topic_id
            }

        except Exception as e:
            logging.error(f"check_publish_prerequisites: Error para topic {topic_id}: {str(e)}")
            return {
                "meets_requirements": False,
                "error": f"Error interno: {str(e)}",
                "topic_id": topic_id
            }

    def publish_topic(self, topic_id: str, user_id: str = None) -> Dict[str, Any]:
        """
        Publica un tema si cumple con los requisitos necesarios.

        Args:
            topic_id: ID del tema a publicar
            user_id: ID del usuario que realiza la acción (opcional, para logging)

        Returns:
            Diccionario con el resultado de la operación:
            - success: bool, si la operación fue exitosa
            - published: bool, estado final de publicación
            - auto_published: bool, si fue publicado automáticamente
            - message: str, mensaje descriptivo
            - error: str, error si ocurrió alguno
        """
        try:
            from bson import ObjectId
            from bson.errors import InvalidId
            from datetime import datetime

            # Validar ID
            try:
                topic_obj_id = ObjectId(topic_id)
            except InvalidId:
                return {
                    "success": False,
                    "published": False,
                    "auto_published": False,
                    "error": "ID de topic inválido",
                    "topic_id": topic_id
                }

            # Verificar requisitos de publicación
            prerequisites = self.check_publish_prerequisites(topic_id)

            if not prerequisites.get("meets_requirements", False):
                return {
                    "success": False,
                    "published": prerequisites.get("already_published", False),
                    "auto_published": False,
                    "message": "Requisitos no cumplidos para publicación",
                    "missing_requirements": prerequisites.get("missing_requirements", []),
                    "topic_id": topic_id,
                    **prerequisites
                }

            # Si ya está publicado, retornar estado actual
            if prerequisites.get("already_published", False):
                return {
                    "success": True,
                    "published": True,
                    "auto_published": False,
                    "message": "El tema ya estaba publicado",
                    "reason": "already_published",
                    "topic_id": topic_id,
                    **prerequisites
                }

            # Publicar el tema - actualización atómica para evitar condiciones de carrera
            db = get_db()
            try:
                update_data = {
                    "published": True,
                    "updated_at": datetime.now()
                }

                # Añadir timestamp de auto-publicación si se proporciona user_id
                if user_id:
                    update_data["auto_published_at"] = datetime.now()

                updated = db.topics.update_one(
                    {"_id": topic_obj_id, "published": {"$ne": True}},  # Solo actualizar si no está publicado
                    {"$set": update_data}
                )

                if updated.modified_count > 0:
                    logging.info(f"publish_topic: Tema {topic_id} publicado exitosamente" +
                               (f" por usuario {user_id}" if user_id else ""))
                    return {
                        "success": True,
                        "published": True,
                        "auto_published": True,
                        "message": "Tema publicado exitosamente",
                        "topic_id": topic_id,
                        **prerequisites
                    }
                else:
                    # Si no se modificó, puede deberse a condiciones de carrera
                    topic_after = self.collection.find_one({"_id": topic_obj_id})
                    return {
                        "success": True,
                        "published": topic_after.get("published", False) if topic_after else False,
                        "auto_published": False,
                        "message": "No se modificó el documento (posible condición de carrera)",
                        "note": "El tema puede haber sido publicado por otro proceso",
                        "topic_id": topic_id,
                        **prerequisites
                    }

            except Exception as e:
                logging.error(f"publish_topic: Error al actualizar topic {topic_id}: {str(e)}")
                return {
                    "success": False,
                    "published": False,
                    "auto_published": False,
                    "error": f"Error al actualizar tema: {str(e)}",
                    "topic_id": topic_id
                }

        except Exception as e:
            logging.error(f"publish_topic: Error procesando publicación para topic {topic_id}: {str(e)}")
            return {
                "success": False,
                "published": False,
                "auto_published": False,
                "error": f"Error interno: {str(e)}",
                "topic_id": topic_id
            }

class EvaluationService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="evaluations")

    def create_evaluation(self, evaluation_data: dict) -> Tuple[bool, str]:
        try:
            topic_ids = evaluation_data.get('topic_ids')
            if not topic_ids or not isinstance(topic_ids, list):
                return False, "topic_ids es requerido y debe ser una lista"

            # Validar que todos los topics existen
            for tid in topic_ids:
                if not get_db().topics.find_one({"_id": ObjectId(tid)}):
                    return False, f"El tema con ID {tid} no fue encontrado"
            
            # Validar y procesar weightings para evaluaciones multi-temáticas
            weightings = evaluation_data.get('weightings', {})
            if weightings:
                # Validar que los topic_ids en weightings coincidan con topic_ids
                for topic_id in weightings.keys():
                    if topic_id not in topic_ids:
                        return False, f"El topic_id {topic_id} en weightings no está en topic_ids"
                # Validar que la suma de pesos sea 1.0 (100%)
                total_weight = sum(weightings.values())
                if abs(total_weight - 1.0) > 0.01:  # Tolerancia para errores de punto flotante
                    return False, f"La suma de weightings debe ser 1.0, actual: {total_weight}"
            else:
                # Si no se proporcionan weightings, distribuir equitativamente
                weight_per_topic = 1.0 / len(topic_ids)
                weightings = {tid: weight_per_topic for tid in topic_ids}
            
            # Crear una copia con los datos necesarios para el constructor
            evaluation_dict = {
                "topic_ids": topic_ids,
                "title": evaluation_data.get("title"),
                "description": evaluation_data.get("description", ""),
                "weight": evaluation_data.get("weight", 0),
                "criteria": evaluation_data.get("criteria", []),
                "weightings": weightings,
                "rubric": evaluation_data.get("rubric", {}),
                # due_date se manejará a continuación
            }
            
            # Opciones de evaluación avanzada
            evaluation_dict["use_quiz_score"] = evaluation_data.get("use_quiz_score", False)
            evaluation_dict["requires_submission"] = evaluation_data.get("requires_submission", False)
            evaluation_dict["auto_grading"] = evaluation_data.get("auto_grading", False)
            if "linked_quiz_id" in evaluation_data:
                evaluation_dict["linked_quiz_id"] = evaluation_data.get("linked_quiz_id")
            
            # ---- Inicio: Manejo de due_date ----
            due_date_str = evaluation_data.get("due_date")
            if isinstance(due_date_str, str):
                try:
                    normalized_due_date = due_date_str.replace("Z", "+00:00") if due_date_str.endswith("Z") else due_date_str
                    evaluation_dict["due_date"] = datetime.fromisoformat(normalized_due_date)
                except ValueError:
                    logging.error(f"Formato de due_date invalido: {due_date_str}")
                    return False, f"Formato de due_date invalido: {due_date_str}"
            elif isinstance(due_date_str, datetime):
                evaluation_dict["due_date"] = due_date_str  # Ya es datetime
            else:
                return False, "due_date es requerida y debe ser string ISO 8601 o datetime"
            # ---- Fin: Manejo de due_date ----

            # Crear la evaluación con parámetros exactos
            evaluation = Evaluation(**evaluation_dict)
            
            # Obtener el diccionario y agregar timestamps
            evaluation_to_insert = evaluation.to_dict()
            evaluation_to_insert['created_at'] = datetime.now()
            evaluation_to_insert['updated_at'] = datetime.now()
            
            result = self.collection.insert_one(evaluation_to_insert)
            
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
    
    def update_evaluation(self, evaluation_id: str, update_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que la evaluación existe
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return False, "Evaluación no encontrada"
            
            # Validar que todos los topics existen si se actualiza topic_ids
            if 'topic_ids' in update_data:
                topic_ids = update_data.get('topic_ids')
                if not topic_ids or not isinstance(topic_ids, list):
                    return False, "topic_ids debe ser una lista no vacía"
                for tid in topic_ids:
                    if not get_db().topics.find_one({"_id": ObjectId(tid)}):
                        return False, f"El tema con ID {tid} no fue encontrado"
                update_data['topic_ids'] = [ObjectId(tid) for tid in topic_ids]
            
            # Validar weightings si se actualiza
            if 'weightings' in update_data:
                weightings = update_data.get('weightings')
                # Obtener topic_ids actuales si no se están actualizando
                current_topic_ids = update_data.get('topic_ids', evaluation.get('topic_ids', []))
                if isinstance(current_topic_ids[0], ObjectId):
                    current_topic_ids = [str(tid) for tid in current_topic_ids]
                
                if weightings:
                    # Validar que los topic_ids en weightings coincidan
                    for topic_id in weightings.keys():
                        if topic_id not in current_topic_ids:
                            return False, f"El topic_id {topic_id} en weightings no está en topic_ids"
                    # Validar que la suma de pesos sea 1.0 (100%)
                    total_weight = sum(weightings.values())
                    if abs(total_weight - 1.0) > 0.01:
                        return False, f"La suma de weightings debe ser 1.0, actual: {total_weight}"
            
            # Manejo de linked_quiz_id para actualización de evaluación
            if 'linked_quiz_id' in update_data and isinstance(update_data['linked_quiz_id'], str):
                update_data['linked_quiz_id'] = ObjectId(update_data['linked_quiz_id'])

            if 'auto_grading' in update_data:
                update_data['auto_grading'] = bool(update_data['auto_grading'])

            # ---- Inicio: Manejo de due_date en actualización ----
            if 'due_date' in update_data:
                due_date_str = update_data['due_date']
                if isinstance(due_date_str, str):
                    try:
                        update_data['due_date'] = datetime.fromisoformat(due_date_str)
                        logging.info(f"Parsed due_date string to datetime during update for evaluation {evaluation_id}")
                    except ValueError:
                        logging.error(f"Formato de due_date inválido al actualizar: {due_date_str}")
                        return False, f"Formato de due_date inválido: {due_date_str}"
                elif not isinstance(due_date_str, datetime):
                    # Si no es string ni datetime, es un tipo inválido
                    return False, f"Tipo de due_date inválido: {type(due_date_str)}"
            # ---- Fin: Manejo de due_date en actualización ----

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
    
    def delete_evaluation(self, evaluation_id: str, cascade: bool = False) -> Tuple[bool, str]:
        try:
            validate_object_id(evaluation_id)
            evaluation_id_obj = ObjectId(evaluation_id)
            db = get_db()

            evaluation = self.collection.find_one({"_id": evaluation_id_obj})
            if not evaluation:
                return False, "Evaluación no encontrada"

            resources_count = db.evaluation_resources.count_documents({"evaluation_id": evaluation_id_obj})
            submissions_count = db.evaluation_submissions.count_documents({"evaluation_id": evaluation_id_obj})
            results_count = db.evaluation_results.count_documents({"evaluation_id": evaluation_id_obj})
            content_results_count = db.content_results.count_documents({"evaluation_id": evaluation_id_obj})

            if not cascade:
                if any([resources_count, submissions_count, results_count, content_results_count]):
                    return False, (
                        "No se puede eliminar la evaluación porque tiene dependencias: "
                        f"{resources_count} recurso(s), {submissions_count} entrega(s), "
                        f"{results_count} resultado(s) registrado(s) y {content_results_count} contenido(s) relacionado(s)."
                    )

                result = self.collection.delete_one({"_id": evaluation_id_obj})
                if result.deleted_count > 0:
                    return True, "Evaluación eliminada exitosamente"
                return False, "No se pudo eliminar la evaluación"

            cascade_service = CascadeDeletionService()
            cascade_result = cascade_service.delete_with_cascade('evaluations', evaluation_id)
            if not cascade_result.get('success', False):
                return False, cascade_result.get('error', 'No se pudo eliminar la evaluación en cascada')

            total_deleted = cascade_result.get('total_deleted', 1)
            dependencies_deleted = max(total_deleted - 1, 0)
            if dependencies_deleted > 0:
                return True, f"Evaluación eliminada junto con {dependencies_deleted} dependencias"
            return True, "Evaluación eliminada exitosamente"
        except Exception as e:
            logging.error(f"Error al eliminar evaluación {evaluation_id}: {e}")
            return False, str(e)
    
    def get_evaluation(self, evaluation_id: str) -> Optional[Dict]:
        try:
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return None

            # Convertir ObjectId a string
            evaluation['_id'] = str(evaluation['_id'])
            if 'topic_ids' in evaluation:
                evaluation['topic_ids'] = [str(tid) for tid in evaluation['topic_ids']]

            return evaluation
        except Exception as e:
            return None

    def get_evaluations_by_topic(self, topic_id: str) -> List[Dict]:
        """Lista todas las evaluaciones asociadas a un tema específico."""
        try:
            evaluations = list(self.collection.find({"topic_ids": ObjectId(topic_id)}))
            for ev in evaluations:
                ev["_id"] = str(ev["_id"])
                ev["topic_ids"] = [str(tid) for tid in ev["topic_ids"]]
            return evaluations
        except Exception:
            return []

    def get_evaluations_status_for_student(self, topic_id: str, student_id: str) -> List[Dict]:
        """Obtiene evaluaciones de un tema con estado para un estudiante."""
        try:
            evaluations = self.get_evaluations_by_topic(topic_id)
            db = get_db()
            results = []
            for ev in evaluations:
                submission = db.evaluation_submissions.find_one({
                    "evaluation_id": ObjectId(ev["_id"]),
                    "student_id": student_id
                })

                status = {
                    "evaluation": ev,
                    "submitted": submission is not None,
                    "submitted_at": submission.get("updated_at") if submission else None,
                    "grade": submission.get("grade") if submission else None,
                    "feedback": submission.get("feedback") if submission else None
                }

                results.append(status)

            return results
        except Exception:
            return []
    
    def record_result(self, result_data: dict) -> Tuple[bool, str]:
        """
        Registra la calificación de una evaluación, ya sea por score directo o
        basado en una entrega (submission) que es un Recurso.
        Utiliza el servicio unificado de ContentResult.
        """
        try:
            evaluation_id = result_data.get("evaluation_id")
            student_id = result_data.get("student_id")
            graded_by = result_data.get("graded_by")

            if not self.check_evaluation_exists(evaluation_id):
                return False, "Evaluación no encontrada"
            if not self.check_student_exists(student_id):
                return False, "Estudiante no encontrado"
            if not self.check_teacher_exists(graded_by):
                return False, "Evaluador no encontrado"

            # Si el resultado viene de una 'submission', esta será el ID de un Recurso
            submission_resource_id = result_data.get("submission_resource_id")
            
            # Preparar datos para ContentResult
            unified_result_data = {
                "content_id": evaluation_id, # La evaluación es el "contenido"
                "student_id": student_id,
                "score": result_data.get("score") / 100.0 if result_data.get("score") is not None else None, # Normalizar a 0-1
                "feedback": result_data.get("feedback"),
                "session_type": "assessment",
                "recorded_at": datetime.now(),
                "metrics": {
                    "graded_by": graded_by,
                    "is_submission": bool(submission_resource_id)
                }
            }

            if submission_resource_id:
                unified_result_data["metrics"]["submission_resource_id"] = submission_resource_id
            
            # TODO: Implementar ContentResultService
            # content_result_service = ContentResultService()
            # success, result_id_or_msg = content_result_service.record_result(unified_result_data)
            
            # Temporal hasta implementar ContentResultService
            return True, "result_id_placeholder"

        except Exception as e:
            logging.error(f"Error registrando resultado de evaluación: {str(e)}")
            return False, str(e)

    def update_result(self, result_id: str, update_data: dict) -> Tuple[bool, str]:
        """Actualiza un resultado de evaluación existente en la colección de ContentResult."""
        try:
            # TODO: Implementar ContentResultService
            # content_result_service = ContentResultService()
            # 
            # # Asegurarse de que el update_data no cambie el student_id o evaluation_id
            # update_data.pop("student_id", None)
            # update_data.pop("evaluation_id", None)
            # 
            # result = content_result_service.collection.update_one(
            #     {"_id": ObjectId(result_id)},
            #     {"$set": update_data}
            # )
            
            # Temporal hasta implementar ContentResultService
            if True:
                return True, "Resultado actualizado exitosamente"
            
            return False, "No se encontró el resultado o no hubo cambios"
        except Exception as e:
            return False, str(e)

    def delete_result(self, result_id: str) -> Tuple[bool, str]:
        """Elimina un resultado de la colección de ContentResult."""
        try:
            # TODO: Implementar ContentResultService
            # content_result_service = ContentResultService()
            # result = content_result_service.collection.delete_one({"_id": ObjectId(result_id)})
            # if result.deleted_count > 0:
            #     return True, "Resultado eliminado exitosamente"
            # return False, "No se encontró el resultado"
            
            # Temporal hasta implementar ContentResultService
            return True, "Resultado eliminado exitosamente"
        except Exception as e:
            return False, str(e)

    def get_student_results(self, student_id: str, topic_id: str = None) -> List[Dict]:
        """
        Obtiene los resultados de las evaluaciones de un estudiante para un tema.
        Utiliza el servicio unificado de ContentResult.
        """
        try:
            # Primero, obtener todas las evaluaciones del tema
            if not topic_id:
                raise ValueError("Se requiere un topic_id para buscar resultados de evaluación.")

            evaluations = list(self.collection.find({"topic_ids": ObjectId(topic_id)}))
            evaluation_ids = [str(e["_id"]) for e in evaluations]

            if not evaluation_ids:
                return []

            # TODO: Implementar ContentResultService
            # content_result_service = ContentResultService()
            # all_results = []
            # 
            # # Buscar un resultado para cada evaluación
            # for eval_id in evaluation_ids:
            #     results_for_eval = content_result_service.get_student_results(
            #         student_id=student_id,
            #         evaluation_id=eval_id
            #     )
            #     all_results.extend(results_for_eval)
            
            # Temporal hasta implementar ContentResultService
            all_results = []

            return all_results
        except Exception as e:
            logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
            return []
    
    def check_student_exists(self, student_id: str) -> bool:
        """Verifica si un estudiante existe."""
        try:
            student = get_db().users.find_one({"_id": ObjectId(student_id), "role": "STUDENT"})
            return student is not None
        except Exception:
            return False

    def check_teacher_exists(self, teacher_id: str) -> bool:
        """Verifica si un profesor existe."""
        try:
            teacher = get_db().users.find_one({"_id": ObjectId(teacher_id)})
            return teacher is not None
        except Exception:
            return False

    # ===== MÉTODOS PARA SUBMISSIONS (ENTREGAS) =====
    
    def create_submission(self, submission_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva entrega de estudiante para una evaluación.
        
        Args:
            submission_data: Datos de la entrega
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Validaciones básicas
            evaluation_id = submission_data.get("evaluation_id")
            student_id = submission_data.get("student_id")
            
            if not evaluation_id or not student_id:
                return False, "evaluation_id y student_id son requeridos"
            
            # Validar IDs
            validate_object_id(evaluation_id)
            
            # Verificar que la evaluación existe
            evaluation = self.collection.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return False, "Evaluación no encontrada"
            
            # Verificar que el estudiante existe (student_id puede ser string o ObjectId)
            db = get_db()
            student = None
            try:
                # Intentar buscar por ObjectId primero
                student = db.users.find_one({"_id": ObjectId(student_id)})
            except (TypeError, ValueError):
                # Si falla, buscar por string (email u otro identificador)
                student = db.users.find_one({"email": student_id}) or db.users.find_one({"_id": student_id})
            
            if not student:
                return False, "Estudiante no encontrado"
            
            # Verificar fecha límite si está configurada
            due_date = evaluation.get("due_date")
            is_late = False
            if due_date and isinstance(due_date, datetime):
                is_late = datetime.now() > due_date
                submission_data["is_late"] = is_late
            
            # Verificar si ya existe una entrega (usar student_id como string)
            existing_submission = db.evaluation_submissions.find_one({
                "evaluation_id": ObjectId(evaluation_id),
                "student_id": str(student["_id"])  # Usar el ID del estudiante encontrado como string
            })
            
            if existing_submission:
                # Incrementar número de intentos
                attempts = existing_submission.get("attempts", 1) + 1
                submission_data["attempts"] = attempts
                
                # Actualizar entrega existente
                submission_data["updated_at"] = datetime.now()
                submission_data["status"] = "resubmitted"
                
                result = db.evaluation_submissions.update_one(
                    {"_id": existing_submission["_id"]},
                    {"$set": submission_data}
                )
                
                return True, str(existing_submission["_id"])
            else:
                # Asegurar que student_id sea string para crear nueva entrega
                submission_data["student_id"] = str(student["_id"])
                
                # Crear nueva entrega
                submission = EvaluationSubmission(**submission_data)
                result = db.evaluation_submissions.insert_one(submission.to_dict())
                
                return True, str(result.inserted_id)
                
        except Exception as e:
            logging.error(f"Error creando submission: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_submissions_by_evaluation(self, evaluation_id: str) -> List[Dict]:
        """
        Obtiene todas las entregas de una evaluación específica.
        """
        try:
            # Validar el evaluation_id
            validate_object_id(evaluation_id)
            
            db = get_db()
            submissions = list(db.evaluation_submissions.find({
                "evaluation_id": ObjectId(evaluation_id)
            }))
            
            # Convertir ObjectIds y enriquecer con datos de estudiante
            for submission in submissions:
                submission["_id"] = str(submission["_id"])
                submission["evaluation_id"] = str(submission["evaluation_id"])
                
                # Asegurar que student_id sea string
                if isinstance(submission["student_id"], ObjectId):
                    submission["student_id"] = str(submission["student_id"])
                
                # Agregar información del estudiante
                student = None
                try:
                    # Intentar buscar por ObjectId si student_id puede convertirse
                    student = db.users.find_one({"_id": ObjectId(submission["student_id"])})
                except (TypeError, ValueError):
                    # Si falla, buscar por string
                    student = db.users.find_one({"_id": submission["student_id"]})
                
                if student:
                    submission["student"] = {
                        "name": student.get("name", ""),
                        "email": student.get("email", ""),
                        "picture": student.get("picture", "")
                    }
                
                # Agregar información del evaluador si existe
                if submission.get("graded_by"):
                    try:
                        grader = db.users.find_one({"_id": ObjectId(submission["graded_by"])})
                        if grader:
                            submission["grader"] = {
                                "name": grader.get("name", ""),
                                "email": grader.get("email", "")
                            }
                    except Exception as e:
                        logging.warning(f"Error obteniendo datos del evaluador: {e}")
            
            return submissions
            
        except Exception as e:
            logging.error(f"Error obteniendo submissions: {str(e)}")
            return []
    
    def get_submissions_by_evaluation_and_student(self, evaluation_id: str, student_id: str) -> List[Dict]:
        """
        Obtiene las entregas de una evaluación específica filtradas por estudiante.
        """
        try:
            # Validar el evaluation_id
            validate_object_id(evaluation_id)
            
            db = get_db()
            submissions = list(db.evaluation_submissions.find({
                "evaluation_id": ObjectId(evaluation_id),
                "student_id": student_id
            }))
            
            # Convertir ObjectIds y enriquecer con datos de estudiante
            for submission in submissions:
                submission["_id"] = str(submission["_id"])
                submission["evaluation_id"] = str(submission["evaluation_id"])
                
                # Asegurar que student_id sea string
                if isinstance(submission["student_id"], ObjectId):
                    submission["student_id"] = str(submission["student_id"])
                
                # Agregar información del estudiante
                student = None
                try:
                    # Intentar buscar por ObjectId si student_id puede convertirse
                    student = db.users.find_one({"_id": ObjectId(submission["student_id"])})
                except (TypeError, ValueError):
                    # Si falla, buscar por string
                    student = db.users.find_one({"_id": submission["student_id"]})
                
                if student:
                    submission["student"] = {
                        "name": student.get("name", ""),
                        "email": student.get("email", ""),
                        "picture": student.get("picture", "")
                    }
                
                # Agregar información del evaluador si existe
                if submission.get("graded_by"):
                    try:
                        grader = db.users.find_one({"_id": ObjectId(submission["graded_by"])})
                        if grader:
                            submission["grader"] = {
                                "name": grader.get("name", ""),
                                "email": grader.get("email", "")
                            }
                    except Exception as e:
                        logging.warning(f"Error obteniendo datos del evaluador: {e}")
            
            return submissions
            
        except Exception as e:
            logging.error(f"Error obteniendo submissions por estudiante: {str(e)}")
            return []
    
    def get_submission_by_student(self, evaluation_id: str, student_id: str) -> Optional[Dict]:
        """
        Obtiene la entrega de un estudiante específico para una evaluación.
        """
        try:
            # Validar el evaluation_id
            validate_object_id(evaluation_id)
            
            # Buscar primero con student_id como string (storage format)
            submission = get_db().evaluation_submissions.find_one({
                "evaluation_id": ObjectId(evaluation_id),
                "student_id": student_id  # Keep as string to match database storage
            })
            
            # Si no se encuentra, intentar con ObjectId por compatibilidad con datos antiguos
            if not submission:
                try:
                    submission = get_db().evaluation_submissions.find_one({
                        "evaluation_id": ObjectId(evaluation_id),
                        "student_id": ObjectId(student_id)
                    })
                except (TypeError, ValueError):
                    # Si student_id no puede convertirse a ObjectId, mantener como None
                    pass
            
            if not submission:
                return None
            
            # Convertir ObjectIds a strings para serialización
            submission["_id"] = str(submission["_id"])
            submission["evaluation_id"] = str(submission["evaluation_id"])
            # student_id ya debería ser string, pero asegurar conversión si es ObjectId
            if isinstance(submission["student_id"], ObjectId):
                submission["student_id"] = str(submission["student_id"])
            
            return submission
            
        except Exception as e:
            logging.error(f"Error obteniendo submission del estudiante: {str(e)}")
            return None
    
    def grade_submission(self, submission_id: str, grade_data: dict) -> Tuple[bool, str]:
        """
        Califica una entrega de estudiante.
        
        Args:
            submission_id: ID de la entrega
            grade_data: Datos de calificación (grade, feedback, graded_by)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Validar el submission_id
            validate_object_id(submission_id)
            
            db = get_db()
            # Verificar que la entrega existe
            submission = db.evaluation_submissions.find_one({"_id": ObjectId(submission_id)})
            if not submission:
                return False, "Entrega no encontrada"
            
            # Datos de calificación
            grade_update = {
                "grade": grade_data.get("grade"),
                "feedback": grade_data.get("feedback", ""),
                "graded_by": ObjectId(grade_data["graded_by"]) if grade_data.get("graded_by") else None,
                "graded_at": datetime.now(),
                "status": "graded",
                "updated_at": datetime.now()
            }
            
            # Validar calificación
            if grade_update["grade"] is not None:
                if not (0 <= grade_update["grade"] <= 100):
                    return False, "La calificación debe estar entre 0 y 100"
            
            # Actualizar entrega
            result = db.evaluation_submissions.update_one(
                {"_id": ObjectId(submission_id)},
                {"$set": grade_update}
            )
            
            if result.modified_count > 0:
                # Crear ContentResult si la evaluación está vinculada a contenido virtual
                evaluation = self.collection.find_one({"_id": submission["evaluation_id"]})
                if evaluation and evaluation.get("linked_quiz_id"):
                    self._create_content_result_from_submission(submission, grade_update)
                
                # Persistir evaluation_results para dashboards/analytics
                try:
                    db.evaluation_results.update_one(
                        {
                            "evaluation_id": submission["evaluation_id"],
                            "student_id": submission["student_id"]
                        },
                        {
                            "$set": {
                                "evaluation_id": submission["evaluation_id"],
                                "student_id": submission["student_id"],
                                "score": grade_update.get("grade"),
                                "source": "manual",
                                "status": "graded",
                                "submission_id": ObjectId(submission_id),
                                "recorded_at": datetime.now()
                            }
                        },
                        upsert=True
                    )
                except Exception as e:
                    logging.error(f"Error guardando evaluation_results (study_plans.grade_submission): {str(e)}")
                
                return True, "Entrega calificada exitosamente"
            
            return False, "No se pudo calificar la entrega"
            
        except Exception as e:
            logging.error(f"Error calificando submission: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    # ===== MÉTODOS PARA RUBRICS =====
    
    def create_rubric(self, rubric_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva rúbrica de evaluación.
        """
        try:
            # Validar criterios si se proporcionan
            criteria = rubric_data.get("criteria", [])
            if criteria:
                for i, criterion in enumerate(criteria):
                    if not criterion.get("id"):
                        criterion["id"] = f"criterion_{i+1}"
                    if not criterion.get("name"):
                        return False, f"Criterio {i+1} debe tener nombre"
                    if not isinstance(criterion.get("points", 0), (int, float)):
                        return False, f"Criterio {i+1} debe tener puntos válidos"
            
            rubric = EvaluationRubric(**rubric_data)
            result = get_db().evaluation_rubrics.insert_one(rubric.to_dict())
            
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error creando rubric: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_rubric_by_evaluation(self, evaluation_id: str) -> Optional[Dict]:
        """
        Obtiene la rúbrica asociada a una evaluación.
        """
        try:
            # Validar el evaluation_id
            validate_object_id(evaluation_id)
            
            rubric = get_db().evaluation_rubrics.find_one({
                "evaluation_id": ObjectId(evaluation_id)
            })
            
            if not rubric:
                return None
            
            # Convertir ObjectIds
            rubric["_id"] = str(rubric["_id"])
            rubric["evaluation_id"] = str(rubric["evaluation_id"])
            
            return rubric
            
        except Exception as e:
            logging.error(f"Error obteniendo rubric: {str(e)}")
            return None
    
    def calculate_grade_with_rubric(self, rubric_id: str, criteria_scores: Dict[str, float]) -> Dict:
        """
        Calcula una calificación usando una rúbrica específica.
        """
        try:
            # Validar el rubric_id
            validate_object_id(rubric_id)
            
            # Obtener rúbrica
            rubric_data = get_db().evaluation_rubrics.find_one({"_id": ObjectId(rubric_id)})
            if not rubric_data:
                return {"error": "Rúbrica no encontrada"}
            
            # Recrear objeto para usar método calculate_grade
            rubric = EvaluationRubric(**rubric_data)
            result = rubric.calculate_grade(criteria_scores)
            
            return result
            
        except Exception as e:
            logging.error(f"Error calculando calificación con rubric: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    # ===== MÉTODOS DE INTEGRACIÓN =====
    
    def _create_content_result_from_submission(self, submission: Dict, grade_data: Dict):
        """
        Crea un ContentResult basado en una entrega calificada.
        Integra las evaluaciones con el sistema de contenidos virtuales.
        """
        try:
            # TODO: Implementar ContentResultService
            # from src.content.services import ContentResultService
            
            # Solo crear si hay calificación válida
            if grade_data.get("grade") is None:
                return
            
            # Datos para ContentResult
            content_result_data = {
                "content_id": str(submission["evaluation_id"]),  # Usar evaluation como content
                "student_id": str(submission["student_id"]),
                "score": grade_data["grade"] / 100.0,  # Normalizar a 0-1
                "feedback": grade_data.get("feedback", ""),
                "metrics": {
                    "submission_type": submission.get("submission_type", "file"),
                    "attempts": submission.get("attempts", 1),
                    "is_late": submission.get("is_late", False),
                    "graded_at": grade_data.get("graded_at").isoformat() if grade_data.get("graded_at") else None
                },
                "session_type": "evaluation_submission"
            }
            
            # TODO: Implementar ContentResultService
            # content_result_service = ContentResultService()
            # success, result_id = content_result_service.record_result(content_result_data)
            # 
            # if success:
            #     logging.info(f"ContentResult creado: {result_id} para submission {submission['_id']}")
            # else:
            #     logging.warning(f"No se pudo crear ContentResult: {result_id}")
            
            # Temporal hasta implementar ContentResultService
            logging.info(f"ContentResult temporal para submission {submission['_id']}")
                
        except Exception as e:
            logging.error(f"Error creando ContentResult desde submission: {str(e)}")
    
    def get_evaluation_statistics(self, evaluation_id: str) -> Dict:
        """
        Obtiene estadísticas completas de una evaluación.
        """
        try:
            # Obtener todas las entregas
            submissions = self.get_submissions_by_evaluation(evaluation_id)
            
            if not submissions:
                return {
                    "total_submissions": 0,
                    "graded_submissions": 0,
                    "pending_submissions": 0,
                    "average_grade": 0,
                    "grade_distribution": {},
                    "late_submissions": 0
                }
            
            # Calcular estadísticas
            total = len(submissions)
            graded = len([s for s in submissions if s.get("grade") is not None])
            pending = total - graded
            late = len([s for s in submissions if s.get("is_late", False)])
            
            # Calcular promedio de calificaciones
            grades = [s["grade"] for s in submissions if s.get("grade") is not None]
            average_grade = sum(grades) / len(grades) if grades else 0
            
            # Distribución de calificaciones
            grade_distribution = {
                "A (90-100)": len([g for g in grades if g >= 90]),
                "B (80-89)": len([g for g in grades if 80 <= g < 90]),
                "C (70-79)": len([g for g in grades if 70 <= g < 80]),
                "D (60-69)": len([g for g in grades if 60 <= g < 70]),
                "F (0-59)": len([g for g in grades if g < 60])
            }
            
            return {
                "total_submissions": total,
                "graded_submissions": graded,
                "pending_submissions": pending,
                "average_grade": round(average_grade, 2),
                "grade_distribution": grade_distribution,
                "late_submissions": late,
                "completion_rate": round((graded / total) * 100, 2) if total > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo estadísticas de evaluación: {str(e)}")
            return {}

class ContentTypeService(VerificationBaseService):
    """
    Servicio para gestionar los tipos de contenido del sistema.
    """
    def __init__(self):
        super().__init__(collection_name="content_types")
        
    def create_content_type(self, content_type_data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo tipo de contenido en el catálogo.
        
        Args:
            content_type_data: Datos del tipo de contenido a crear
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar si ya existe un tipo de contenido con el mismo código
            existing = self.collection.find_one({"code": content_type_data.get("code")})
            if existing:
                return False, "Ya existe un tipo de contenido con ese código"
                
            # Crear objeto y obtener diccionario para inserción
            content_type = ContentType(**content_type_data)
            result = self.collection.insert_one(content_type.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al crear tipo de contenido: {str(e)}")
            return False, str(e)
            
    def list_content_types(self) -> List[Dict]:
        """
        Lista todos los tipos de contenido disponibles.
        
        Args:
            
        Returns:
            Lista de tipos de contenido
        """
        try:
            filter_query = {"status": "active"}
                
            content_types = list(self.collection.find(filter_query))
            
            # Convertir ObjectId a str para serialización
            for content_type in content_types:
                if "_id" in content_type:
                    content_type["_id"] = str(content_type["_id"])
                    
            return content_types
        except Exception as e:
            logging.error(f"Error al listar tipos de contenido: {str(e)}")
            return []
            
    def get_content_type(self, code: str) -> Optional[Dict]:
        """
        Obtiene un tipo de contenido por su código.
        
        Args:
            code: Código del tipo de contenido
            
        Returns:
            Diccionario con datos del tipo de contenido o None si no existe
        """
        try:
            if not code:
                return None

            normalized_code = code.strip().lower()

            if normalized_code == "slide_template":
                return {
                    "code": "slide_template",
                    "name": "Slide Template",
                    "description": "Plantilla base reutilizable para contenido de diapositivas",
                    "status": "active",
                    "subcategory": "template",
                    "builtin": True
                }

            content_type = self.collection.find_one({"code": normalized_code, "status": "active"})
            if not content_type:
                return None
                
            # Convertir ObjectId a str para serialización
            if "_id" in content_type:
                content_type["_id"] = str(content_type["_id"])
                
            return content_type
        except Exception as e:
            logging.error(f"Error al obtener tipo de contenido: {str(e)}")
            return None

class LearningMethodologyService(VerificationBaseService):
    """
    Servicio para gestionar las metodologías de aprendizaje.
    """
    def __init__(self):
        super().__init__(collection_name="learning_methodologies")
        
    def create_methodology(self, methodology_data: dict) -> Tuple[bool, str]:
        """
        Crea una nueva metodología de aprendizaje.
        
        Args:
            methodology_data: Datos de la metodología a crear
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # Verificar si ya existe una metodología con el mismo código
            existing = self.collection.find_one({"code": methodology_data.get("code")})
            if existing:
                return False, "Ya existe una metodología con ese código"
                
            # Crear objeto y obtener diccionario para inserción
            methodology = LearningMethodology(**methodology_data)
            result = self.collection.insert_one(methodology.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error al crear metodología: {str(e)}")
            return False, str(e)
            
    def list_methodologies(self) -> List[Dict]:
        """
        Lista todas las metodologías de aprendizaje disponibles.
        
        Returns:
            Lista de metodologías
        """
        try:
            methodologies = list(self.collection.find({"status": "active"}))
            
            # Convertir ObjectId a str para serialización
            for methodology in methodologies:
                if "_id" in methodology:
                    methodology["_id"] = str(methodology["_id"])
                    
            return methodologies
        except Exception as e:
            logging.error(f"Error al listar metodologías: {str(e)}")
            return []
            
    def get_methodology(self, code: str) -> Optional[Dict]:
        """
        Obtiene una metodología por su código.
        
        Args:
            code: Código de la metodología
            
        Returns:
            Diccionario con datos de la metodología o None si no existe
        """
        try:
            methodology = self.collection.find_one({"code": code, "status": "active"})
            if not methodology:
                return None
                
            # Convertir ObjectId a str para serialización
            if "_id" in methodology:
                methodology["_id"] = str(methodology["_id"])
                
            return methodology
        except Exception as e:
            logging.error(f"Error al obtener metodología: {str(e)}")
            return None
            
    def get_compatible_methodologies(self, cognitive_profile: Dict) -> List[Dict]:
        """
        Obtiene las metodologías compatibles con un perfil cognitivo.
        
        Args:
            cognitive_profile: Perfil cognitivo del estudiante
            
        Returns:
            Lista de metodologías compatibles ordenadas por relevancia
        """
        try:
            methodologies = self.list_methodologies()
            
            # Calcular puntuación de compatibilidad para cada metodología
            scored_methodologies = []
            for methodology in methodologies:
                score = 0
                profile_match = methodology.get("cognitive_profile_match", {})
                
                # Calcular puntuación basada en coincidencias del perfil
                for profile_key, profile_value in cognitive_profile.items():
                    if profile_key in profile_match:
                        # Mayor valor en profile_match indica mayor compatibilidad
                        match_value = profile_match[profile_key]
                        score += match_value * profile_value
                        
                methodology["compatibility_score"] = score
                scored_methodologies.append(methodology)
                
            # Ordenar por puntuación de compatibilidad (descendente)
            return sorted(scored_methodologies, key=lambda m: m["compatibility_score"], reverse=True)
        except Exception as e:
            logging.error(f"Error al obtener metodologías compatibles: {str(e)}")
            return []

class TopicContentService(VerificationBaseService):
    """
    Servicio para la gestión de contenidos por tipo en topics
    """
    def __init__(self):
        super().__init__(collection_name="topic_contents")
        self.content_type_service = ContentTypeService()
        
    def create_content(self, data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo contenido para un tema.
        
        Args:
            data: Datos del contenido a crear, directamente desde el JSON del request.
            
        Returns:
            Tupla con estado y mensaje/ID
        """
        try:
            # 1. Validaciones de datos de entrada
            topic_id = data.get("topic_id")
            if not topic_id:
                return False, "Falta topic_id"
            
            content_type = data.get("content_type")
            if not content_type:
                return False, "Falta content_type"
            
            content_payload = data.get("content")
            if content_payload is None:
                return False, "Falta el campo 'content'"

            # 2. Validaciones de existencia en la BD
            topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, "Tema no encontrado"

            if not self.content_type_service.get_content_type(content_type):
                return False, f"Tipo de contenido '{content_type}' no válido"

            # 3. Mapeo y preparación de datos para el constructor
            learning_methodologies = []
            methodology = data.get('methodology')
            if methodology:
                learning_methodologies.append(methodology)

            # DIAGNÓSTICO: Registrar la firma del constructor de TopicContent
            try:
                logging.info(f"DIAGNOSTIC: TopicContent constructor signature: {inspect.signature(TopicContent)}")
            except Exception as inspect_e:
                logging.error(f"DIAGNOSTIC: Could not inspect TopicContent signature: {inspect_e}")

            # 4. Creación explícita del objeto TopicContent
            # Se llama al constructor con argumentos nombrados para evitar errores de **kwargs.
            topic_content = TopicContent(
                topic_id=topic_id,
                content=content_payload,
                content_type=content_type,
                status=data.get('status', 'draft'),
                ai_credits=data.get('ai_credits', True),
                generation_prompt=data.get('generation_prompt'),
                learning_methodologies=learning_methodologies,
                adaptation_options=data.get('metadata')
            )
            
            # 5. Inserción en la base de datos
            result = self.collection.insert_one(topic_content.to_dict())
            
            return True, str(result.inserted_id)
        except TypeError as e:
            # Este log es crucial para depurar si el error persiste.
            logging.error(f"Error de tipo al instanciar TopicContent: {str(e)}. Datos recibidos: {data}")
            return False, f"Error interno del servidor al procesar la solicitud: {str(e)}"
        except Exception as e:
            logging.error(f"Error general al crear contenido para tema: {str(e)}")
            return False, str(e)
            
    def get_topic_contents(self, topic_id: str) -> List[Dict]:
        """
        Obtiene todos los contenidos asociados a un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Lista de contenidos
        """
        try:
            contents = list(self.collection.find({"topic_id": ObjectId(topic_id)}))
            
            # Convertir ObjectId a str para serialización
            for content in contents:
                if "_id" in content:
                    content["_id"] = str(content["_id"])
                if "topic_id" in content:
                    content["topic_id"] = str(content["topic_id"])
                    
            return contents
        except Exception as e:
            logging.error(f"Error al obtener contenidos del tema: {str(e)}")
            return []
            
    def get_content(self, content_id: str) -> Optional[Dict]:
        """
        Obtiene un contenido específico por su ID.
        
        Args:
            content_id: ID del contenido
            
        Returns:
            Diccionario con datos del contenido o None si no existe
        """
        try:
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return None
                
            # Convertir ObjectId a str para serialización
            if "_id" in content:
                content["_id"] = str(content["_id"])
            if "topic_id" in content:
                content["topic_id"] = str(content["topic_id"])
                
            return content
        except Exception as e:
            logging.error(f"Error al obtener contenido: {str(e)}")
            return None
            
    def update_content(self, content_id: str, update_data: dict) -> Tuple[bool, str]:
        """
        Actualiza un contenido existente.
        
        Args:
            content_id: ID del contenido a actualizar
            update_data: Datos a actualizar
            
        Returns:
            Tupla con estado y mensaje
        """
        try:
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return False, "Contenido no encontrado"

            update_data['updated_at'] = datetime.now()
            
            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                # Disparar detección de cambios y encolar actualizaciones
                topic_id = str(content.get("topic_id"))
                topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
                if topic:
                    module_id = str(topic.get("module_id"))
                    try:
                        change_detector = ContentChangeDetector()
                        change_info = change_detector.detect_changes(module_id)
                        if change_info.get("has_changes"):
                            change_detector.schedule_incremental_updates(module_id, change_info)
                            logging.info(f"Cambios detectados en el módulo {module_id} tras actualizar el contenido {content_id}. Actualizaciones encoladas.")
                    except Exception as e:
                        logging.error(f"Error en el proceso de detección de cambios para el módulo {module_id}: {e}")

                return True, "Contenido actualizado exitosamente"
            else:
                return False, "No se encontró el contenido o no hubo cambios"
        except Exception as e:
            return False, str(e)
            
    def delete_content(self, content_id: str) -> Tuple[bool, str]:
        """
        Elimina un contenido existente.
        
        Args:
            content_id: ID del contenido a eliminar
            
        Returns:
            Tupla con estado y mensaje
        """
        try:
            # Verificar que el contenido existe
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return False, "Contenido no encontrado"
                
            # Eliminar el contenido
            result = self.collection.delete_one({"_id": ObjectId(content_id)})
            
            if result.deleted_count > 0:
                return True, "Contenido eliminado exitosamente"
            return False, "No se pudo eliminar el contenido"
        except Exception as e:
            logging.error(f"Error al eliminar contenido: {str(e)}")
            return False, str(e)
            
    def get_topic_content_by_type(self, topic_id: str, content_type: str) -> Optional[List[Dict]]:
        """
        Obtiene todos los contenidos de un tema según su tipo.
        """
        try:
            contents = list(self.collection.find({
                "topic_id": ObjectId(topic_id),
                "content_type": content_type
            }))
            # Convertir ObjectId a str para serialización
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
            return contents
        except Exception as e:
            logging.error(f"Error al obtener contenidos por tipo: {str(e)}")
            return None

    def adapt_content_to_methodology(self, content_id: str, methodology_code: str) -> Tuple[bool, Dict]:
        """
        Adapta un contenido según una metodología de aprendizaje específica.
        
        Args:
            content_id: ID del contenido
            methodology_code: Código de la metodología
            
        Returns:
            Tupla con estado y datos del contenido adaptado
        """
        try:
            # Obtener el contenido
            content = self.get_content(content_id)
            if not content:
                return False, {"error": "Contenido no encontrado"}
            
            # Obtener la metodología
            methodology_service = LearningMethodologyService()
            methodology = methodology_service.get_methodology(methodology_code)
            if not methodology:
                return False, {"error": f"Metodología '{methodology_code}' no encontrada"}
            
            # Verificar compatibilidad
            content_type = content.get("content_type")
            if not content_type in methodology.get("compatible_content_types", []):
                return False, {"error": f"La metodología '{methodology_code}' no es compatible con el tipo de contenido '{content_type}'"}
            
            # Obtener el tema
            topic_id = content.get("topic_id")
            topic = get_db().topics.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, {"error": "Tema no encontrado"}
            
            # Convertir a formato serializable
            topic = ensure_json_serializable(topic)
            
            # Obtener el contenido original
            original_content = content.get("content", "")
            
            # Adaptaciones según metodología
            adapted_content = original_content
            adaptation_notes = []
            
            if methodology_code == "feynman":
                # Adaptación según el método Feynman (simplificación y analogías)
                adapted_content = self._adapt_feynman(original_content, topic.get("name", ""))
                adaptation_notes.append("Contenido simplificado usando lenguaje claro y analogías")
                
            elif methodology_code == "spaced_repetition":
                # Adaptación para repetición espaciada (resúmenes y puntos clave)
                adapted_content = self._adapt_spaced_repetition(original_content)
                adaptation_notes.append("Contenido estructurado para repetición espaciada con puntos clave destacados")
                
            elif methodology_code == "mind_map":
                # Adaptación para mapas mentales (estructura jerárquica y conectada)
                adapted_content = self._adapt_mind_map(original_content, topic.get("name", ""))
                adaptation_notes.append("Contenido estructurado para ser representado como mapa mental")
                
            elif methodology_code == "project_based":
                # Adaptación para aprendizaje basado en proyectos
                adapted_content = self._adapt_project_based(original_content, topic.get("name", ""))
                adaptation_notes.append("Contenido orientado a proyectos prácticos de aplicación")
                
            elif methodology_code == "socratic":
                # Adaptación para método socrático (preguntas y reflexión)
                adapted_content = self._adapt_socratic(original_content)
                adaptation_notes.append("Contenido transformado en preguntas de reflexión y cuestionamiento")
                
            else:
                # Si no hay adaptación específica, mantener el contenido original
                adaptation_notes.append("Metodología sin adaptación específica, manteniendo contenido original")
            
            # Estructura de respuesta
            result = {
                "original_content": original_content,
                "adapted_content": adapted_content,
                "methodology": methodology,
                "adaptation_notes": adaptation_notes,
                "content_type": content_type,
                "topic_name": topic.get("name", "")
            }
            
            return True, result
        except Exception as e:
            logging.error(f"Error al adaptar contenido: {str(e)}")
            return False, {"error": str(e)}
        
    def _adapt_feynman(self, content: str, topic_name: str) -> str:
        """Adapta contenido según el método Feynman (simplificación)"""
        lines = content.split("\n")
        adapted = [f"# Explicación simplificada de {topic_name}", ""]
        
        # Simplificar y añadir analogías
        paragraphs = []
        current_paragraph = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                    current_paragraph = ""
            else:
                current_paragraph += line + " "
            
        if current_paragraph:
            paragraphs.append(current_paragraph)
        
        # Procesar cada párrafo
        for i, paragraph in enumerate(paragraphs):
            # Simplificar terminología técnica
            simplifications = [
                (r'[\w\s]+ es una metodología que', 'es un método que'),
                (r'se puede conceptualizar como', 'es como'),
                (r'es necesario [.\w\s]+ para', 'necesitas'),
                (r'se fundamenta en', 'se basa en'),
                (r'implementación', 'uso'),
                (r'([A-Z]\w+(?:\s[A-Z]\w+)+) es', r'"\1" es')  # Destacar términos técnicos
            ]
            
            simplified = paragraph
            for pattern, replacement in simplifications:
                simplified = re.sub(pattern, replacement, simplified)
            
            # Añadir una analogía para párrafos largos
            if len(simplified) > 200 and i == 0:
                simplified += f"\n\nPiensa en {topic_name} como si fuera un..."
            
            adapted.append(simplified)
            adapted.append("")
        
        # Añadir resumen final
        adapted.append("## En resumen:")
        adapted.append("* Punto clave 1")
        adapted.append("* Punto clave 2")
        adapted.append("* Punto clave 3")
        
        return "\n".join(adapted)
        
    def _adapt_spaced_repetition(self, content: str) -> str:
        """Adapta contenido para repetición espaciada (puntos clave y resúmenes)"""
        lines = content.split("\n")
        
        # Extraer puntos clave y conceptos
        key_points = []
        concepts = []
        
        # Buscar frases importantes (contienen palabras clave)
        important_indicators = ['importante', 'clave', 'fundamental', 'destacar', 'esencial', 'recordar', 'principal']
        concept_indicators = ['concepto', 'definición', 'término', 'significa', 'se define como']
        
        paragraphs = []
        current_paragraph = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                    current_paragraph = ""
            else:
                current_paragraph += line + " "
            
        if current_paragraph:
            paragraphs.append(current_paragraph)
        
        # Extraer puntos clave
        for paragraph in paragraphs:
            # Buscar puntos clave
            if any(indicator in paragraph.lower() for indicator in important_indicators):
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                for sentence in sentences:
                    if any(indicator in sentence.lower() for indicator in important_indicators):
                        key_points.append(sentence.strip())
            
            # Buscar conceptos
            if any(indicator in paragraph.lower() for indicator in concept_indicators):
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                for sentence in sentences:
                    if any(indicator in sentence.lower() for indicator in concept_indicators):
                        concepts.append(sentence.strip())
        
        # Si no encontramos suficientes puntos clave, usar las primeras oraciones de algunos párrafos
        if len(key_points) < 3 and paragraphs:
            for paragraph in paragraphs[:3]:
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                if sentences:
                    key_points.append(sentences[0].strip())
        
        # Estructurar el contenido para repetición espaciada
        adapted = ["# Contenido para Repetición Espaciada", ""]
        
        # Añadir sección de revisión rápida
        adapted.append("## Revisión Rápida (5 min)")
        if key_points:
            for point in key_points:
                adapted.append(f"* {point}")
        else:
            adapted.append("* Punto clave extraído del contenido")
        adapted.append("")
        
        # Añadir sección de conceptos
        adapted.append("## Conceptos Clave")
        if concepts:
            for concept in concepts:
                adapted.append(f"* {concept}")
        else:
            adapted.append("* No se encontraron definiciones claras en el contenido")
        adapted.append("")
        
        # Añadir contenido completo
        adapted.append("## Contenido Completo (Revisión detallada)")
        adapted.append(content)
        
        return "\n".join(adapted)
        
    def _adapt_mind_map(self, content: str, topic_name: str) -> str:
        """Adapta contenido para estructura de mapa mental"""
        try:
            # Convertir el contenido a estructura jerárquica para mapas mentales
            adapted = [f"# Mapa Mental: {topic_name}", ""]
            
            # Añadir nodo central
            adapted.append(f"## Nodo Central: {topic_name}")
            
            # Procesar el contenido
            lines = content.split('\n')
            current_level = 0
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Determinar nivel basado en encabezados
                if line.startswith('#'):
                    level = len(re.match(r'^#+', line).group())
                    current_level = level - 1
                    line = line.lstrip('#').strip()
                    
                # Añadir línea con indentación apropiada
                indent = "  " * current_level
                adapted.append(f"{indent}- {line}")
                
            return "\n".join(adapted)
            
        except Exception as e:
            logging.error(f"Error al generar recomendaciones: {str(e)}")
            return f"# Error al generar mapa mental\n{str(e)}"
        
    def _extract_keywords_from_topic(self, topic: Dict) -> List[str]:
        """
        Extrae palabras clave de un tema.
        
        Args:
            topic: Diccionario del tema
            
        Returns:
            Lista de palabras clave
        """
        keywords = []
        
        # Añadir nombre del tema
        if "name" in topic:
            keywords.append(topic["name"])
            
        # Extraer palabras del contenido teórico
        if "theory_content" in topic and topic["theory_content"]:
            # Definir palabras a ignorar (stop words)
            stop_words = set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'a', 
                             'de', 'del', 'en', 'con', 'por', 'para', 'es', 'son', 'al', 'e', 'u'])
                             
            # Extraer palabras relevantes
            words = re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b', topic["theory_content"].lower())
            
            # Filtrar stop words y contar frecuencia
            word_counts = {}
            for word in words:
                if word not in stop_words:
                    word_counts[word] = word_counts.get(word, 0) + 1
                    
            # Obtener las 10 palabras más frecuentes
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            frequent_words = [word for word, count in sorted_words[:10]]
            
            keywords.extend(frequent_words)
            
        # Si no hay suficientes palabras clave, usar el módulo
        if len(keywords) < 3 and "module_id" in topic:
            try:
                module = get_db().modules.find_one({"_id": ObjectId(topic["module_id"])})
                if module and "name" in module:
                    keywords.append(module["name"])
            except (TypeError, ValueError):
                pass
                
        return list(set(keywords))  # Eliminar duplicados
        
    def _recommend_pdfs(self, pdf_service, keywords: List[str]) -> List[Dict]:
        """
        Recomienda PDFs según palabras clave.
        
        Args:
            pdf_service: Servicio de procesamiento de PDFs
            keywords: Lista de palabras clave
            
        Returns:
            Lista de PDFs recomendados
        """
        try:
            # Buscar PDFs que contengan las palabras clave
            relevant_pdfs = []
            
            # Usamos una consulta de MongoDB para encontrar PDFs relevantes
            query = {
                "$or": [
                    {"tags": {"$in": keywords}},
                    {"title": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"extracted_text": {"$regex": "|".join(keywords), "$options": "i"}}
                ],
                "status": "active"
            }
            
            pdfs = list(pdf_service.collection.find(query).limit(5))
            
            # Convertir a formato serializable
            for pdf in pdfs:
                pdf = ensure_json_serializable(pdf)
                
                # Añadir puntuación de relevancia
                score = 0
                for keyword in keywords:
                    if keyword.lower() in pdf.get("title", "").lower():
                        score += 3
                    if keyword.lower() in " ".join(pdf.get("tags", [])).lower():
                        score += 2
                    extracted_text = pdf.get("extracted_text", "")
                    if extracted_text and keyword.lower() in extracted_text.lower():
                        score += 1
                        
                pdf["relevance_score"] = score
                relevant_pdfs.append(pdf)
                
            # Ordenar por relevancia
            relevant_pdfs.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return relevant_pdfs
        except Exception as e:
            logging.error(f"Error al recomendar PDFs: {str(e)}")
            return []
            
    def _recommend_web_resources(self, web_service, keywords: List[str]) -> List[Dict]:
        """
        Recomienda recursos web según palabras clave.
        
        Args:
            web_service: Servicio de búsqueda web
            keywords: Lista de palabras clave
            
        Returns:
            Lista de recursos web recomendados
        """
        try:
            # Buscar recursos web que contengan las palabras clave
            query = {
                "$or": [
                    {"tags": {"$in": keywords}},
                    {"title": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"snippet": {"$regex": "|".join(keywords), "$options": "i"}}
                ],
                "is_saved": True
            }
            
            web_resources = list(web_service.collection.find(query).limit(5))
            
            # Convertir a formato serializable
            relevant_resources = []
            for resource in web_resources:
                resource = ensure_json_serializable(resource)
                
                # Añadir puntuación de relevancia
                score = 0
                for keyword in keywords:
                    if keyword.lower() in resource.get("title", "").lower():
                        score += 3
                    if keyword.lower() in " ".join(resource.get("tags", [])).lower():
                        score += 2
                    if keyword.lower() in resource.get("snippet", "").lower():
                        score += 1
                        
                resource["relevance_score"] = score
                relevant_resources.append(resource)
                
            # Ordenar por relevancia
            relevant_resources.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return relevant_resources
        except Exception as e:
            logging.error(f"Error al recomendar recursos web: {str(e)}")
            return []
            
    def _recommend_diagrams(self, diagram_service, keywords: List[str], topic_name: str) -> List[Dict]:
        """
        Recomienda diagramas según palabras clave.
        
        Args:
            diagram_service: Servicio de diagramas
            keywords: Lista de palabras clave
            topic_name: Nombre del tema
            
        Returns:
            Lista de diagramas recomendados y plantillas sugeridas
        """
        try:
            # Buscar diagramas existentes
            query = {
                "$or": [
                    {"title": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"content": {"$regex": "|".join(keywords), "$options": "i"}}
                ],
                "status": "active"
            }
            
            diagrams = list(diagram_service.collection.find(query).limit(3))
            
            # Convertir a formato serializable
            relevant_diagrams = []
            for diagram in diagrams:
                diagram = ensure_json_serializable(diagram)
                
                # Añadir puntuación de relevancia
                score = 0
                for keyword in keywords:
                    if keyword.lower() in diagram.get("title", "").lower():
                        score += 3
                    if keyword.lower() in diagram.get("content", "").lower():
                        score += 1
                        
                diagram["relevance_score"] = score
                relevant_diagrams.append(diagram)
                
            # Ordenar por relevancia
            relevant_diagrams.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            # Determinar qué tipos de diagramas serían más útiles según las palabras clave
            # Palabras clave que sugieren diferentes tipos de diagramas
            process_keywords = ['proceso', 'flujo', 'pasos', 'etapas', 'procedimiento', 'secuencia']
            relation_keywords = ['relación', 'estructura', 'jerarquía', 'organización', 'sistema']
            concept_keywords = ['concepto', 'idea', 'teoría', 'principio', 'fundamento', 'mapa']
            
            recommended_types = []
            for keyword in keywords:
                keyword = keyword.lower()
                if any(k in keyword for k in process_keywords):
                    recommended_types.append("flowchart")
                if any(k in keyword for k in relation_keywords):
                    recommended_types.append("uml")
                if any(k in keyword for k in concept_keywords):
                    recommended_types.append("mindmap")
                    
            # Si no hay tipos recomendados, sugerir mapa mental por defecto
            if not recommended_types:
                recommended_types = ["mindmap"]
                
            return {
                "existing_diagrams": relevant_diagrams,
                "recommended_types": list(set(recommended_types))
            }
        except Exception as e:
            logging.error(f"Error al recomendar diagramas: {str(e)}")
            return {
                "existing_diagrams": [],
                "recommended_types": []
            }

class ContentRecommendationService(VerificationBaseService):
    """
    Servicio para recomendar contenido (PDFs, recursos web, diagramas) basado en temas.
    """
    def __init__(self):
        super().__init__(collection_name="topics")  # Usamos topics como colección base
        from src.shared.utils import ensure_json_serializable
        self.ensure_json_serializable = ensure_json_serializable
        
    def get_content_recommendations(self, topic_id: str) -> Dict:
        """
        Obtiene recomendaciones de contenido (PDFs, recursos web, diagramas) para un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Dict con 'pdfs', 'web_resources' y 'diagrams'
        """
        try:
            # Obtener el tema
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return {
                    "pdfs": [],
                    "web_resources": [],
                    "diagrams": {"existing_diagrams": [], "recommended_types": []}
                }
            
            topic = self.ensure_json_serializable(topic)
            
            # Extraer palabras clave del tema
            keywords = self._extract_keywords_from_topic(topic)
            
            # Obtener recomendaciones
            pdfs = self._recommend_pdfs(keywords)
            web_resources = self._recommend_web_resources(keywords)
            diagrams = self._recommend_diagrams(keywords, topic.get("name", ""))
            
            return {
                "pdfs": pdfs,
                "web_resources": web_resources,
                "diagrams": diagrams
            }
            
        except Exception as e:
            logging.error(f"Error al obtener recomendaciones de contenido: {str(e)}")
            return {
                "pdfs": [],
                "web_resources": [],
                "diagrams": {"existing_diagrams": [], "recommended_types": []}
            }
    
    def _extract_keywords_from_topic(self, topic: Dict) -> List[str]:
        """
        Extrae palabras clave de un tema.
        
        Args:
            topic: Diccionario del tema
            
        Returns:
            Lista de palabras clave
        """
        keywords = []
        
        # Añadir nombre del tema
        if "name" in topic:
            keywords.append(topic["name"])
            
        # Extraer palabras del contenido teórico
        if "theory_content" in topic and topic["theory_content"]:
            # Definir palabras a ignorar (stop words)
            stop_words = set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'a', 
                             'de', 'del', 'en', 'con', 'por', 'para', 'es', 'son', 'al', 'e', 'u'])
                             
            # Extraer palabras relevantes
            words = re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b', topic["theory_content"].lower())
            
            # Filtrar stop words y contar frecuencia
            word_counts = {}
            for word in words:
                if word not in stop_words:
                    word_counts[word] = word_counts.get(word, 0) + 1
                    
            # Obtener las 10 palabras más frecuentes
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            frequent_words = [word for word, count in sorted_words[:10]]
            
            keywords.extend(frequent_words)
            
        # Si no hay suficientes palabras clave, usar el módulo
        if len(keywords) < 3 and "module_id" in topic:
            try:
                module = get_db().modules.find_one({"_id": ObjectId(topic["module_id"])})
                if module and "name" in module:
                    keywords.append(module["name"])
            except (TypeError, ValueError):
                pass
                
        return list(set(keywords))  # Eliminar duplicados
    
    def _recommend_pdfs(self, keywords: List[str]) -> List[Dict]:
        """
        Recomienda PDFs según palabras clave.
        
        Args:
            keywords: Lista de palabras clave
            
        Returns:
            Lista de PDFs recomendados
        """
        try:
            # Buscar PDFs en la colección de recursos que sean PDFs
            query = {
                "$and": [
                    {
                        "$or": [
                            {"tags": {"$in": keywords}},
                            {"title": {"$regex": "|".join(keywords), "$options": "i"}},
                            {"description": {"$regex": "|".join(keywords), "$options": "i"}}
                        ]
                    },
                    {
                        "$or": [
                            {"file_type": "pdf"},
                            {"resource_type": "pdf"},
                            {"content_type": "pdf"}
                        ]
                    }
                ],
                "status": {"$ne": "deleted"}
            }
            
            # Intentar buscar en diferentes colecciones posibles
            pdfs_collection = get_db().resources  # O pdfs si existe
            pdfs = list(pdfs_collection.find(query).limit(5))
            
            # Convertir a formato serializable
            relevant_pdfs = []
            for pdf in pdfs:
                pdf = self.ensure_json_serializable(pdf)
                
                # Añadir puntuación de relevancia
                score = 0
                for keyword in keywords:
                    if keyword.lower() in pdf.get("title", "").lower():
                        score += 3
                    if keyword.lower() in " ".join(pdf.get("tags", [])).lower():
                        score += 2
                    description = pdf.get("description", "")
                    if description and keyword.lower() in description.lower():
                        score += 1
                        
                pdf["relevance_score"] = score
                relevant_pdfs.append(pdf)
                
            # Ordenar por relevancia
            relevant_pdfs.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return relevant_pdfs
        except Exception as e:
            logging.error(f"Error al recomendar PDFs: {str(e)}")
            return []
            
    def _recommend_web_resources(self, keywords: List[str]) -> List[Dict]:
        """
        Recomienda recursos web según palabras clave.
        
        Args:
            keywords: Lista de palabras clave
            
        Returns:
            Lista de recursos web recomendados
        """
        try:
            # Buscar recursos web que contengan las palabras clave
            query = {
                "$and": [
                    {
                        "$or": [
                            {"tags": {"$in": keywords}},
                            {"title": {"$regex": "|".join(keywords), "$options": "i"}},
                            {"description": {"$regex": "|".join(keywords), "$options": "i"}},
                            {"url": {"$regex": "|".join(keywords), "$options": "i"}}
                        ]
                    },
                    {
                        "$or": [
                            {"resource_type": "link"},
                            {"content_type": "link"},
                            {"resource_type": "web"}
                        ]
                    }
                ],
                "status": {"$ne": "deleted"}
            }
            
            web_resources_collection = get_db().resources
            web_resources = list(web_resources_collection.find(query).limit(5))
            
            # Convertir a formato serializable
            relevant_resources = []
            for resource in web_resources:
                resource = self.ensure_json_serializable(resource)
                
                # Añadir puntuación de relevancia
                score = 0
                for keyword in keywords:
                    if keyword.lower() in resource.get("title", "").lower():
                        score += 3
                    if keyword.lower() in " ".join(resource.get("tags", [])).lower():
                        score += 2
                    description = resource.get("description", "")
                    if description and keyword.lower() in description.lower():
                        score += 1
                        
                resource["relevance_score"] = score
                relevant_resources.append(resource)
                
            # Ordenar por relevancia
            relevant_resources.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return relevant_resources
        except Exception as e:
            logging.error(f"Error al recomendar recursos web: {str(e)}")
            return []
            
    def _recommend_diagrams(self, keywords: List[str], topic_name: str) -> Dict:
        """
        Recomienda diagramas según palabras clave.
        
        Args:
            keywords: Lista de palabras clave
            topic_name: Nombre del tema
            
        Returns:
            Dict con 'existing_diagrams' y 'recommended_types'
        """
        try:
            # Buscar diagramas existentes en topic_contents con content_type='diagram'
            query = {
                "$or": [
                    {"title": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"content": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"description": {"$regex": "|".join(keywords), "$options": "i"}}
                ],
                "content_type": "diagram",
                "status": {"$ne": "deleted"}
            }
            
            diagrams_collection = get_db().topic_contents
            diagrams = list(diagrams_collection.find(query).limit(3))
            
            # Convertir a formato serializable
            relevant_diagrams = []
            for diagram in diagrams:
                diagram = self.ensure_json_serializable(diagram)
                
                # Añadir puntuación de relevancia
                score = 0
                for keyword in keywords:
                    title = diagram.get("title", "") or diagram.get("content", {}).get("title", "")
                    if title and keyword.lower() in title.lower():
                        score += 3
                    content_str = str(diagram.get("content", ""))
                    if keyword.lower() in content_str.lower():
                        score += 1
                        
                diagram["relevance_score"] = score
                relevant_diagrams.append(diagram)
                
            # Ordenar por relevancia
            relevant_diagrams.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            # Determinar qué tipos de diagramas serían más útiles según las palabras clave
            process_keywords = ['proceso', 'flujo', 'pasos', 'etapas', 'procedimiento', 'secuencia']
            relation_keywords = ['relación', 'estructura', 'jerarquía', 'organización', 'sistema']
            concept_keywords = ['concepto', 'idea', 'teoría', 'principio', 'fundamento', 'mapa']
            
            recommended_types = []
            for keyword in keywords:
                keyword = keyword.lower()
                if any(k in keyword for k in process_keywords):
                    recommended_types.append("flowchart")
                if any(k in keyword for k in relation_keywords):
                    recommended_types.append("uml")
                if any(k in keyword for k in concept_keywords):
                    recommended_types.append("mindmap")
                    
            # Si no hay tipos recomendados, sugerir mapa mental por defecto
            if not recommended_types:
                recommended_types = ["mindmap"]
                
            return {
                "existing_diagrams": relevant_diagrams,
                "recommended_types": list(set(recommended_types))
            }
        except Exception as e:
            logging.error(f"Error al recomendar diagramas: {str(e)}")
            return {
                "existing_diagrams": [],
                "recommended_types": []
            }

class EvaluationResourceService(VerificationBaseService):
    """
    Servicio para gestionar la vinculación entre Evaluaciones y Recursos.
    """
    def __init__(self):
        super().__init__(collection_name="evaluation_resources")

    def check_evaluation_exists(self, evaluation_id: str) -> bool:
        """Verifica si una evaluación existe."""
        try:
            return get_db().evaluations.find_one({"_id": ObjectId(evaluation_id)}) is not None
        except Exception:
            return False

    def check_resource_exists(self, resource_id: str) -> bool:
        """Verifica si un recurso existe."""
        try:
            return get_db().resources.find_one({"_id": ObjectId(resource_id)}) is not None
        except Exception:
            return False

    def link_resource_to_evaluation(self, evaluation_id: str, resource_id: str, role: str, created_by: str) -> Tuple[bool, str]:
        """
        Vincula un recurso existente a una evaluación con un rol específico.
        
        Args:
            evaluation_id: ID de la evaluación.
            resource_id: ID del recurso.
            role: Rol del recurso ("template", "submission", "supporting_material").
            created_by: ID del usuario que crea la vinculación.
            
        Returns:
            (éxito, ID de la vinculación o mensaje de error)
        """
        try:
            if not self.check_evaluation_exists(evaluation_id):
                return False, "Evaluación no encontrada"
            if not self.check_resource_exists(resource_id):
                return False, "Recurso no encontrado"

            # Verificar si ya existe esta vinculación específica (podría ser opcional)
            existing_link = self.collection.find_one({
                "evaluation_id": ObjectId(evaluation_id),
                "resource_id": ObjectId(resource_id)
            })
            if existing_link:
                # Podríamos decidir actualizar el rol o simplemente retornar el existente
                return True, str(existing_link["_id"])
            
            link_data = {
                "evaluation_id": evaluation_id,
                "resource_id": resource_id,
                "role": role,
                "created_by": created_by
            }
            evaluation_resource = EvaluationResource(**link_data)
            result = self.collection.insert_one(evaluation_resource.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            log_error(f"Error al vincular recurso {resource_id} a evaluación {evaluation_id}: {str(e)}")
            return False, str(e)

    def get_evaluation_resources(self, evaluation_id: str, role: Optional[str] = None, student_id: Optional[str] = None) -> List[Dict]:
        """
        Obtiene los recursos vinculados a una evaluación, con filtros opcionales.
        
        Args:
            evaluation_id: ID de la evaluación.
            role: Filtrar por rol del recurso.
            student_id: Filtrar por entregables de un estudiante específico (si role="submission").
            
        Returns:
            Lista de documentos de la vinculación (enriquecidos con datos del recurso).
        """
        try:
            if not self.check_evaluation_exists(evaluation_id):
                return []

            query = {"evaluation_id": ObjectId(evaluation_id)}
            if role:
                query["role"] = role
            if student_id and role == "submission":
                query["created_by"] = ObjectId(student_id)
            
            links = list(self.collection.find(query))
            
            # Enriquecer con detalles del recurso
            enriched_links = []
            resource_ids = [link["resource_id"] for link in links]
            resources = list(get_db().resources.find({"_id": {"$in": resource_ids}}))
            resource_map = {str(r["_id"]): r for r in resources}

            for link in links:
                resource_id_str = str(link["resource_id"])
                resource_details = resource_map.get(resource_id_str)
                if resource_details:
                    link["_id"] = str(link["_id"])
                    link["evaluation_id"] = str(link["evaluation_id"])
                    link["resource_id"] = resource_id_str
                    link["created_by"] = str(link["created_by"])
                    
                    # Limpiar resource_details antes de añadirlo
                    resource_details['_id'] = str(resource_details['_id'])
                    if 'created_by' in resource_details: resource_details['created_by'] = str(resource_details['created_by'])
                    if 'folder_id' in resource_details: resource_details['folder_id'] = str(resource_details['folder_id'])
                    
                    link["resource"] = resource_details
                    enriched_links.append(link)
                    
            return enriched_links
        except Exception as e:
            log_error(f"Error al obtener recursos para evaluación {evaluation_id}: {str(e)}")
            return []

    def remove_resource_from_evaluation(self, evaluation_id: str, resource_id: str) -> Tuple[bool, str]:
        """
        Elimina la vinculación entre una evaluación y un recurso.
        No elimina el recurso en sí.
        
        Args:
            evaluation_id: ID de la evaluación.
            resource_id: ID del recurso.
            
        Returns:
            (éxito, mensaje)
        """
        try:
            result = self.collection.delete_one({
                "evaluation_id": ObjectId(evaluation_id),
                "resource_id": ObjectId(resource_id)
            })
            
            if result.deleted_count > 0:
                return True, "Vinculación eliminada correctamente"
            return False, "Vinculación no encontrada"
        except Exception as e:
            log_error(f"Error al eliminar vinculación recurso {resource_id} evaluación {evaluation_id}: {str(e)}")
            return False, str(e)

class AutomaticGradingService:
    """
    IMPLEMENTACIÓN SIMPLIFICADA - Servicio para corrección automática de entregas.
    
    NOTA: Esta es una implementación básica que utiliza algoritmos simplificados
    de evaluación automática. Es funcional pero limitada en comparación con 
    sistemas de IA avanzados de corrección automática.
    
    LIMITACIONES ACTUALES:
    - Análisis de texto básico sin procesamiento de lenguaje natural avanzado
    - Evaluación basada en criterios simples (longitud, keywords, formato)
    - No incluye análisis semántico profundo
    - Sin machine learning para mejora continua
    
    TODO FUTURO: Considerar integración con:
    - Modelos de IA especializados en evaluación de texto
    - Análisis semántico avanzado
    - Sistema de retroalimentación inteligente
    - Mejora continua basada en feedback humano
    
    EXPECTATIVA DEL CLIENTE: El cliente está informado de que este es un sistema
    de corrección automática simplificado, no una solución de IA avanzada.
    """

    def __init__(self):
        self.db = get_db()
        # Logging para indicar uso de implementación simplificada
        logging.info("Iniciando AutomaticGradingService - implementación simplificada de corrección automática")

    def grade_submission(self, resource_id: str, evaluation_id: str) -> Dict:
        """
        SIMPLIFICADO - Califica automáticamente una entrega basada en criterios básicos.
        
        Utiliza algoritmos simplificados de evaluación. No incluye IA avanzada
        ni procesamiento de lenguaje natural sofisticado.
        """
        logging.debug(f"Iniciando corrección automática simplificada para resource: {resource_id}")
        
        try:
            # Obtener información del recurso (archivo entregado)
            resource = self.db.resources.find_one({"_id": ObjectId(resource_id)})
            if not resource:
                return {"grade": 0.0, "feedback": "Recurso no encontrado"}
            
            # Obtener información de la evaluación
            evaluation = self.db.evaluations.find_one({"_id": ObjectId(evaluation_id)})
            if not evaluation:
                return {"grade": 0.0, "feedback": "Evaluación no encontrada"}
            
            # Lógica de calificación automática básica
            grade = self._calculate_automatic_grade(resource, evaluation)
            feedback = self._generate_automatic_feedback(resource, evaluation, grade)
            
            return {
                "grade": grade,
                "feedback": feedback,
                "graded_at": datetime.now(),
                "auto_graded": True
            }
        except Exception as e:
            logging.error(f"Error en calificación automática: {str(e)}")
            return {
                "grade": 0.0, 
                "feedback": f"Error en calificación automática: {str(e)}",
                "graded_at": datetime.now(),
                "auto_graded": True
            }
    
    def _calculate_automatic_grade(self, resource: Dict, evaluation: Dict) -> float:
        """Calcula la calificación automática basada en criterios simples."""
        try:
            # Criterios básicos de calificación automática
            base_score = 70.0  # Puntuación base por entregar
            
            # Bonus por tipo de archivo
            file_type_bonus = 0.0
            resource_type = resource.get("type", "")
            if resource_type in ["pdf", "docx", "doc"]:
                file_type_bonus = 10.0
            elif resource_type in ["txt", "md"]:
                file_type_bonus = 5.0
            
            # Bonus por tamaño del archivo (indica esfuerzo)
            size_bonus = 0.0
            file_size = resource.get("size", 0)
            if file_size > 1024:  # Más de 1KB
                size_bonus = 10.0
            elif file_size > 512:  # Más de 512B
                size_bonus = 5.0
            
            # Bonus por entrega temprana (si hay fecha límite)
            timing_bonus = 0.0
            due_date = evaluation.get("due_date")
            if due_date and isinstance(due_date, datetime):
                submitted_at = resource.get("created_at", datetime.now())
                if submitted_at < due_date:
                    timing_bonus = 5.0
            
            total_score = min(100.0, base_score + file_type_bonus + size_bonus + timing_bonus)
            return total_score
            
        except Exception:
            return 70.0  # Puntuación por defecto
    
    def _generate_automatic_feedback(self, resource: Dict, evaluation: Dict, grade: float) -> str:
        """Genera feedback automático basado en la calificación."""
        try:
            feedback_parts = ["Calificación automática:"]
            
            if grade >= 90:
                feedback_parts.append("Excelente entrega.")
            elif grade >= 80:
                feedback_parts.append("Buena entrega.")
            elif grade >= 70:
                feedback_parts.append("Entrega satisfactoria.")
            else:
                feedback_parts.append("Entrega necesita mejoras.")
            
            # Agregar detalles específicos
            resource_type = resource.get("type", "")
            if resource_type in ["pdf", "docx", "doc"]:
                feedback_parts.append("Formato de archivo apropiado.")
            
            file_size = resource.get("size", 0)
            if file_size > 1024:
                feedback_parts.append("Archivo con contenido sustancial.")
            
            feedback_parts.append("Revisión manual recomendada para feedback detallado.")
            
            return " ".join(feedback_parts)
            
        except Exception:
            return "Calificado automáticamente. Revisión manual recomendada."

class TopicReadinessService(VerificationBaseService):
    """
    Servicio para verificar si un tema está listo para ser publicado y virtualizado.
    """
    def __init__(self):
        super().__init__(collection_name="topics")
        self.content_service = ContentService()

    def check_readiness(self, topic_id: str) -> Dict[str, Any]:
        """
        Verifica si un tema cumple con los requisitos mínimos para ser publicado.
        Según la documentación técnica, solo las diapositivas individuales (slide) y 
        el quiz son obligatorios para la virtualización de un tema.

        Args:
            topic_id: ID del tema a verificar.

        Returns:
            Un diccionario con el estado de preparación y los requisitos faltantes.
        """
        try:
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                raise AppException("Tema no encontrado", ErrorCodes.NOT_FOUND)

            # Obtener contenidos con todos los estados válidos para slides
            # Incluir "narrative_ready" que es el estado de slides generadas
            all_valid_statuses = ["draft", "active", "published", "skeleton", "html_ready", "narrative_ready"]
            contents = self.content_service.get_topic_content(topic_id, status_filter=all_valid_statuses)
            content_types_present = {c.get('content_type') for c in contents}

            # --- Nuevas Reglas de Validación (Solo Quiz y Slide Obligatorios) ---
            missing_requirements = []
            
            # Verificar contenidos obligatorios
            required_content_types = ['quiz', 'slide']  # Solo estos son obligatorios
            
            for content_type in required_content_types:
                if content_type not in content_types_present:
                    if content_type == 'quiz':
                        message = "Falta una evaluación tipo quiz."
                    elif content_type == 'slide':
                        message = "Falta una diapositiva individual."
                    missing_requirements.append(message)

            # Verificar contenidos opcionales (para información del frontend)
            type_map = ContentTypes.get_categories()
            theoretical_types = set(type_map.get("theoretical", []))
            has_theoretical = any(ct in theoretical_types for ct in content_types_present)
            has_kinesthetic = ("game" in content_types_present) or ("simulation" in content_types_present)
            has_critical_thinking = "guided_questions" in content_types_present

            # --- Construir Respuesta ---
            # Un tema está listo SOLO si tiene quiz Y diapositivas individuales
            is_ready = "quiz" in content_types_present and "slide" in content_types_present
            
            return {
                "ready": is_ready,
                "topic_id": topic_id,
                "checks": {
                    "has_theoretical": has_theoretical,
                    "has_quiz": "quiz" in content_types_present,
                    "has_slide": "slide" in content_types_present,  # Nomenclatura actualizada
                    "has_diagram": "diagram" in content_types_present,
                    "has_video": "video" in content_types_present,
                    "has_kinesthetic": has_kinesthetic,
                    "has_critical_thinking": has_critical_thinking,
                    "found_content_types": list(content_types_present)
                },
                "missing_requirements": missing_requirements  # Solo incluye quiz y slide si faltan
            }

        except AppException as e:
            raise e
        except Exception as e:
            log_error(f"Error al verificar la preparación del tema {topic_id}: {e}")
            raise AppException("Error interno del servidor al verificar el tema.", ErrorCodes.SERVER_ERROR)
