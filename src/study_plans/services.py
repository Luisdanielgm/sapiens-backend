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
from src.classes.services import ClassService
from src.study_plans.models import (
    StudyPlanPerSubject, StudyPlanAssignment, Module, Topic, Evaluation, 
    EvaluationResource
)
from src.content.models import (
    TopicContent, ContentType, ContentTypes
)
from src.resources.services import ResourceService, ResourceFolderService
from src.content.services import ContentResultService, ContentService
from src.shared.logging import log_error
import inspect # <--- Añadir import

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

    def list_study_plans(self, email: str = None) -> List[Dict]:
        try:
            query = {}
            if email:
                # Buscar el ID del usuario por su email
                user = get_db().users.find_one({"email": email})
                if user:
                    query["author_id"] = ObjectId(user["_id"])
            
            plans = list(self.collection.find(query))
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
            
            # Obtener evaluaciones relacionadas
            evaluations = list(get_db().evaluations.find({"module_id": ObjectId(module_id)}))
            
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
                # Al eliminar un tema, también se deben eliminar sus contenidos asociados
                contents = get_db().topic_contents.find({"topic_id": ObjectId(topic['_id'])})
                content_ids_to_delete = [c['_id'] for c in contents]
                if content_ids_to_delete:
                    get_db().topic_contents.delete_many({"_id": {"$in": content_ids_to_delete}})
                
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

    def get_virtualization_readiness(self, module_id: str) -> Dict:
        """
        Verifica requisitos para virtualización y sugiere acciones.
        """
        validate_object_id(module_id, "ID de módulo")
        module = self.collection.find_one({"_id": ObjectId(module_id)})
        if not module:
            raise AppException("Módulo no encontrado", AppException.NOT_FOUND)
        db = get_db()
        # Obtener temas del módulo
        topics = list(db.topics.find({"module_id": ObjectId(module_id)}))
        total_topics = len(topics)
        # Conteo de temas publicados/no publicados
        published_topics = list(db.topics.find({"module_id": ObjectId(module_id), "published": True}))
        published_topics_count = len(published_topics)
        unpublished_topics_count = total_topics - published_topics_count
        missing_theory = [t for t in topics if not t.get("theory_content")]
        missing_resources = [t for t in topics if not t.get("resources") or len(t.get("resources")) == 0]
        # Contar evaluaciones asociadas
        eval_count = db.evaluations.count_documents({"module_id": ObjectId(module_id)})
        
        # Calcular content_completeness_score
        content_completeness_score = 0
        if total_topics > 0:
            topics_with_content = total_topics - len(missing_theory)
            content_completeness_score = int((topics_with_content / total_topics) * 100)
            
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
        
        # Preparar detalles de cheques
        checks = {
            "total_topics": total_topics,
            "published_topics_count": published_topics_count,
            "unpublished_topics_count": unpublished_topics_count,
            "missing_theory_count": len(missing_theory),
            "missing_resources_count": len(missing_resources),
            "evaluations_count": eval_count,
            "content_completeness_score": content_completeness_score
        }
        suggestions = []
        # Sugerencia de publicar temas restantes
        if unpublished_topics_count > 0:
            suggestions.append(f"{unpublished_topics_count} temas sin publicar")
        if total_topics == 0:
            suggestions.append("Agregar al menos un tema al módulo")
        else:
            if checks["missing_theory_count"] > 0:
                suggestions.append(f"{checks['missing_theory_count']} temas sin contenido teórico")
            if checks["missing_resources_count"] > 0:
                suggestions.append(f"{checks['missing_resources_count']} temas sin recursos asociados")
        if eval_count == 0:
            suggestions.append("Agregar al menos una evaluación al módulo")
        ready = all([
            checks["published_topics_count"] > 0,
            checks["missing_theory_count"] == 0,
            checks["missing_resources_count"] == 0,
            eval_count > 0
        ])
        return {"ready": ready, "checks": checks, "suggestions": suggestions}


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
    
    def delete_topic(self, topic_id: str) -> Tuple[bool, str]:
        """
        Elimina un tema y sus vinculaciones. 
        Elimina los recursos asociados SOLO si este tema era el único que los vinculaba.
        """
        try:
            # Validar ID
            topic_id_obj = ObjectId(topic_id)

            # Verificar que el tema existe
            topic = self.collection.find_one({"_id": topic_id_obj})
            if not topic:
                return False, "Tema no encontrado"

            # Eliminar todos los TopicContent asociados a este tema
            content_result = get_db().topic_contents.delete_many({"topic_id": topic_id_obj})
            logging.info(f"Eliminados {content_result.deleted_count} contenidos asociados al tema {topic_id}")
            
            # Finalmente, eliminar el tema en sí
            result = self.collection.delete_one({"_id": topic_id_obj})
            
            if result.deleted_count > 0:
                msg = f"Tema y {content_result.deleted_count} contenidos asociados eliminados exitosamente."
                return True, msg
            
            # Si llegamos aquí, el tema no se eliminó por alguna razón
            return False, "No se pudo eliminar el tema después de procesar sus contenidos"

        except Exception as e:
            logging.error(f"Error al eliminar el tema {topic_id}: {str(e)}")
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

class EvaluationService(VerificationBaseService):
    def __init__(self):
        super().__init__(collection_name="evaluations")

    def create_evaluation(self, evaluation_data: dict) -> Tuple[bool, str]:
        try:
            # Validar que existe el módulo
            module_id = evaluation_data.get('module_id')
            module = get_db().modules.find_one({"_id": ObjectId(module_id)})
            if not module:
                return False, "Módulo no encontrado"
            
            # Crear una copia con los datos necesarios para el constructor
            evaluation_dict = {
                "module_id": ObjectId(module_id),
                "title": evaluation_data.get("title"),
                "description": evaluation_data.get("description", ""),
                "weight": evaluation_data.get("weight", 0),
                "criteria": evaluation_data.get("criteria", []),
                # due_date se manejará a continuación
            }
            
            # Opciones de evaluación avanzada
            evaluation_dict["use_quiz_score"] = evaluation_data.get("use_quiz_score", False)
            evaluation_dict["requires_submission"] = evaluation_data.get("requires_submission", False)
            if "linked_quiz_id" in evaluation_data:
                evaluation_dict["linked_quiz_id"] = evaluation_data.get("linked_quiz_id")
            
            # ---- Inicio: Manejo de due_date ----
            due_date_str = evaluation_data.get("due_date")
            if isinstance(due_date_str, str):
                try:
                    evaluation_dict["due_date"] = datetime.fromisoformat(due_date_str)
                except ValueError:
                     logging.error(f"Formato de due_date inválido: {due_date_str}")
                     return False, f"Formato de due_date inválido: {due_date_str}"
            elif isinstance(due_date_str, datetime):
                 evaluation_dict["due_date"] = due_date_str # Ya es datetime
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
            
            # Convertir module_id a ObjectId si se actualiza
            if 'module_id' in update_data and isinstance(update_data['module_id'], str):
                update_data['module_id'] = ObjectId(update_data['module_id'])
            
            # Manejo de linked_quiz_id para actualización de evaluación
            if 'linked_quiz_id' in update_data and isinstance(update_data['linked_quiz_id'], str):
                update_data['linked_quiz_id'] = ObjectId(update_data['linked_quiz_id'])

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
        """
        Registra la calificación de una evaluación.
        Utiliza el servicio unificado de ContentResult.
        """
        try:
            # Validaciones
            evaluation_id = result_data.get("evaluation_id")
            student_id = result_data.get("student_id")
            graded_by = result_data.get("graded_by")

            if not self.check_evaluation_exists(evaluation_id):
                return False, "Evaluación no encontrada"
            if not self.check_student_exists(student_id):
                return False, "Estudiante no encontrado"
            if not self.check_teacher_exists(graded_by):
                return False, "Evaluador no encontrado"

            # Preparar datos para ContentResult
            unified_result_data = {
                "evaluation_id": evaluation_id,
                "student_id": student_id,
                "graded_by": graded_by,
                "score": result_data.get("score"),
                "feedback": result_data.get("feedback"),
                "session_type": "assessment"
            }
            
            # Usar el servicio unificado
            content_result_service = ContentResultService()
            success, result_id_or_msg = content_result_service.record_result(unified_result_data)

            return success, result_id_or_msg

        except Exception as e:
            logging.error(f"Error registrando resultado de evaluación: {str(e)}")
            return False, str(e)

    def update_result(self, result_id: str, update_data: dict) -> Tuple[bool, str]:
        """Actualiza un resultado de evaluación existente en la colección de ContentResult."""
        try:
            # El result_id ahora corresponde a un _id en content_results
            content_result_service = ContentResultService()
            
            # Asegurarse de que el update_data no cambie el student_id o evaluation_id
            update_data.pop("student_id", None)
            update_data.pop("evaluation_id", None)
            
            result = content_result_service.collection.update_one(
                {"_id": ObjectId(result_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                return True, "Resultado actualizado exitosamente"
            
            return False, "No se encontró el resultado o no hubo cambios"
        except Exception as e:
            return False, str(e)

    def delete_result(self, result_id: str) -> Tuple[bool, str]:
        """Elimina un resultado de la colección de ContentResult."""
        try:
            content_result_service = ContentResultService()
            result = content_result_service.collection.delete_one({"_id": ObjectId(result_id)})
            if result.deleted_count > 0:
                return True, "Resultado eliminado exitosamente"
            return False, "No se encontró el resultado"
        except Exception as e:
            return False, str(e)

    def get_student_results(self, student_id: str, module_id: str = None) -> List[Dict]:
        """
        Obtiene los resultados de las evaluaciones de un estudiante para un módulo.
        Utiliza el servicio unificado de ContentResult.
        """
        try:
            # Primero, obtener todas las evaluaciones del módulo
            if not module_id:
                raise ValueError("Se requiere un module_id para buscar resultados de evaluación.")

            evaluations = list(self.collection.find({"module_id": ObjectId(module_id)}))
            evaluation_ids = [str(e["_id"]) for e in evaluations]

            if not evaluation_ids:
                return []

            # Usar ContentResultService para obtener los resultados
            content_result_service = ContentResultService()
            all_results = []
            
            # Buscar un resultado para cada evaluación
            for eval_id in evaluation_ids:
                results_for_eval = content_result_service.get_student_results(
                    student_id=student_id,
                    evaluation_id=eval_id
                )
                all_results.extend(results_for_eval)

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
            content_type = self.collection.find_one({"code": code, "status": "active"})
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
            
            # Convertir diccionario a JSON string si es necesario
            if isinstance(content_payload, dict):
                content_payload = json.dumps(content_payload, ensure_ascii=False)
            elif not isinstance(content_payload, str):
                content_payload = str(content_payload)

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
            except:
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

class TopicReadinessService(VerificationBaseService):
    """
    Servicio para verificar si un tema está listo para ser publicado y virtualizado.
    """
    def __init__(self):
        super().__init__(collection_name="topics")
        self.content_service = ContentService()

    def check_readiness(self, topic_id: str) -> Dict[str, Any]:
        """
        Verifica si un tema cumple con los requisitos mínimos para ser publicado,
        asegurando una rica variedad de contenidos para diferentes estilos de aprendizaje.

        Args:
            topic_id: ID del tema a verificar.

        Returns:
            Un diccionario con el estado de preparación y los requisitos faltantes.
        """
        try:
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                raise AppException("Tema no encontrado", ErrorCodes.NOT_FOUND)

            contents = self.content_service.get_topic_content(topic_id)
            content_types_present = {c.get('content_type') for c in contents}

            # --- Reglas de Validación Multisensorial ---
            missing_requirements = []
            
            # 1. Requisito Teórico (Base fundamental)
            type_map = ContentTypes.get_categories()
            theoretical_types = set(type_map.get("theoretical", []))
            has_theoretical = any(ct in theoretical_types for ct in content_types_present)
            if not has_theoretical:
                types_str = ", ".join(theoretical_types)
                message = f"Falta un contenido teórico base. Puedes crear uno de los siguientes tipos: {types_str}."
                missing_requirements.append(message)

            # 2. Requisitos Específicos por Estilo de Aprendizaje
            checks = {
                "quiz": ("evaluación", "quiz"),
                "slides": ("lecto-escritura/visual", "slides"),
                "diagram": ("visual", "diagram"),
                "video": ("auditivo/visual", "video"),
            }

            for content_key, (style, type_name) in checks.items():
                if content_key not in content_types_present:
                    message = f"Falta un contenido de tipo {style}. Se requiere un '{type_name}'."
                    missing_requirements.append(message)
            
            # 3. Requisito Kinestésico (Juego o Simulación)
            has_kinesthetic = ("game" in content_types_present) or ("simulation" in content_types_present)
            if not has_kinesthetic:
                message = "Falta un contenido kinestésico/interactivo. Se requiere un 'game' o 'simulation'."
                missing_requirements.append(message)

            # --- Construir Respuesta ---
            is_ready = not missing_requirements
            
            return {
                "ready": is_ready,
                "topic_id": topic_id,
                "checks": {
                    "has_theoretical": has_theoretical,
                    "has_quiz": "quiz" in content_types_present,
                    "has_slides": "slides" in content_types_present,
                    "has_diagram": "diagram" in content_types_present,
                    "has_video": "video" in content_types_present,
                    "has_kinesthetic": has_kinesthetic,
                    "found_content_types": list(content_types_present)
                },
                "missing_requirements": missing_requirements
            }

        except AppException as e:
            raise e
        except Exception as e:
            log_error(f"Error al verificar la preparación del tema {topic_id}: {e}")
            raise AppException("Error interno del servidor al verificar el tema.", ErrorCodes.SERVER_ERROR)
