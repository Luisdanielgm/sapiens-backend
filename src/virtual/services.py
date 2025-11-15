from typing import Tuple, List, Dict, Optional, Any
from collections import defaultdict
from bson import ObjectId
from datetime import datetime, timedelta
import logging

from pymongo import UpdateOne

from src.shared.database import get_db
from src.shared.constants import STATUS, COLLECTIONS
from src.shared.standardization import BaseService, VerificationBaseService
from src.shared.exceptions import AppException
from .models import (
    VirtualModule,
    VirtualTopic,
    VirtualGenerationTask,
    VirtualTopicContent
)
# Quiz y QuizResult eliminados - ahora se usan TopicContent y ContentResult

class VirtualModuleService(VerificationBaseService):
    """
    Servicio para gestionar módulos virtuales.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_modules")

    def check_study_plan_exists(self, plan_id: str) -> bool:
        """
        Verifica si un plan de estudios existe
        
        Args:
            plan_id: ID del plan de estudios
            
        Returns:
            bool: True si el plan existe, False en caso contrario
        """
        try:
            study_plan = self.db.study_plans_per_subject.find_one({"_id": ObjectId(plan_id)})
            return study_plan is not None
        except Exception:
            return False

    def create_module(self, module_data: dict) -> Tuple[bool, str]:
        try:
            # Verificar que el plan de estudio existe
            if not self.check_study_plan_exists(module_data['study_plan_id']):
                return False, "Plan de estudios no encontrado"

            module = VirtualModule(**module_data)
            result = self.collection.insert_one(module.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)

    def get_module_details(self, module_id: str) -> Optional[Dict]:
        """
        Obtiene los detalles de un módulo virtual.
        
        Args:
            module_id: ID del módulo a obtener
            
        Returns:
            Dict: Detalles del módulo o None si no existe
        """
        try:
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return None
                
            # Convertir ObjectId a string y preparar module_id
            module["_id"] = str(module["_id"])
            # Campo module_id siempre presente
            module["module_id"] = str(module.get("module_id"))

            # Manejar study_plan_id faltante (módulos creados antes del parche)
            orig_plan_oid = module.get("study_plan_id")
            if orig_plan_oid:
                module["study_plan_id"] = str(orig_plan_oid)
            else:
                # Obtener study_plan_id desde colección de módulos originales
                orig = self.db.modules.find_one({"_id": ObjectId(module["module_id"])})
                if orig and orig.get("study_plan_id"):
                    module["study_plan_id"] = str(orig.get("study_plan_id"))

            # Manejar description faltante
            if not module.get("description"):
                # Tratamiento para módulos antiguos sin campo description
                orig = orig if 'orig' in locals() else self.db.modules.find_one({"_id": ObjectId(module["module_id"])})
                module["description"] = orig.get("description", "") if orig else ""

            # Obtener información del plan de estudios si existe study_plan_id
            # Obtener información del plan de estudios
            study_plan = None
            if module.get("study_plan_id"):
                study_plan = self.db.study_plans_per_subject.find_one({"_id": ObjectId(module["study_plan_id"])})
            if study_plan:
                module["study_plan"] = {
                    "name": study_plan.get("name", ""),
                    "subject": study_plan.get("subject", "")
                }
                
            # Obtener temas asociados
            topic_service = VirtualTopicService()
            module["topics"] = topic_service.get_module_topics(module_id)
            
            return module
        except Exception as e:
            logging.error(f"Error al obtener detalles del módulo: {str(e)}")
            return None

    def get_student_modules(self, study_plan_id: str, student_id: str, workspace_type: str = None, workspace_user_id: str = None, class_id: str = None) -> List[Dict]:
        """
        Obtiene todos los módulos virtuales de un estudiante para un plan de estudios dado.
        Aplica filtros de workspace según el tipo de workspace.
        """
        try:
            # Obtener IDs de módulos del plan de estudios
            module_query = {"study_plan_id": ObjectId(study_plan_id)}
            
            # Aplicar filtros de workspace si están presentes
            if workspace_type and workspace_user_id:
                from src.workspaces.services import WorkspaceService
                workspace_service = WorkspaceService()
                module_query = workspace_service.apply_workspace_filters(
                    module_query, workspace_type, workspace_user_id, class_id
                )
            
            module_objs = self.db.modules.find(module_query, {"_id": 1})
            module_ids = [m["_id"] for m in module_objs]
            
            # Buscar módulos virtuales del estudiante para esos módulos
            virtual_module_query = {
                "student_id": ObjectId(student_id),
                "module_id": {"$in": module_ids}
            }
            
            vmods = list(self.collection.find(virtual_module_query))
            
            # Convertir ObjectId a string
            for vm in vmods:
                vm["_id"] = str(vm["_id"])
                vm["module_id"] = str(vm["module_id"])
                vm["student_id"] = str(vm["student_id"])
            return vmods
        except Exception as e:
            logging.error(f"Error al listar módulos virtuales: {str(e)}")
            return []

    def get_module_progress(self, virtual_module_id: str) -> Dict[str, Any]:
        """
        Calcula y retorna el progreso actual de un módulo virtual.
        
        Args:
            virtual_module_id: ID del módulo virtual
            
        Returns:
            Dict con información de progreso del módulo
        """
        try:
            # Obtener el módulo virtual
            virtual_module = self.collection.find_one({"_id": ObjectId(virtual_module_id)})
            if not virtual_module:
                return {
                    "success": False,
                    "error": "Módulo virtual no encontrado"
                }
            
            # Obtener todos los temas del módulo
            all_topics = list(self.db.virtual_topics.find({
                "virtual_module_id": ObjectId(virtual_module_id)
            }))
            
            if not all_topics:
                return {
                    "success": True,
                    "virtual_module_id": virtual_module_id,
                    "progress_percentage": 0.0,
                    "completion_status": "not_started",
                    "total_topics": 0,
                    "completed_topics": 0,
                    "topics_breakdown": [],
                    "should_trigger_next_module": False
                }
            
            # Calcular métricas de progreso
            total_progress = sum(topic.get("progress", 0) for topic in all_topics)
            average_progress = round(total_progress / len(all_topics), 2)
            
            # Contar temas completados
            completed_topics = len([t for t in all_topics if t.get("completion_status") == "completed"])
            
            # Determinar estado del módulo
            if completed_topics == len(all_topics):
                module_status = "completed"
            elif completed_topics > 0:
                module_status = "in_progress"
            else:
                module_status = "not_started"
            
            # Verificar si debe disparar generación del siguiente módulo (80% threshold)
            should_trigger_next_module = average_progress >= 80.0
            
            # Preparar breakdown de temas
            topics_breakdown = []
            for topic in all_topics:
                topics_breakdown.append({
                    "topic_id": str(topic["_id"]),
                    "original_topic_id": str(topic.get("topic_id", "")),
                    "progress": topic.get("progress", 0),
                    "completion_status": topic.get("completion_status", "not_started"),
                    "locked": topic.get("locked", True)
                })
            
            # Actualizar el progreso en la base de datos si ha cambiado
            current_db_progress = virtual_module.get("progress", 0)
            if abs(current_db_progress - average_progress) > 0.01:  # Solo actualizar si hay diferencia significativa
                self.collection.update_one(
                    {"_id": ObjectId(virtual_module_id)},
                    {"$set": {
                        "progress": average_progress,
                        "completion_status": module_status,
                        "updated_at": datetime.now()
                    }}
                )
            
            return {
                "success": True,
                "virtual_module_id": virtual_module_id,
                "progress_percentage": average_progress,
                "completion_status": module_status,
                "total_topics": len(all_topics),
                "completed_topics": completed_topics,
                "topics_breakdown": topics_breakdown,
                "should_trigger_next_module": should_trigger_next_module,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error calculando progreso del módulo {virtual_module_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Error interno: {str(e)}"
            }

    def _update_module_progress_from_topic(self, virtual_topic: Dict):
        """
        Actualiza el progreso del módulo virtual cuando se completa un tema.
        Dispara automáticamente la generación del siguiente módulo al alcanzar 80%.
        """
        try:
            virtual_module_id = virtual_topic["virtual_module_id"]
            
            # Obtener todos los temas del módulo
            all_topics = list(self.db.virtual_topics.find({
                "virtual_module_id": virtual_module_id
            }))
            
            if not all_topics:
                return
            
            # Calcular progreso total del módulo
            total_progress = sum(topic.get("progress", 0) for topic in all_topics)
            average_progress = total_progress / len(all_topics)
            
            # Determinar estado del módulo
            completed_topics = len([t for t in all_topics if t.get("completion_status") == "completed"])
            
            if completed_topics == len(all_topics):
                module_status = "completed"
            elif completed_topics > 0:
                module_status = "in_progress"
            else:
                module_status = "not_started"
            
            # Actualizar módulo virtual
            self.db.virtual_modules.update_one(
                {"_id": virtual_module_id},
                {"$set": {
                    "progress": round(average_progress, 2),
                    "completion_status": module_status,
                    "updated_at": datetime.now()
                }}
            )
            
            logging.info(f"Progreso del módulo {virtual_module_id} actualizado: {average_progress}%")
            
            # Verificar si debe disparar generación del siguiente módulo (80% threshold)
            if average_progress >= 80.0:
                try:
                    # Obtener información del módulo virtual
                    virtual_module = self.db.virtual_modules.find_one({"_id": virtual_module_id})
                    if virtual_module:
                        student_id = str(virtual_module["student_id"])
                        module_id = str(virtual_module["module_id"])
                        
                        logging.info(f"Triggering next module generation: progress {average_progress}% >= 80% for module {module_id}")
                        
                        # Importar y usar FastVirtualModuleGenerator para generar siguiente módulo
                        from src.virtual.services import FastVirtualModuleGenerator
                        fast_generator = FastVirtualModuleGenerator()
                        
                        # Obtener el plan de estudios
                        original_module = self.db.modules.find_one({"_id": ObjectId(module_id)})
                        if original_module:
                            study_plan_id = original_module.get("study_plan_id")
                            
                            # Buscar siguiente módulo disponible
                            all_plan_modules = list(self.db.modules.find({
                                "study_plan_id": study_plan_id
                            }).sort("created_at", 1))
                            
                            # Encontrar el módulo actual y el siguiente
                            current_index = -1
                            for i, mod in enumerate(all_plan_modules):
                                if str(mod["_id"]) == module_id:
                                    current_index = i
                                    break
                            
                            if current_index != -1 and current_index + 1 < len(all_plan_modules):
                                next_module = all_plan_modules[current_index + 1]
                                
                                # Verificar si el siguiente módulo ya fue generado
                                existing_vm = self.db.virtual_modules.find_one({
                                    "student_id": ObjectId(student_id),
                                    "module_id": next_module["_id"]
                                })
                                
                                if not existing_vm:
                                    # Generar siguiente módulo en cola
                                    fast_generator.generate_single_module(
                                        student_id=student_id,
                                        module=next_module
                                    )
                                    logging.info(f"Siguiente módulo {next_module['_id']} encolado para generación automática")
                                else:
                                    logging.info(f"Siguiente módulo {next_module['_id']} ya existe para estudiante {student_id}")
                            else:
                                logging.info("No hay más módulos disponibles en el plan de estudios")
                        
                except Exception as trigger_error:
                    logging.error(f"Error disparando generación automática del siguiente módulo: {trigger_error}")
            
        except Exception as e:
            logging.error(f"Error actualizando progreso del módulo: {str(e)}")

class VirtualTopicService(VerificationBaseService):
    """
    Servicio para gestionar temas de módulos virtuales.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_topics")
        
    def create_topic(self, topic_data: dict) -> Tuple[bool, str]:
        """
        Crea un nuevo tema para un módulo virtual.
        
        Args:
            topic_data: Datos del tema a crear
            
        Returns:
            Tuple[bool, str]: (Éxito, mensaje o ID)
        """
        try:
            # Verificar que el módulo existe
            if "virtual_module_id" in topic_data and not self.check_module_exists(topic_data["virtual_module_id"]):
                return False, "Módulo virtual no encontrado"
                
            topic = VirtualTopic(**topic_data)
            result = self.collection.insert_one(topic.to_dict())
            return True, str(result.inserted_id)
        except Exception as e:
            return False, str(e)
            
    def check_module_exists(self, module_id: str) -> bool:
        """
        Verifica si un módulo virtual existe.
        
        Args:
            module_id: ID del módulo a verificar
            
        Returns:
            bool: True si el módulo existe, False en caso contrario
        """
        try:
            module = self.db.virtual_modules.find_one({"_id": ObjectId(module_id)})
            return module is not None
        except Exception:
            return False

    def get_module_topics(self, module_id: str) -> List[Dict]:
        try:
            topics = list(
                self.collection
                .find({"virtual_module_id": ObjectId(module_id)})
                .sort("order", 1)
            )
            
            # Convertir ObjectIds a strings
            for topic in topics:
                topic["_id"] = str(topic["_id"])
                topic["virtual_module_id"] = str(topic["virtual_module_id"])
                topic["locked"] = topic.get("locked", False)
                topic["status"] = topic.get("status", "")
                
            return topics
        except Exception as e:
            print(f"Error al obtener temas del módulo: {str(e)}")
            return []

    def get_topic_contents(self, virtual_topic_id: str) -> List[Dict]:
        """
        Obtiene todos los contenidos de un tema virtual específico.
        """
        try:
            # 1. Obtener el tema virtual para conseguir el ID del tema original
            virtual_topic = self.db.virtual_topics.find_one(
                {"_id": ObjectId(virtual_topic_id)}
            )
            if not virtual_topic:
                logging.warning(f"No se encontró el tema virtual con ID: {virtual_topic_id}")
                return []

            original_topic_id = virtual_topic.get("topic_id")

            # 2. Obtener los contenidos virtuales (el nuevo sistema)
            virtual_contents = list(
                self.db.virtual_topic_contents
                .find({"virtual_topic_id": ObjectId(virtual_topic_id)})
                .sort([("order", 1), ("created_at", 1)])
            )

            # 3. Obtener los recursos del tema original (sistema legacy para compatibilidad)
            # Esto evita que el frontend entre en un bucle si todavía depende de 'topic_resources'
            topic_resources = list(self.db.topic_resources.find(
                {"topic_id": ObjectId(original_topic_id)}
            ).sort("created_at", 1))
            
            # 4. Unificar los resultados en una sola lista
            all_content = []

            # Formatear contenidos virtuales
            for content in virtual_contents:
                content["_id"] = str(content["_id"])
                content["virtual_topic_id"] = str(content["virtual_topic_id"])
                content["content_id"] = str(content["content_id"])
                content["student_id"] = str(content["student_id"])
                
                # NUEVO: Enriquecer con datos del contenido original
                original_content = self.db.topic_contents.find_one({"_id": content["content_id"]})
                if original_content:
                    # Incluir personalization_markers y slide_template del contenido original
                    content["original_personalization_markers"] = original_content.get("personalization_markers", {})
                    content["original_slide_template"] = original_content.get("slide_template", "")
                    content["original_content_type"] = original_content.get("content_type", "unknown")
                    content["original_content"] = original_content.get("content", "")
                    content["original_interactive_data"] = original_content.get("interactive_data", {})
                
                # Añadir un campo para distinguir el tipo de contenido en el frontend
                content["source_type"] = "virtual_content"
                all_content.append(content)

            # Formatear y añadir recursos legacy
            for resource in topic_resources:
                resource["_id"] = str(resource["_id"])
                resource["topic_id"] = str(resource["topic_id"])
                # Simular la estructura de un contenido virtual para que el frontend lo pueda renderizar
                all_content.append({
                    "_id": resource["_id"],
                    "content_id": resource["_id"],  # Usar el mismo ID para referencia
                    "virtual_topic_id": virtual_topic_id,
                    "student_id": str(virtual_topic.get("student_id")),
                    "personalization_data": {
                        "content_type": resource.get("type", "resource"),
                    },
                    "interaction_tracking": {"completion_status": "not_started"},
                    "legacy_resource_data": resource, # Incluir todos los datos originales
                    "source_type": "legacy_resource",
                    # Para recursos legacy, no hay marcadores ni plantillas
                    "original_personalization_markers": {},
                    "original_slide_template": "",
                    "original_content_type": "legacy_resource"
                })

            return all_content
        except Exception as e:
            logging.error(f"Error al obtener contenidos del tema virtual: {str(e)}")
            return []
    
    def trigger_next_topic_generation(self, topic_id: str, progress: float) -> Tuple[bool, Dict]:
        """
        Activa la generación del siguiente tema cuando el progreso supera el 80%.
        
        Args:
            topic_id: ID del tema actual
            progress: Progreso actual (0-100)
            
        Returns:
            Tuple[bool, Dict]: (Éxito, resultado con información de generación)
        """
        try:
            # Validar progreso
            if progress < 80:
                return False, {
                    "message": "El progreso debe ser mayor al 80% para activar la generación",
                    "error": "PROGRESS_TOO_LOW"
                }
            
            # Obtener el tema actual
            topic = self.collection.find_one({"_id": ObjectId(topic_id)})
            if not topic:
                return False, {
                    "message": "Tema no encontrado",
                    "error": "TOPIC_NOT_FOUND"
                }
            
            # Usar el servicio de cola optimizada para activar la generación
            queue_service = OptimizedQueueService()
            result = queue_service.trigger_on_progress(topic_id, progress)
            
            # Verificar si hay error en el resultado
            if "error" in result:
                return False, {
                    "message": result.get("error", "Error desconocido"),
                    "error": "QUEUE_ERROR"
                }
            
            # Si no se activó el trigger
            if not result.get("triggered", False):
                return False, {
                    "message": result.get("reason", "Trigger no ejecutado"),
                    "error": "TRIGGER_NOT_EXECUTED",
                    "reason": result.get("reason")
                }
            
            # Extraer información de la cola
            queue_maintenance = result.get("queue_maintenance", {})
            generated_topics_list = queue_maintenance.get("details", [])
            
            return True, {
                "message": "Generación del siguiente tema activada exitosamente",
                "triggered": True,
                "progress": progress,
                "topic_completed": result.get("topic_completed", False),
                "generated_topics": generated_topics_list,
                "generated_topics_count": len(generated_topics_list),
                "has_next": queue_maintenance.get("remaining_original", 0) > 0,
                "queue_maintenance": queue_maintenance
            }
                
        except Exception as e:
            logging.error(f"Error en trigger_next_topic_generation: {str(e)}")
            return False, {
                "message": f"Error interno: {str(e)}",
                "error": "INTERNAL_ERROR"
            }

# QuizService eliminado - Los quizzes ahora se manejan como TopicContent con content_type="quiz"
# La funcionalidad de evaluación se migró al sistema unificado de ContentResult


class ContentChangeDetector(VerificationBaseService):
    """
    Servicio para detectar cambios en el contenido de módulos.
    Utiliza hashing para comparar versiones y activar actualizaciones.
    """
    def __init__(self):
        super().__init__(collection_name="modules")
        
    def calculate_module_hash(self, module_id: str) -> str:
        """
        Calcula un hash del contenido completo del módulo.
        
        Args:
            module_id: ID del módulo
            
        Returns:
            str: Hash MD5 del contenido del módulo
        """
        import hashlib
        
        try:
            # Obtener módulo
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return ""
            
            # Obtener temas del módulo
            topics = list(self.db.topics.find({"module_id": ObjectId(module_id)}))
            
            # Obtener evaluaciones del módulo a través de sus temas
            topic_ids = [t["_id"] for t in topics]
            evaluations = []
            if topic_ids:
                evaluations = list(self.db.evaluations.find({"topic_ids": {"$in": topic_ids}}))
            
            # Crear string con el contenido relevante
            content_string = ""
            
            # Añadir datos del módulo
            content_string += f"module:{module.get('name', '')}"
            content_string += f"learning_outcomes:{str(module.get('learning_outcomes', []))}"
            content_string += f"evaluation_rubric:{str(module.get('evaluation_rubric', {}))}"
            
            # Añadir temas ordenados por ID
            for topic in sorted(topics, key=lambda x: str(x["_id"])):
                content_string += f"topic:{topic.get('name', '')}"
                content_string += f"theory:{topic.get('theory_content', '')}"
                content_string += f"difficulty:{topic.get('difficulty', '')}"
                content_string += f"resources:{str(topic.get('resources', []))}"
            
            # Añadir evaluaciones ordenadas por ID
            for evaluation in sorted(evaluations, key=lambda x: str(x["_id"])):
                content_string += f"eval:{evaluation.get('title', '')}"
                content_string += f"desc:{evaluation.get('description', '')}"
                content_string += f"criteria:{str(evaluation.get('criteria', []))}"
                content_string += f"weight:{evaluation.get('weight', 0)}"
            
            # Calcular hash MD5
            hash_md5 = hashlib.md5(content_string.encode()).hexdigest()
            return hash_md5
            
        except Exception as e:
            logging.error(f"Error calculando hash del módulo {module_id}: {str(e)}")
            return ""
    
    def detect_changes(self, module_id: str) -> Dict:
        """
        Detecta cambios en un módulo comparando con la última versión.
        
        Args:
            module_id: ID del módulo
            
        Returns:
            Dict con información de cambios detectados
        """
        try:
            # Calcular hash actual
            current_hash = self.calculate_module_hash(module_id)
            if not current_hash:
                return {"has_changes": False, "error": "No se pudo calcular hash"}
            
            # Obtener módulo para verificar versiones
            module = self.collection.find_one({"_id": ObjectId(module_id)})
            if not module:
                return {"has_changes": False, "error": "Módulo no encontrado"}
            
            content_versions = module.get("content_versions", [])
            
            # Si no hay versiones previas, es la primera vez
            if not content_versions:
                # Crear primera versión
                version_record = {
                    "hash": current_hash,
                    "timestamp": datetime.now(),
                    "changes": {"initial_version": True}
                }
                
                self.collection.update_one(
                    {"_id": ObjectId(module_id)},
                    {
                        "$push": {"content_versions": version_record},
                        "$set": {"last_content_update": datetime.now()}
                    }
                )
                
                return {
                    "has_changes": False,
                    "is_initial": True,
                    "current_hash": current_hash
                }
            
            # Obtener última versión
            last_version = content_versions[-1]
            last_hash = last_version.get("hash", "")
            
            # Comparar hashes
            if current_hash != last_hash:
                # Hay cambios - crear nueva versión
                version_record = {
                    "hash": current_hash,
                    "timestamp": datetime.now(),
                    "changes": {
                        "previous_hash": last_hash,
                        "change_detected": True
                    }
                }
                
                self.collection.update_one(
                    {"_id": ObjectId(module_id)},
                    {
                        "$push": {"content_versions": version_record},
                        "$set": {"last_content_update": datetime.now()}
                    }
                )
                
                return {
                    "has_changes": True,
                    "current_hash": current_hash,
                    "previous_hash": last_hash,
                    "change_timestamp": datetime.now()
                }
            
            # No hay cambios
            return {
                "has_changes": False,
                "current_hash": current_hash,
                "last_check": datetime.now()
            }
            
        except Exception as e:
            logging.error(f"Error detectando cambios en módulo {module_id}: {str(e)}")
            return {"has_changes": False, "error": str(e)}
    
    def schedule_incremental_updates(self, module_id: str, change_info: Dict) -> List[str]:
        """
        Programa actualizaciones incrementales para módulos virtuales afectados.
        
        Args:
            module_id: ID del módulo que cambió
            change_info: Información sobre los cambios detectados
            
        Returns:
            List[str]: IDs de las tareas de actualización creadas
        """
        try:
            # Encontrar módulos virtuales que usan este módulo
            virtual_modules = list(self.db.virtual_modules.find({
                "module_id": ObjectId(module_id),
                "status": "active"
            }))
            
            if not virtual_modules:
                return []
            
            # Importar servicio de cola
            from .services import ServerlessQueueService
            queue_service = ServerlessQueueService()
            
            created_tasks = []
            
            for vm in virtual_modules:
                student_id = str(vm["student_id"])
                
                # Crear tarea de actualización incremental
                success, task_id = queue_service.enqueue_generation_task(
                    student_id=student_id,
                    module_id=module_id,
                    task_type="update",
                    priority=3,  # Prioridad media para actualizaciones
                    payload={
                        "change_info": change_info,
                        "virtual_module_id": str(vm["_id"]),
                        "update_type": "content_change"
                    }
                )
                
                if success:
                    created_tasks.append(task_id)
            
            return created_tasks
            
        except Exception as e:
            logging.error(f"Error programando actualizaciones incrementales: {str(e)}")
            return []


class ServerlessQueueService(VerificationBaseService):
    """
    Servicio de cola para generación progresiva adaptado a arquitectura serverless.
    Gestiona tareas de generación de módulos virtuales con límites de tiempo.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_generation_tasks")
        
    def enqueue_generation_task(self, student_id: str, module_id: str, 
                              task_type: str = "generate", priority: int = 5, 
                              payload: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Encola una tarea de generación de módulo virtual.
        
        Args:
            student_id: ID del estudiante
            module_id: ID del módulo a generar
            task_type: Tipo de tarea ("generate", "update", "enhance")
            priority: Prioridad (1=alta, 10=baja)
            payload: Datos adicionales para la tarea
            
        Returns:
            Tuple[bool, str]: (Éxito, ID de tarea o mensaje de error)
        """
        try:
            # Verificar si ya existe una tarea pendiente para este módulo y estudiante
            existing_task = self.collection.find_one({
                "student_id": ObjectId(student_id),
                "module_id": ObjectId(module_id),
                "status": {"$in": ["pending", "processing"]}
            })
            
            if existing_task:
                return False, f"Ya existe una tarea {existing_task['status']} para este módulo"
            
            # Crear nueva tarea
            task = VirtualGenerationTask(
                student_id=student_id,
                module_id=module_id,
                task_type=task_type,
                priority=priority,
                payload=payload or {}
            )
            
            result = self.collection.insert_one(task.to_dict())
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error al encolar tarea: {str(e)}")
            return False, str(e)
    
    def get_next_tasks(self, limit: int = 2, max_duration: int = 45) -> List[Dict]:
        """
        Obtiene las siguientes tareas a procesar, respetando límites de tiempo.
        
        Args:
            limit: Máximo número de tareas a obtener
            max_duration: Duración máxima total estimada (segundos)
            
        Returns:
            Lista de tareas a procesar
        """
        try:
            # Buscar tareas pendientes ordenadas por prioridad y fecha
            tasks = list(self.collection.find({
                "status": "pending",
                "attempts": {"$lt": 3}  # No reintentar tareas que han fallado mucho
            }).sort([("priority", 1), ("created_at", 1)]).limit(limit * 2))
            
            # Seleccionar tareas que quepan en el tiempo disponible
            selected_tasks = []
            total_duration = 0
            
            for task in tasks:
                estimated_duration = task.get("estimated_duration", 30)
                if total_duration + estimated_duration <= max_duration:
                    selected_tasks.append(task)
                    total_duration += estimated_duration
                    
                if len(selected_tasks) >= limit:
                    break
            
            # Convertir ObjectIds a strings
            for task in selected_tasks:
                task["_id"] = str(task["_id"])
                task["student_id"] = str(task["student_id"])
                task["module_id"] = str(task["module_id"])
            
            return selected_tasks
            
        except Exception as e:
            logging.error(f"Error al obtener próximas tareas: {str(e)}")
            return []
    
    def mark_task_processing(self, task_id: str) -> bool:
        """
        Marca una tarea como en procesamiento.
        
        Args:
            task_id: ID de la tarea
            
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(task_id), "status": "pending"},
                {
                    "$set": {
                        "status": "processing",
                        "processing_started_at": datetime.now()
                    },
                    "$inc": {"attempts": 1}
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logging.error(f"Error al marcar tarea como procesando: {str(e)}")
            return False
    
    def complete_task(self, task_id: str, result_data: Optional[Dict] = None) -> bool:
        """
        Marca una tarea como completada.
        
        Args:
            task_id: ID de la tarea
            result_data: Datos del resultado (opcional)
            
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            update_data = {
                "status": "completed",
                "completed_at": datetime.now()
            }
            
            if result_data:
                update_data["result"] = result_data
            
            result = self.collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logging.error(f"Error al completar tarea: {str(e)}")
            return False
    
    def fail_task(self, task_id: str, error_message: str) -> bool:
        """
        Marca una tarea como fallida y programa reintento si es posible.
        
        Args:
            task_id: ID de la tarea
            error_message: Mensaje de error
            
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            # Obtener la tarea actual
            task = self.collection.find_one({"_id": ObjectId(task_id)})
            if not task:
                return False
            
            attempts = task.get("attempts", 0)
            max_attempts = task.get("max_attempts", 3)
            
            update_data = {
                "error_message": error_message,
                "processing_started_at": None
            }
            
            # Si ya se agotaron los intentos, marcar como fallida definitivamente
            if attempts >= max_attempts:
                update_data["status"] = "failed"
                update_data["completed_at"] = datetime.now()
            else:
                # Programar para reintento
                update_data["status"] = "pending"
            
            result = self.collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logging.error(f"Error al fallar tarea: {str(e)}")
            return False
    
    def get_student_queue_status(self, student_id: str) -> Dict:
        """
        Obtiene el estado de la cola para un estudiante específico.
        
        Args:
            student_id: ID del estudiante
            
        Returns:
            Dict con estadísticas de la cola del estudiante
        """
        try:
            student_oid = ObjectId(student_id)
            
            # Contar tareas por estado
            pending = self.collection.count_documents({
                "student_id": student_oid, 
                "status": "pending"
            })
            
            processing = self.collection.count_documents({
                "student_id": student_oid, 
                "status": "processing"
            })
            
            completed = self.collection.count_documents({
                "student_id": student_oid, 
                "status": "completed"
            })
            
            failed = self.collection.count_documents({
                "student_id": student_oid, 
                "status": "failed"
            })
            
            # Obtener última tarea completada
            last_completed = self.collection.find_one({
                "student_id": student_oid,
                "status": "completed"
            }, sort=[("completed_at", -1)])
            
            return {
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "total": pending + processing + completed + failed,
                "last_completed_at": last_completed.get("completed_at") if last_completed else None
            }
            
        except Exception as e:
            logging.error(f"Error al obtener estado de cola: {str(e)}")
            return {
                "pending": 0,
                "processing": 0, 
                "completed": 0,
                "failed": 0,
                "total": 0,
                "last_completed_at": None
            }
    
    def cleanup_old_tasks(self, days_old: int = 7) -> int:
        """
        Limpia tareas antiguas completadas o fallidas.
        
        Args:
            days_old: Días de antigüedad para limpiar
            
        Returns:
            int: Número de tareas eliminadas
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            result = self.collection.delete_many({
                "status": {"$in": ["completed", "failed"]},
                "completed_at": {"$lt": cutoff_date}
            })
            
            return result.deleted_count
            
        except Exception as e:
            logging.error(f"Error al limpiar tareas antiguas: {str(e)}")
            return 0


class FastVirtualModuleGenerator(VerificationBaseService):
    """
    Generador optimizado para crear módulos virtuales rápidamente.
    Diseñado para funcionar dentro de los límites de tiempo serverless.
    """

    EVALUATION_CONTENT_TYPES = {
        "quiz",
        "exam",
        "formative_test",
        "summative_test",
        "project",
        "evaluation",
        "assessment",
        "interactive_quiz",
        "diagnostic_quiz"
    }

    INTERACTIVE_CONTENT_TYPES = {
        "interactive",
        "interactive_slide",
        "interactive_activity",
        "interactive_exercise",
        "interactive_video",
        "simulation",
        "virtual_lab",
        "lab",
        "game",
        "diagram",
        "infographic",
        "case_study",
        "scenario",
        "microlesson",
        "microlab",
        "explorer"
    }

    EXCLUDED_CONTENT_TYPES = {
        "slide_template"
    }

    def __init__(self):
        super().__init__(collection_name="virtual_modules")
        
    def generate_single_module(self, student_id: str, module_id: str, 
                             timeout: int = 45) -> Tuple[bool, str]:
        """
        Genera un módulo virtual optimizado para velocidad.
        
        Args:
            student_id: ID del estudiante
            module_id: ID del módulo original
            timeout: Tiempo límite en segundos
            
        Returns:
            Tuple[bool, str]: (Éxito, ID del módulo virtual o mensaje de error)
        """
        start_time = datetime.now()
        
        try:
            # 1. Verificar si ya existe el módulo virtual
            existing = self.collection.find_one({
                "student_id": ObjectId(student_id),
                "module_id": ObjectId(module_id)
            })
            
            if existing:
                return True, str(existing["_id"])
            
            # 2. Obtener datos del módulo original
            original_module = self.db.modules.find_one({"_id": ObjectId(module_id)})
            if not original_module:
                return False, "Módulo original no encontrado"
            
            # 3. Obtener perfil cognitivo del estudiante
            student = self.db.users.find_one({"_id": ObjectId(student_id)})
            cognitive_profile = student.get("cognitive_profile", {}) if student else {}
            
            # 4. Crear módulo virtual básico
            virtual_module_data = {
                "study_plan_id": str(original_module["study_plan_id"]),
                "module_id": module_id,
                "student_id": student_id,
                "adaptations": {
                    "cognitive_profile": cognitive_profile,
                    "generation_method": "fast",
                    "generated_at": datetime.now()
                },
                "generation_status": "generating",
                "generation_progress": 50
            }
            
            # Usar el modelo para asegurar la conversión a ObjectId
            module = VirtualModule(**virtual_module_data)
            result = self.collection.insert_one(module.to_dict())
            virtual_module_id = str(result.inserted_id)
            
            # 5. Generar temas virtuales de forma optimizada
            self._generate_virtual_topics_fast(
                module_id, student_id, virtual_module_id,
                cognitive_profile,
                preferences=None
            )
            
            # 6. Actualizar estado del módulo virtual
            self.collection.update_one(
                {"_id": ObjectId(virtual_module_id)},
                {
                    "$set": {
                        "generation_status": "completed",
                        "generation_progress": 100,
                        "completed_at": datetime.now()
                    }
                }
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logging.info(f"Módulo virtual generado en {elapsed:.2f} segundos")
            
            return True, virtual_module_id
            
        except Exception as e:
            logging.error(f"Error al generar módulo virtual: {str(e)}")
            return False, str(e)
    
    def _generate_virtual_topics_fast(self, module_id: str, student_id: str,
                                    virtual_module_id: str, cognitive_profile: Dict,
                                    preferences: Dict = None, initial_batch_size: int = 2):
        """
        Genera temas virtuales optimizados para velocidad.
        """
        try:
            # Obtener temas del módulo original que estén publicados
            topics = list(self.db.topics.find({
                "module_id": ObjectId(module_id),
                "published": True
            }).sort("created_at", 1))  # Ordenar por fecha de creación
            
            if not topics:
                logging.warning(f"No se encontraron temas publicados para el módulo {module_id}. El módulo virtual se generará sin temas.")
                return

            # Limitar al lote inicial
            topics_to_generate = topics[:initial_batch_size]
            existing_count = self.db.virtual_topics.count_documents({
                "virtual_module_id": ObjectId(virtual_module_id)
            })
            
            logging.info(f"Generando lote inicial de {len(topics_to_generate)} temas para el módulo virtual {virtual_module_id}. "
                         f"({len(topics) - len(topics_to_generate)} pendientes)")

            # Generar contenido para cada tema
            for idx, topic in enumerate(topics_to_generate):
                try:
                    topic_id = str(topic["_id"])
                    topic_order = existing_count + idx
                    
                    # Crear tema virtual básico
                    virtual_topic_data = {
                        "topic_id": topic_id,
                        "student_id": student_id,
                        "virtual_module_id": virtual_module_id,
                        "order": topic_order,
                        # El modelo no incluye 'name' ni 'description', se obtienen del topic original si es necesario
                        "adaptations": {
                            "cognitive_profile": cognitive_profile,
                            "difficulty_adjustment": self._calculate_quick_difficulty_adjustment(
                                topic, cognitive_profile
                            )
                        },
                        "status": "active", # Los temas del lote inicial deben estar activos
                        "locked": False,  # Los temas del lote inicial están desbloqueados
                        "progress": 0.0,
                        "completion_status": "not_started"
                    }
                    
                    # Insertar tema virtual usando el modelo
                    virtual_topic = VirtualTopic(**virtual_topic_data)
                    result = self.db.virtual_topics.insert_one(virtual_topic.to_dict())
                    virtual_topic_id = str(result.inserted_id)
                    
                    # Generar contenido personalizado para el tema
                    self._generate_topic_contents_for_sync(
                        topic_id=topic_id,
                        virtual_topic_id=virtual_topic_id,
                        cognitive_profile=cognitive_profile,
                        student_id=student_id,
                        preferences=preferences
                    )
                except Exception as e_topic:
                    logging.error(f"Error generando tema virtual para {topic['_id']}: {e_topic}")

        except Exception as e:
            logging.error(f"Error en _generate_virtual_topics_fast: {str(e)}")

    def synchronize_module_content(self, virtual_module_id: str) -> Tuple[bool, Dict]:
        """
        Sincroniza un módulo virtual existente con su módulo original.
        Aplica cambios, añade nuevo contenido y desactiva el obsoleto.
        """
        try:
            logging.info(f"Iniciando sincronización para el módulo virtual: {virtual_module_id}")
            report = {"added": [], "updated": [], "removed": [], "errors": []}

            virtual_module = self.db.virtual_modules.find_one({"_id": ObjectId(virtual_module_id)})
            if not virtual_module:
                return False, {"error": "Módulo virtual no encontrado"}

            module_id = virtual_module["module_id"]
            student_id = virtual_module["student_id"]
            
            student = self.db.users.find_one({"_id": student_id})
            cognitive_profile = student.get("cognitive_profile", {}) if student else {}

            # 1. Comparar Temas
            original_topics = list(self.db.topics.find({"module_id": module_id, "published": True}))
            virtual_topics = list(self.db.virtual_topics.find({"virtual_module_id": ObjectId(virtual_module_id)}))
            
            original_topic_ids = {str(t["_id"]) for t in original_topics}
            virtual_topic_ids = {str(vt["topic_id"]) for vt in virtual_topics}

            # Temas a añadir
            topics_to_add = [t for t in original_topics if str(t["_id"]) not in virtual_topic_ids]
            for topic in topics_to_add:
                try:
                    logging.info(f"Sincronización: añadiendo nuevo tema {topic['_id']} a {virtual_module_id}")
                    
                    # Crear tema virtual básico usando la misma lógica que _generate_virtual_topics_fast
                    virtual_topic_data = {
                        "topic_id": ObjectId(str(topic["_id"])),
                        "student_id": student_id,
                        "virtual_module_id": ObjectId(virtual_module_id),
                        "name": topic.get("name"),
                        "description": topic.get("theory_content", ""),
                        "adaptations": {
                            "cognitive_profile": cognitive_profile,
                            "difficulty_adjustment": self._calculate_quick_difficulty_adjustment(
                                topic, cognitive_profile
                            )
                        },
                        "status": "locked",
                        "locked": True,  # Los temas añadidos por sincronización están bloqueados por defecto
                        "progress": 0.0,
                        "completion_status": "not_started",
                        "created_at": datetime.now()
                    }
                    
                    # Insertar tema virtual
                    result = self.db.virtual_topics.insert_one(virtual_topic_data)
                    virtual_topic_id = str(result.inserted_id)
                    
                    # Generar contenido personalizado para el tema nuevo
                    self._generate_topic_contents_for_sync(
                        topic_id=str(topic["_id"]),
                        virtual_topic_id=virtual_topic_id,
                        cognitive_profile=cognitive_profile,
                        student_id=str(student_id),
                        preferences={}
                    )
                    
                    report["added"].append({"type": "topic", "id": str(topic["_id"]), "virtual_topic_id": virtual_topic_id})
                except Exception as e:
                    report["errors"].append({"type": "topic_add", "id": str(topic["_id"]), "error": str(e)})

            # Temas a eliminar (despublicados)
            topics_to_remove_ids = [vt["_id"] for vt in virtual_topics if str(vt["topic_id"]) not in original_topic_ids]
            if topics_to_remove_ids:
                self.db.virtual_topics.update_many(
                    {"_id": {"$in": topics_to_remove_ids}},
                    {"$set": {"status": "archived", "updated_at": datetime.now()}}
                )
                report["removed"].extend([{"type": "topic", "id": str(tid)} for tid in topics_to_remove_ids])

            # 2. Comparar Contenidos para cada tema existente
            for vt in virtual_topics:
                original_topic_id = vt["topic_id"]
                
                original_contents = list(self.db.topic_contents.find({"topic_id": original_topic_id}))
                virtual_contents = list(self.db.virtual_topic_contents.find({"virtual_topic_id": vt["_id"]}))

                original_content_ids = {str(c["_id"]) for c in original_contents}
                virtual_content_ids = {str(vc["content_id"]) for vc in virtual_contents}

                # Contenido a añadir
                contents_to_add = [c for c in original_contents if str(c["_id"]) not in virtual_content_ids]
                for content in contents_to_add:
                    try:
                        logging.info(f"Sincronización: añadiendo nuevo contenido {content['_id']} a virtual_topic {vt['_id']}")
                        
                        # Crear VirtualTopicContent personalizado para el estudiante
                        virtual_content_data = {
                            "virtual_topic_id": vt["_id"],
                            "content_id": content["_id"],
                            "student_id": student_id,
                            "personalization_data": {
                                "adapted_for_profile": cognitive_profile,
                                "sync_generated": True,
                                "sync_date": datetime.now()
                            },
                            "adapted_content": None,  # Usar contenido original sin adaptación por ahora
                            "interaction_tracking": {
                                "access_count": 0,
                                "total_time_spent": 0,
                                "last_accessed": None,
                                "completion_status": "not_started",
                                "completion_percentage": 0.0,
                                "sessions": 0,
                                "best_score": None,
                                "avg_score": None,
                                "interactions": []
                            },
                            "access_permissions": {},
                            "status": "active",
                            "created_at": datetime.now(),
                            "updated_at": datetime.now()
                        }
                        
                        # Propagar render_engine e instance_id si el contenido original es una plantilla HTML
                        if content.get("render_engine") == "html_template":
                            virtual_content_data["render_engine"] = "html_template"
                            if content.get("instance_id"):
                                virtual_content_data["instance_id"] = content["instance_id"]

                        # Insertar contenido virtual
                        result = self.db.virtual_topic_contents.insert_one(virtual_content_data)
                        virtual_content_id = str(result.inserted_id)
                        
                        report["added"].append({"type": "content", "id": str(content["_id"]), "virtual_content_id": virtual_content_id})
                    except Exception as e:
                        report["errors"].append({"type": "content_add", "id": str(content["_id"]), "error": str(e)})

                # Contenido a eliminar
                contents_to_remove_ids = [vc["_id"] for vc in virtual_contents if str(vc["content_id"]) not in original_content_ids]
                if contents_to_remove_ids:
                    self.db.virtual_topic_contents.update_many(
                        {"_id": {"$in": contents_to_remove_ids}},
                        {"$set": {"status": "archived", "updated_at": datetime.now()}}
                    )
                    report["removed"].extend([{"type": "content", "id": str(cid)} for cid in contents_to_remove_ids])
                
                # Contenido a actualizar (simplificado: por ahora no se detectan cambios internos)
                # En una versión avanzada, se compararía un hash o `updated_at` de `TopicContent` vs `VirtualTopicContent`
                
            # Registrar la actualización en el módulo virtual
            self.db.virtual_modules.update_one(
                {"_id": ObjectId(virtual_module_id)},
                {"$push": {"updates": {
                    "type": "content_sync",
                    "timestamp": datetime.now(),
                    "details": report
                }}}
            )

            logging.info(f"Sincronización completada para {virtual_module_id}. Reporte: {report}")
            return True, report

        except Exception as e:
            logging.error(f"Error fatal durante la sincronización del módulo {virtual_module_id}: {str(e)}")
            return False, {"error": str(e)}

    def _calculate_quick_difficulty_adjustment(self, topic: Dict, 
                                             cognitive_profile: Dict) -> Dict:
        """
        Cálculo rápido de ajuste de dificultad.
        """
        base_difficulty = topic.get("difficulty", "medium")
        adjustment = 0
        
        # Ajustes simples basados en perfil
        if cognitive_profile.get("learning_speed") == "slow":
            adjustment -= 1
        elif cognitive_profile.get("learning_speed") == "fast":
            adjustment += 1
            
        if cognitive_profile.get("needs_support", False):
            adjustment -= 1
            
        # Mapear a dificultad final
        difficulty_map = {"easy": -1, "medium": 0, "hard": 1}
        base_level = difficulty_map.get(base_difficulty, 0)
        new_level = max(-1, min(1, base_level + adjustment))
        final_difficulty = {-1: "easy", 0: "medium", 1: "hard"}[new_level]
        
        return {
            "original": base_difficulty,
            "adjusted": final_difficulty,
            "factor": adjustment
        }

    def _generate_topic_contents_for_sync(self, topic_id: str, virtual_topic_id: str, cognitive_profile: Dict, student_id: str, preferences: Dict = None):
        """
        Genera contenidos virtuales personalizados para un tema específico durante sincronización.
        Integrado con sistema de generación paralela para Fase 2B.
        
        Args:
            topic_id: ID del tema original
            virtual_topic_id: ID del tema virtual recién creado
            cognitive_profile: Perfil cognitivo del estudiante
            student_id: ID del estudiante
        """
        try:
            # Obtener contenidos originales del tema
            original_contents = list(self.db.topic_contents.find({
                "topic_id": ObjectId(topic_id),
                "status": {"$in": ["active", "draft", "approved", "published", "narrative_ready", "skeleton", "html_ready"]}
            }))
            
            if not original_contents:
                logging.warning(f"No se encontraron contenidos para el tema {topic_id}")
                return
            
            # Seleccionar contenidos preservando todas las diapositivas, evaluaciones y recursos
            selected_contents = self._select_personalized_contents(
                original_contents,
                cognitive_profile,
                preferences or {}
            )

            if not selected_contents:
                logging.warning(
                    f"No se pudieron personalizar contenidos para el tema {topic_id}. Usando orden original."
                )
                selected_contents = original_contents

            # Aplicar secuencia estructurada (diapositivas → evaluaciones → recursos)
            try:
                from src.content.structured_sequence_service import StructuredSequenceService
                structured_service = StructuredSequenceService(self.db)

                structured_contents = structured_service.get_structured_content_sequence(
                    topic_id,
                    student_id
                )

                if structured_contents:
                    selected_ids = {str(content["_id"]) for content in selected_contents}
                    ordered_contents = [
                        content for content in structured_contents
                        if str(content["_id"]) in selected_ids
                    ]

                    if len(ordered_contents) != len(selected_contents):
                        remaining_ids = selected_ids - {str(c["_id"]) for c in ordered_contents}
                        if remaining_ids:
                            extras = [
                                content for content in selected_contents
                                if str(content["_id"]) in remaining_ids
                            ]
                            ordered_contents.extend(extras)

                    selected_contents = ordered_contents
                    logging.info(
                        "Secuencia estructurada aplicada para tema %s: %s contenidos (slides=%s, evaluations=%s, resources=%s)",
                        topic_id,
                        len(selected_contents),
                        len([c for c in selected_contents if c.get('content_type') == 'slide']),
                        len([
                            c for c in selected_contents
                            if c.get('content_type') in self.EVALUATION_CONTENT_TYPES
                        ]),
                        len([
                            c for c in selected_contents
                            if c.get('content_type') not in {'slide'}
                            | self.EVALUATION_CONTENT_TYPES
                        ])
                    )
                else:
                    logging.warning(
                        "No se encontró secuencia estructurada para tema %s. Manteniendo orden derivado de selección.",
                        topic_id
                    )
            except Exception as e:
                logging.error(
                    "Error aplicando secuencia estructurada para tema %s: %s",
                    topic_id,
                    str(e)
                )

            logging.info(
                "Generando %s contenidos virtuales para tema %s (virtual_topic_id=%s)",
                len(selected_contents),
                topic_id,
                virtual_topic_id
            )
            self._generate_contents_traditional(
                virtual_topic_id,
                student_id,
                selected_contents,
                cognitive_profile
            )
            
        except Exception as e:
            logging.error(f"Error en _generate_topic_contents_for_sync: {str(e)}")

    def apply_topic_personalization(
        self,
        virtual_topic_id: str,
        selections: List[Dict],
        ordered_content_ids: List[str]
    ) -> Tuple[bool, Dict]:
        """
        Persiste la selección de variantes y el orden final enviado desde el frontend.
        """
        try:
            try:
                topic_oid = ObjectId(virtual_topic_id)
            except Exception:
                return False, {"error": "virtual_topic_id inválido"}

            contents = list(self.db.virtual_topic_contents.find({"virtual_topic_id": topic_oid}))
            if not contents:
                return False, {"error": "No se encontraron contenidos para el tema virtual"}

            document_map = {str(doc["_id"]): doc for doc in contents}
            variants_by_parent: Dict[str, List[Dict]] = defaultdict(list)
            for doc in contents:
                parent_id = doc.get("parent_content_id")
                if parent_id:
                    variants_by_parent[str(parent_id)].append(doc)

            operations: List[UpdateOne] = []
            now = datetime.now()

            if ordered_content_ids:
                order_lookup = {
                    str(content_id): index + 1 for index, content_id in enumerate(ordered_content_ids)
                }
                for content_id, order_value in order_lookup.items():
                    doc = document_map.get(content_id)
                    if not doc:
                        continue
                    operations.append(
                        UpdateOne(
                            {"_id": doc["_id"]},
                            {"$set": {"order": order_value, "updated_at": now}}
                        )
                    )
            else:
                order_lookup = {}

            applied = 0
            for selection in selections or []:
                parent_id = str(selection.get("parent_content_id") or "")
                variant_id = str(selection.get("variant_content_id") or "")
                if not parent_id or not variant_id:
                    continue

                base_doc = document_map.get(parent_id)
                variant_doc = document_map.get(variant_id)
                if not base_doc or not variant_doc:
                    continue

                applied += 1
                selection_payload = {
                    "variant_content_id": variant_id,
                    "variant_label": selection.get("variant_label"),
                    "selection_reason": selection.get("reason"),
                    "selection_confidence": selection.get("confidence"),
                    "matched_modalities": selection.get("matched_modalities"),
                    "source": selection.get("source"),
                    "prediction_id": selection.get("prediction_id"),
                    "rl_confidence": selection.get("rl_confidence"),
                    "rl_recommendation_type": selection.get("rl_recommendation_type"),
                    "rl_context_summary": selection.get("rl_context_summary"),
                    "rl_boost_details": selection.get("rl_boost_details"),
                    "vark_score": selection.get("vark_score"),
                    "updated_at": now,
                }

                operations.append(
                    UpdateOne(
                        {"_id": base_doc["_id"]},
                        {"$set": {"selected_dynamic_variant": selection_payload, "updated_at": now}}
                    )
                )

                operations.append(
                    UpdateOne(
                        {"_id": variant_doc["_id"]},
                        {"$set": {"dynamic_variant_state": "selected", "updated_at": now}}
                    )
                )

                siblings = variants_by_parent.get(parent_id, [])
                for sibling in siblings:
                    if str(sibling["_id"]) == variant_id:
                        continue
                    operations.append(
                        UpdateOne(
                            {"_id": sibling["_id"]},
                            {"$set": {"dynamic_variant_state": "omitted", "updated_at": now}}
                        )
                    )

            if not operations:
                return False, {"error": "No se aplicaron cambios"}

            self.db.virtual_topic_contents.bulk_write(operations)
            return True, {
                "applied_variants": applied,
                "reordered_contents": len(order_lookup),
            }
        except Exception as exc:
            logging.error(f"Error aplicando personalización del tema: {exc}")
            return False, {"error": str(exc)}


    def _generate_contents_traditional(self, virtual_topic_id: str, student_id: str, 
                                     selected_contents: List[Dict], cognitive_profile: Dict):
        """
        Genera contenidos usando el método tradicional.
        """
        parent_variant_counters: Dict[str, int] = defaultdict(int)
        parent_order_cache: Dict[str, Optional[float]] = {}
        base_order_state = {"next_order": 1}
        for content in selected_contents:
            self._create_traditional_virtual_content(
                virtual_topic_id,
                student_id,
                content,
                cognitive_profile,
                parent_variant_counters,
                parent_order_cache,
                base_order_state
            )

    def _create_traditional_virtual_content(self, virtual_topic_id: str, student_id: str, 
                                          content: Dict, cognitive_profile: Dict,
                                          parent_variant_counters: Dict[str, int],
                                          parent_order_cache: Dict[str, Optional[float]],
                                          base_order_state: Dict[str, float]):
        """
        Crea contenido virtual usando el método tradicional.
        """
        try:
            # Generar adaptaciones específicas para este contenido
            personalization_data = self._generate_content_personalization(content, cognitive_profile)

            # Obtener datos del estudiante para personalización de markers
            student = self.db.users.find_one({"_id": ObjectId(student_id)})
            
            # Nota: Personalización de markers deshabilitada temporalmente
            # El contenido se usa tal como está almacenado en la base de datos
            personalized_content = content.get("content", "")
            
            order_value = self._determine_virtual_order(
                content,
                parent_variant_counters,
                parent_order_cache,
                base_order_state
            )

            virtual_content_data = {
                "virtual_topic_id": ObjectId(virtual_topic_id),
                "content_id": content["_id"],
                "student_id": ObjectId(student_id),
                "content_type": content.get("content_type", "unknown"),
                "content": personalized_content,
                "personalization_data": personalization_data,
                "interaction_tracking": {
                    "access_count": 0,
                    "total_time_spent": 0,
                    "last_accessed": None,
                    "completion_status": "not_started",
                    "completion_percentage": 0.0,
                    "sessions": 0,
                    "best_score": None,
                    "avg_score": None,
                    "interactions": []
                },
                "status": "active",
                "order": order_value,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            # Propagar render_engine e instance_id si el contenido original es una plantilla HTML
            if content.get("render_engine") == "html_template":
                virtual_content_data["render_engine"] = "html_template"
                if content.get("instance_id"):
                    virtual_content_data["instance_id"] = content["instance_id"]
            
            # Insertar contenido virtual
            result = self.db.virtual_topic_contents.insert_one(virtual_content_data)
            logging.debug(f"Contenido virtual tradicional creado: {result.inserted_id} para tema {virtual_topic_id}")
            
        except Exception as e_content:
            logging.error(f"Error creando contenido virtual tradicional para {content.get('_id')}: {e_content}")
    
    def _determine_virtual_order(
        self,
        content: Dict,
        parent_variant_counters: Dict[str, int],
        parent_order_cache: Dict[str, Optional[float]],
        base_order_state: Dict[str, float],
    ) -> float:
        """
        Calcula el valor de orden para el contenido virtual, intercalando variantes inmediatamente
        después de su diapositiva padre usando incrementos decimales.
        """
        override_order = content.get("_virtual_normalized_order") or content.get("virtual_normalized_order")
        if isinstance(override_order, (int, float)):
            return float(override_order)

        order_value = content.get("order")
        numeric_order: Optional[float] = None
        if isinstance(order_value, (int, float)):
            numeric_order = float(order_value)
        else:
            try:
                numeric_order = float(order_value)
            except (TypeError, ValueError):
                numeric_order = None

        parent_id = content.get("parent_content_id")
        if parent_id:
            if isinstance(parent_id, ObjectId):
                parent_id_obj = parent_id
                parent_id_str = str(parent_id)
            else:
                parent_id_str = str(parent_id)
                try:
                    parent_id_obj = ObjectId(parent_id)
                except Exception:
                    parent_id_obj = None

            parent_order = parent_order_cache.get(parent_id_str)
            if parent_order is None:
                parent_doc = None
                if parent_id_obj:
                    parent_doc = self.db.topic_contents.find_one(
                        {"_id": parent_id_obj}, {"order": 1}
                    )
                parent_order = float(parent_doc.get("order")) if parent_doc and isinstance(parent_doc.get("order"), (int, float)) else None
                parent_order_cache[parent_id_str] = parent_order

            if parent_order is None:
                parent_order = numeric_order if numeric_order is not None else 0.0

            variant_meta = content.get("variant") or {}
            variant_index = variant_meta.get("variant_index")
            if isinstance(variant_index, (int, float)):
                variant_index_value = int(variant_index)
            else:
                parent_variant_counters[parent_id_str] += 1
                variant_index_value = parent_variant_counters[parent_id_str] - 1
            return round(float(parent_order) + (variant_index_value + 1) / 10.0, 4)

        if numeric_order is not None:
            return numeric_order

        next_order = float(base_order_state.get("next_order", 1))
        base_order_state["next_order"] = next_order + 1
        return next_order

    def _calculate_content_priority(self, content_type: str) -> int:
        """
        Calcula la prioridad de generación basada en el tipo de contenido.
        """
        priority_map = {
            "text": 1,           # Alta prioridad - contenido textual base
            "slide": 1,          # Alta prioridad - presentaciones
            "video": 2,          # Media-alta prioridad - contenido multimedia
            "quiz": 2,           # Media-alta prioridad - evaluaciones
            "exam": 2,           # Media-alta prioridad - exámenes
            "diagram": 3,        # Media prioridad - contenido visual
            "infographic": 3,    # Media prioridad - infografías
            "game": 4,           # Media-baja prioridad - juegos
            "simulation": 4,     # Media-baja prioridad - simulaciones
            "audio": 5,          # Baja prioridad - contenido auditivo
            "music": 5           # Baja prioridad - música
        }
        
        return priority_map.get(content_type, 5)


    def _select_personalized_contents(
        self,
        original_contents: List[Dict],
        cognitive_profile: Dict,
        preferences: Dict = None
    ) -> List[Dict]:
        """
        Selecciona los contenidos que conformarán el tema virtual respetando la relación
        teórica → interactiva → evaluaciones. Solo se escoge una plantilla interactiva
        por diapositiva y se normaliza el orden final.
        """
        try:
            if not original_contents:
                return []

            preferences = preferences or {}
            avoid_types = {str(t).lower() for t in preferences.get('avoid_types', [])}
            preferred_modes = {
                str(mode).lower() for mode in preferences.get('preferred_interaction_modes', [])
            }
            preferred_templates = {
                str(tid) for tid in preferences.get('preferred_template_ids', [])
            }

            valid_statuses = {
                'draft',
                'active',
                'approved',
                'published',
                'narrative_ready',
                'skeleton',
                'html_ready'
            }
            vak_dimensions = ["visual", "auditory", "reading_writing", "kinesthetic"]

            def normalize_type(value: Any) -> str:
                if isinstance(value, str):
                    return value.lower()
                if value is None:
                    return ""
                return str(value).lower()

            def normalize_id(value: Any) -> Optional[str]:
                if isinstance(value, ObjectId):
                    return str(value)
                if value is None:
                    return None
                return str(value)

            def sort_key(content: Dict) -> float:
                order_value = content.get('order')
                if isinstance(order_value, (int, float)):
                    return float(order_value)
                try:
                    return float(order_value)
                except (TypeError, ValueError):
                    return 9999.0

            def extract_vak_vector(source: Optional[Dict]) -> Dict[str, float]:
                vector = {dim: 0.0 for dim in vak_dimensions}
                if not isinstance(source, dict):
                    return vector

                candidates = []
                learning_style = source.get("learning_style")
                if isinstance(learning_style, dict):
                    candidates.append(learning_style)

                profile_data = source.get("profile")
                if isinstance(profile_data, dict):
                    vak_scores = profile_data.get("vak_scores")
                    if isinstance(vak_scores, dict):
                        candidates.append(vak_scores)
                    else:
                        candidates.append(profile_data)

                if not candidates:
                    candidates.append(source)

                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    for dim in vak_dimensions:
                        raw_value = candidate.get(dim)
                        if isinstance(raw_value, (int, float)):
                            vector[dim] = max(vector[dim], float(raw_value))

                total = sum(vector.values())
                if total > 0:
                    vector = {dim: value / total for dim, value in vector.items()}
                return vector

            def extract_vak_from_content(content: Dict) -> Dict[str, float]:
                vector = {dim: 0.0 for dim in vak_dimensions}
                candidates = []
                for key in ("baseline_mix", "learning_mix"):
                    mix = content.get(key)
                    if isinstance(mix, dict):
                        if isinstance(mix.get("vak"), dict):
                            candidates.append(mix["vak"])
                        elif isinstance(mix.get("vak_scores"), dict):
                            candidates.append(mix["vak_scores"])
                        else:
                            candidates.append(mix)

                personalization = content.get("personalization_data")
                if isinstance(personalization, dict):
                    vak_scores = personalization.get("vak_scores")
                    if isinstance(vak_scores, dict):
                        candidates.append(vak_scores)

                if not candidates:
                    candidates.append(content.get("vak_profile") or {})

                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    for dim in vak_dimensions:
                        raw_value = candidate.get(dim)
                        if isinstance(raw_value, dict):
                            raw_value = raw_value.get("value") or raw_value.get("score") or raw_value.get("weight")
                        if isinstance(raw_value, (int, float)):
                            vector[dim] = max(vector[dim], float(raw_value))

                total = sum(vector.values())
                if total > 0:
                    vector = {dim: value / total for dim, value in vector.items()}
                return vector

            def vak_alignment_score(student_vak: Dict[str, float], content_vak: Dict[str, float]) -> float:
                if not student_vak or not content_vak:
                    return 0.0
                return sum(student_vak.get(dim, 0.0) * content_vak.get(dim, 0.0) for dim in vak_dimensions)

            def is_interactive_candidate(content: Dict) -> bool:
                if content.get("render_engine") == "html_template":
                    return True
                if isinstance(content.get("interactive_data"), dict):
                    return True
                return normalize_type(content.get("content_type")) in self.INTERACTIVE_CONTENT_TYPES

            def compute_interactive_score(content: Dict) -> float:
                vak_vector = extract_vak_from_content(content)
                vak_score = vak_alignment_score(student_vak, vak_vector)

                personalization = content.get("personalization_data") or {}
                rl_score = personalization.get("rl_score") or personalization.get("rl_confidence") or 0.0
                final_score = (
                    personalization.get("final_score")
                    or personalization.get("match_score")
                    or content.get("final_score")
                    or content.get("rl_score")
                    or 0.0
                )

                interaction_mode = normalize_type(
                    (content.get("interactive_data") or {}).get("interaction_mode")
                    or personalization.get("interaction_mode")
                )
                interaction_bonus = 0.1 if interaction_mode and interaction_mode in preferred_modes else 0.0

                template_usage_id = str(
                    content.get("template_usage_id")
                    or (content.get("attachment") or {}).get("template_id")
                    or ""
                )
                template_bonus = 0.1 if template_usage_id and template_usage_id in preferred_templates else 0.0

                base_match = 0.0
                variant_meta = content.get("variant") or {}
                variant_match = variant_meta.get("match_score")
                if isinstance(variant_match, (int, float)):
                    base_match = float(variant_match)

                return (
                    vak_score * 0.45
                    + float(rl_score) * 0.25
                    + float(final_score) * 0.15
                    + interaction_bonus
                    + template_bonus
                    + base_match * 0.05
                )

            student_vak = extract_vak_vector(cognitive_profile or {})

            base_slides: List[Dict] = []
            evaluations: List[Dict] = []
            optional_resources: List[Dict] = []
            orphan_interactives: List[Dict] = []
            interactive_by_parent: Dict[str, List[Dict]] = defaultdict(list)

            for content in original_contents:
                ctype = normalize_type(content.get('content_type'))
                if not ctype or ctype in avoid_types or ctype in self.EXCLUDED_CONTENT_TYPES:
                    continue

                status = normalize_type(content.get('status'))
                if status and status not in valid_statuses:
                    continue

                if ctype == 'slide':
                    content_id = normalize_id(content.get('_id') or content.get('id'))
                    parent_id = normalize_id(content.get("parent_content_id"))
                    if parent_id and parent_id != content_id:
                        interactive_by_parent[parent_id].append(content)
                    else:
                        base_slides.append(content)
                    continue

                if ctype in self.EVALUATION_CONTENT_TYPES:
                    evaluations.append(content)
                    continue

                parent_id = normalize_id(content.get("parent_content_id"))
                if parent_id and is_interactive_candidate(content):
                    interactive_by_parent[parent_id].append(content)
                    continue

                if is_interactive_candidate(content):
                    orphan_interactives.append(content)
                    continue

                optional_resources.append(content)

            base_slides.sort(key=sort_key)
            evaluations.sort(key=sort_key)
            optional_resources.sort(key=sort_key)
            orphan_interactives.sort(key=sort_key)

            best_variants: Dict[str, Dict] = {}
            for slide in base_slides:
                slide_id = normalize_id(slide.get('_id') or slide.get('id'))
                if not slide_id:
                    continue
                candidates = interactive_by_parent.get(slide_id, [])
                if not candidates:
                    continue
                ranked = sorted(
                    candidates,
                    key=lambda item: compute_interactive_score(item),
                    reverse=True
                )
                best_variants[slide_id] = ranked[0]

            normalized_sequence: List[Dict] = []
            seen_ids = set()
            next_order = 1

            def push_content(content: Dict):
                nonlocal next_order
                content_id = normalize_id(content.get('_id') or content.get('id'))
                if content_id and content_id in seen_ids:
                    return
                if content_id:
                    seen_ids.add(content_id)
                content['_virtual_normalized_order'] = next_order
                content['order'] = next_order
                next_order += 1
                normalized_sequence.append(content)

            for slide in base_slides:
                slide_id = normalize_id(slide.get('_id') or slide.get('id'))
                push_content(slide)
                if slide_id and slide_id in best_variants:
                    selected_variant = best_variants[slide_id]
                    selected_variant['_selected_interactive_for'] = slide_id
                    push_content(selected_variant)

            for resource in optional_resources + orphan_interactives:
                push_content(resource)

            evaluations_sorted: List[Dict] = sorted(
                evaluations,
                key=lambda item: (
                    1 if normalize_type(item.get('content_type')) == 'quiz' else 0,
                    sort_key(item)
                )
            )
            for evaluation in evaluations_sorted:
                push_content(evaluation)

            if not normalized_sequence:
                logging.warning(
                    "No se encontraron contenidos válidos tras aplicar la nueva lógica. Se devuelve el arreglo original (%s elementos).",
                    len(original_contents)
                )
                return original_contents

            logging.info(
                "Selección final para topic: slides=%s, interactivos=%s, evaluaciones=%s, recursos=%s, total=%s",
                len(base_slides),
                len(best_variants),
                len(evaluations),
                len(optional_resources) + len(orphan_interactives),
                len(normalized_sequence)
            )
            return normalized_sequence
        except Exception as e:
            logging.error(f"Error en _select_personalized_contents (nueva lógica): {e}")
            return original_contents
    def _generate_content_personalization(self, content: Dict, cognitive_profile: Dict) -> Dict:
        """
        Genera datos de personalización específicos para un contenido.
        
        Args:
            content: Contenido original
            cognitive_profile: Perfil cognitivo del estudiante
            
        Returns:
            Diccionario con datos de personalización
        """
        try:
            learning_style = cognitive_profile.get("learning_style", {})
            profile_data = cognitive_profile.get("profile", {})
            
            if isinstance(profile_data, str):
                try:
                    import json
                    profile_data = json.loads(profile_data)
                except:
                    profile_data = {}
            
            vak_scores = learning_style or profile_data.get("vak_scores", {})
            learning_disabilities = profile_data.get("learning_disabilities", {})
            
            personalization = {
                "adapted_for_profile": True,
                "sync_generated": True,
                "sync_date": datetime.now(),
                "content_type": content.get("content_type", "unknown"),
                "vak_adaptation": {
                    "visual_emphasis": vak_scores.get("visual", 0) > 0.6,
                    "audio_support": vak_scores.get("auditory", 0) > 0.6,
                    "interactive_elements": vak_scores.get("kinesthetic", 0) > 0.6,
                    "text_optimization": vak_scores.get("reading_writing", 0) > 0.6
                },
                "accessibility_adaptations": {
                    "dyslexia_friendly": learning_disabilities.get("dyslexia", False),
                    "adhd_optimized": learning_disabilities.get("adhd", False),
                    "high_contrast": learning_disabilities.get("visual_impairment", False)
                },
                "difficulty_adjustment": self._calculate_difficulty_adjustment(cognitive_profile),
                "estimated_time": self._estimate_content_time(content, cognitive_profile)
            }
            
            return personalization
            
        except Exception as e:
            logging.error(f"Error generando personalización: {str(e)}")
            return {
                "adapted_for_profile": True,
                "sync_generated": True,
                "sync_date": datetime.now(),
                "content_type": content.get("content_type", "unknown"),
                "error": str(e)
            }
    
    def _calculate_difficulty_adjustment(self, cognitive_profile: Dict) -> float:
        """
        Calcula el ajuste de dificultad basado en el perfil cognitivo.
        
        Returns:
            Float entre -0.5 y 0.5 (negativo = más fácil, positivo = más difícil)
        """
        try:
            profile_data = cognitive_profile.get("profile", {})
            if isinstance(profile_data, str):
                try:
                    import json
                    profile_data = json.loads(profile_data)
                except:
                    profile_data = {}
            
            difficulties = cognitive_profile.get("cognitive_difficulties", [])
            strengths = cognitive_profile.get("cognitive_strengths", [])
            
            adjustment = 0.0
            
            # Ajustar por dificultades
            if "memoria" in difficulties or "atención" in difficulties:
                adjustment -= 0.2
            if "procesamiento" in difficulties:
                adjustment -= 0.3
            
            # Ajustar por fortalezas
            if "análisis" in strengths or "síntesis" in strengths:
                adjustment += 0.2
            if "memoria_visual" in strengths:
                adjustment += 0.1
            
            # Mantener en rango válido
            return max(-0.5, min(0.5, adjustment))
            
        except Exception as e:
            logging.error(f"Error calculando ajuste de dificultad: {str(e)}")
            return 0.0
    
    def _estimate_content_time(self, content: Dict, cognitive_profile: Dict) -> int:
        """
        Estima el tiempo necesario para completar el contenido según el perfil.
        
        Returns:
            Tiempo estimado en minutos
        """
        try:
            content_type = content.get("content_type", "")
            
            # Tiempos base por tipo de contenido (en minutos)
            base_times = {
                "text": 10, "feynman": 15, "slide": 12, "video": 8,
                "diagram": 5, "infographic": 7, "mindmap": 6,
                "game": 15, "simulation": 20, "quiz": 10,
                "audio": 8, "interactive_exercise": 12
            }
            
            base_time = base_times.get(content_type, 10)
            
            # Ajustar según dificultades cognitivas
            profile_data = cognitive_profile.get("profile", {})
            if isinstance(profile_data, str):
                try:
                    import json
                    profile_data = json.loads(profile_data)
                except:
                    profile_data = {}
            
            learning_disabilities = profile_data.get("learning_disabilities", {})
            
            # Aumentar tiempo si hay dificultades
            if learning_disabilities.get("dyslexia") and content_type in ["text", "slide"]:
                base_time *= 1.5
            if learning_disabilities.get("adhd") and content_type in ["text", "video"]:
                base_time *= 1.3
            
            return int(base_time)
            
        except Exception as e:
            logging.error(f"Error estimando tiempo de contenido: {str(e)}")
            return 10

    def _validate_content_balance(self, selected_contents: List[Dict], original_contents: List[Dict]) -> Dict:
        """
        Valida el balance de contenidos seleccionados y retorna métricas de calidad.
        
        Args:
            selected_contents: Contenidos seleccionados para el estudiante
            original_contents: Contenidos originales disponibles
            
        Returns:
            Dict con métricas de balance y recomendaciones
        """
        try:
            if not selected_contents:
                return {
                    "balance_score": 0.0,
                    "warnings": ["No hay contenidos seleccionados"],
                    "coverage": {"complete": 0, "specific": 0, "evaluative": 0},
                    "recommendations": ["Revisar algoritmo de selección"]
                }
            
            # Analizar tipos de contenidos seleccionados
            selected_types = [c.get('content_type', 'unknown') for c in selected_contents]
            
            # Categorizar contenidos
            complete_types = ["text", "slide", "video", "feynman", "story", "summary", "narrated_presentation"]
            evaluative_types = ["quiz", "exam", "formative_test", "project"]
            
            complete_count = sum(1 for t in selected_types if t in complete_types)
            evaluative_count = sum(1 for t in selected_types if t in evaluative_types)
            specific_count = len(selected_types) - complete_count - evaluative_count
            
            # Calcular score de balance (0.0 a 1.0)
            balance_score = 0.0
            warnings = []
            recommendations = []
            
            # Criterio 1: Debe haber al menos 1 contenido completo (40% del score)
            if complete_count >= 1:
                balance_score += 0.4
            else:
                warnings.append("Sin contenidos completos - cobertura del tema comprometida")
                recommendations.append("Asegurar al menos 1 contenido que cubra todo el tema")
            
            # Criterio 2: Variedad de tipos (30% del score)
            unique_types = len(set(selected_types))
            if unique_types >= 3:
                balance_score += 0.3
            elif unique_types >= 2:
                balance_score += 0.15
            else:
                warnings.append("Poca variedad de tipos de contenido")
                recommendations.append("Incluir más tipos diversos de contenido")
            
            # Criterio 3: Cantidad apropiada (20% del score)
            content_count = len(selected_contents)
            if 3 <= content_count <= 6:
                balance_score += 0.2
            elif content_count >= 2:
                balance_score += 0.1
            else:
                warnings.append(f"Cantidad de contenidos inadecuada: {content_count}")
                recommendations.append("Mantener entre 3-6 contenidos por tema")
            
            # Criterio 4: Contenido evaluativo presente (10% del score)
            if evaluative_count >= 1:
                balance_score += 0.1
            else:
                original_eval = sum(1 for c in original_contents 
                                  if c.get('content_type') in evaluative_types)
                if original_eval > 0:
                    warnings.append("Sin contenidos evaluativos a pesar de estar disponibles")
                    recommendations.append("Incluir al menos 1 contenido evaluativo")
            
            # Validaciones adicionales
            if content_count > 6:
                warnings.append("Demasiados contenidos seleccionados")
                recommendations.append("Limitar a máximo 6 contenidos")
            
            if complete_count > 2:
                warnings.append("Demasiados contenidos completos - puede ser redundante")
                recommendations.append("Balancear con más contenidos específicos")
            
            return {
                "balance_score": round(balance_score, 2),
                "warnings": warnings,
                "recommendations": recommendations,
                "coverage": {
                    "complete": complete_count,
                    "specific": specific_count,
                    "evaluative": evaluative_count,
                    "total": content_count
                },
                "variety": {
                    "unique_types": unique_types,
                    "types": selected_types
                },
                "quality_level": (
                    "Excelente" if balance_score >= 0.9 else
                    "Bueno" if balance_score >= 0.7 else
                    "Aceptable" if balance_score >= 0.5 else
                    "Necesita mejora"
                )
            }
            
        except Exception as e:
            logging.error(f"Error validando balance de contenidos: {str(e)}")
            return {
                "balance_score": 0.0,
                "warnings": [f"Error en validación: {str(e)}"],
                "coverage": {"complete": 0, "specific": 0, "evaluative": 0},
                "recommendations": ["Revisar función de validación"]
            }

class VirtualContentProgressService(VerificationBaseService):
    """
    Servicio para manejar automáticamente el progreso de contenidos virtuales,
    incluyendo la creación automática de ContentResults y actualización de progreso.
    """
    
    def __init__(self):
        super().__init__(collection_name="virtual_topic_contents")
    
    def complete_content_automatically(self, virtual_content_id: str, student_id: str, 
                                     completion_data: Dict = None) -> Tuple[bool, str]:
        """
        Marca un contenido como completado automáticamente y crea ContentResult.
        
        Args:
            virtual_content_id: ID del contenido virtual
            student_id: ID del estudiante
            completion_data: Datos adicionales de completación
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Obtener contenido virtual
            virtual_content = self.collection.find_one({"_id": ObjectId(virtual_content_id)})
            if not virtual_content:
                return False, "Contenido virtual no encontrado"
            
            # Verificar que el estudiante es el propietario
            if str(virtual_content.get("student_id")) != str(student_id):
                return False, "No tienes permiso para completar este contenido"
            
            # Verificar que no esté ya completado
            current_status = virtual_content.get("interaction_tracking", {}).get("completion_status")
            if current_status == "completed":
                return False, "Contenido ya completado"
            
            # Datos por defecto de completación
            completion_data = completion_data or {}
            score = completion_data.get("score", 1.0)  # Score por defecto para completación
            completion_percentage = completion_data.get("completion_percentage", 100)
            session_data = completion_data.get("session_data", {})
            content_type = virtual_content.get("content_type", "unknown")
            
            # Ajustar score según tipo de contenido
            score = self._calculate_auto_score(content_type, completion_data)
            
            # 1. Crear ContentResult automáticamente
            success, content_result_id = self._create_automatic_content_result(
                virtual_content, student_id, score, session_data
            )
            
            if not success:
                logging.warning(f"No se pudo crear ContentResult: {content_result_id}")
            
            # 2. Actualizar tracking del contenido virtual
            self._update_content_tracking(virtual_content_id, completion_percentage, session_data)
            
            # 3. Verificar y actualizar progreso del tema virtual
            topic_updated = self._check_and_update_topic_progress(virtual_content)
            
            # 4. Verificar trigger para siguiente tema (80% progreso)
            if topic_updated:
                self._trigger_next_topic_generation(virtual_content)
            
            return True, content_result_id or "Contenido completado exitosamente"
            
        except Exception as e:
            logging.error(f"Error completando contenido automáticamente: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def _calculate_auto_score(self, content_type: str, completion_data: Dict) -> float:
        """
        Calcula el score automático según el tipo de contenido.
        
        Args:
            content_type: Tipo de contenido
            completion_data: Datos de completación
            
        Returns:
            Score entre 0.0 y 1.0
        """
        # Si ya se proporciona un score, usarlo
        if "score" in completion_data:
            return min(max(completion_data["score"], 0.0), 1.0)
        
        # Scores automáticos por tipo de contenido
        auto_scores = {
            # Contenidos de solo visualización/lectura
            "text": 1.0,
            "slide": 1.0, 
            "video": 1.0,
            "audio": 1.0,
            "document": 1.0,
            "image": 1.0,
            "diagram": 1.0,
            "infographic": 1.0,
            "mindmap": 1.0,
            
            # Contenidos interactivos (requieren participación)
            "game": 0.8,  # Puntuación base alta por participación
            "simulation": 0.8,
            "interactive_exercise": 0.8,
            "virtual_lab": 0.8,
            
            # Contenidos evaluativos (no deberían auto-completarse)
            "quiz": 0.0,  # Los quizzes requieren respuestas correctas
            "exam": 0.0,
            "project": 0.0,
            
            # Contenidos especiales
            "flashcards": 0.9,
            "glossary": 1.0,
            "examples": 1.0
        }
        
        return auto_scores.get(content_type, 0.8)  # Score por defecto
    
    def _create_automatic_content_result(self, virtual_content: Dict, student_id: str, 
                                       score: float, session_data: Dict) -> Tuple[bool, str]:
        """
        Crea un ContentResult automáticamente.
        """
        try:
            from src.content.services import ContentResultService
            
            # Preparar datos para ContentResult
            original_content_ref = (
                virtual_content.get("content_id")
                or virtual_content.get("original_content_id")
            )
            content_result_data = {
                "virtual_content_id": str(virtual_content["_id"]),
                "content_id": str(original_content_ref) if original_content_ref else None,
                "student_id": student_id,
                "score": score,
                "feedback": "Contenido completado automáticamente",
                "metrics": {
                    "content_type": virtual_content.get("content_type", "unknown"),
                    "auto_completed": True,
                    "completion_time": session_data.get("time_spent", 0),
                    "interaction_count": session_data.get("interactions", 1),
                    "personalization_applied": bool(virtual_content.get("personalization_data"))
                },
                "session_type": "auto_completion",
            }
            
            # Crear ContentResult
            content_result_service = ContentResultService()
            success, result_id = content_result_service.record_result(content_result_data)
            
            if success:
                logging.info(f"ContentResult automático creado: {result_id} para contenido {virtual_content['_id']}")
                return True, result_id
            else:
                logging.error(f"Error creando ContentResult automático: {result_id}")
                return False, result_id
                
        except Exception as e:
            logging.error(f"Error en _create_automatic_content_result: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def _update_content_tracking(self, virtual_content_id: str, completion_percentage: float, 
                               session_data: Dict):
        """
        Actualiza el tracking del contenido virtual.
        """
        try:
            set_operations = {
                "interaction_tracking.last_accessed": datetime.now(),
                "interaction_tracking.completion_percentage": completion_percentage,
                "interaction_tracking.completion_status": "completed" if completion_percentage >= 100 else "in_progress",
                "updated_at": datetime.now()
            }
            
            inc_operations = {
                "interaction_tracking.access_count": 1
            }
            
            if completion_percentage >= 100:
                inc_operations["interaction_tracking.sessions"] = 1
            
            time_spent = session_data.get("time_spent")
            if isinstance(time_spent, (int, float)) and time_spent > 0:
                inc_operations["interaction_tracking.total_time_spent"] = time_spent
            
            operations: Dict[str, Dict] = {"$set": set_operations, "$inc": inc_operations}
            
            self.collection.update_one(
                {"_id": ObjectId(virtual_content_id)},
                operations
            )
            
            logging.debug(f"Tracking actualizado para contenido {virtual_content_id}")
            
        except Exception as e:
            logging.error(f"Error actualizando tracking: {str(e)}")
    
    def _check_and_update_topic_progress(self, virtual_content: Dict) -> bool:
        """
        Verifica y actualiza el progreso del tema virtual basado en contenidos completados.
        
        Returns:
            bool: True si el tema fue actualizado
        """
        try:
            virtual_topic_id = virtual_content["virtual_topic_id"]
            
            # Obtener todos los contenidos del tema virtual
            all_contents = list(self.collection.find({
                "virtual_topic_id": virtual_topic_id,
                "status": "active"
            }))
            
            if not all_contents:
                return False
            
            # Calcular progreso total
            total_contents = len(all_contents)
            completed_contents = len([
                c for c in all_contents 
                if c.get("interaction_tracking", {}).get("completion_status") == "completed"
            ])
            
            progress_percentage = (completed_contents / total_contents) * 100
            
            # Determinar estado
            if progress_percentage >= 100:
                status = "completed"
            elif progress_percentage > 0:
                status = "in_progress"
            else:
                status = "not_started"
            
            # Actualizar tema virtual
            self.db.virtual_topics.update_one(
                {"_id": virtual_topic_id},
                {"$set": {
                    "progress": progress_percentage,
                    "completion_status": status,
                    "updated_at": datetime.now()
                }}
            )
            
            logging.info(f"Progreso del tema virtual {virtual_topic_id} actualizado: {progress_percentage}%")
            return True
            
        except Exception as e:
            logging.error(f"Error actualizando progreso del tema: {str(e)}")
            return False
    
    def _trigger_next_topic_generation(self, virtual_content: Dict):
        """
        Verifica si debe generar el siguiente tema (trigger al 80% de progreso).
        Usa el OptimizedQueueService para mantener la cola automáticamente.
        """
        try:
            virtual_topic_id = virtual_content["virtual_topic_id"]
            
            # Obtener el tema virtual
            virtual_topic = self.db.virtual_topics.find_one({"_id": virtual_topic_id})
            if not virtual_topic:
                return
            
            # Verificar progreso
            progress = virtual_topic.get("progress", 0)
            if progress >= 80:
                # Usar el sistema optimizado de cola
                try:
                    from src.virtual.services import OptimizedQueueService
                    queue_service = OptimizedQueueService()
                    
                    # Triggear el sistema optimizado
                    result = queue_service.trigger_on_progress(str(virtual_topic_id), progress)
                    
                    if result.get("triggered"):
                        logging.info(f"Trigger exitoso para tema {virtual_topic_id}: {result}")
                        
                        # Si se completó, también actualizar módulo
                        if result.get("topic_completed"):
                            self._update_module_progress_from_topic(virtual_topic)
                    else:
                        logging.debug(f"Trigger no ejecutado: {result.get('reason', 'Unknown')}")
                        
                except Exception as queue_error:
                    logging.warning(f"Error en trigger optimizado: {str(queue_error)}")
                    # Fallback al sistema anterior
                    self._trigger_legacy_generation(virtual_topic)
            
        except Exception as e:
            logging.error(f"Error en trigger de siguiente tema: {str(e)}")
    
    def _trigger_legacy_generation(self, virtual_topic: Dict):
        """
        Sistema de fallback para generación de temas.
        """
        try:
            virtual_module_id = virtual_topic["virtual_module_id"]
            virtual_module = self.db.virtual_modules.find_one({"_id": virtual_module_id})
            
            if virtual_module:
                student_id = virtual_module["student_id"]
                
                # Intentar con el FastVirtualModuleGenerator original
                try:
                    fast_generator = FastVirtualModuleGenerator()
                    success, result = fast_generator.trigger_next_topic_generation(
                        str(student_id), str(virtual_topic["_id"]), virtual_topic.get("progress", 0)
                    )
                    
                    if success:
                        logging.info(f"Fallback generation successful: {result}")
                    else:
                        logging.warning(f"Fallback generation failed: {result}")
                        
                except Exception as gen_error:
                    logging.error(f"Error en generación de fallback: {str(gen_error)}")
                    
        except Exception as e:
            logging.error(f"Error en trigger legacy: {str(e)}")
    
    def _update_module_progress_from_topic(self, virtual_topic: Dict):
        """
        Actualiza el progreso del módulo virtual cuando se completa un tema.
        """
        try:
            virtual_module_id = virtual_topic["virtual_module_id"]
            
            # Obtener todos los temas del módulo
            all_topics = list(self.db.virtual_topics.find({
                "virtual_module_id": virtual_module_id
            }))
            
            if not all_topics:
                return
            
            # Calcular progreso total del módulo
            total_progress = sum(topic.get("progress", 0) for topic in all_topics)
            average_progress = total_progress / len(all_topics)
            
            # Determinar estado del módulo
            completed_topics = len([t for t in all_topics if t.get("completion_status") == "completed"])
            
            if completed_topics == len(all_topics):
                module_status = "completed"
            elif completed_topics > 0:
                module_status = "in_progress"
            else:
                module_status = "not_started"
            
            # Actualizar módulo virtual
            self.db.virtual_modules.update_one(
                {"_id": virtual_module_id},
                {"$set": {
                    "progress": round(average_progress, 2),
                    "completion_status": module_status,
                    "updated_at": datetime.now()
                }}
            )
            
            logging.info(f"Progreso del módulo {virtual_module_id} actualizado: {average_progress}%")
            
        except Exception as e:
            logging.error(f"Error actualizando progreso del módulo: {str(e)}")
    
    def auto_complete_reading_content(self, virtual_content_id: str, student_id: str, 
                                    reading_data: Dict = None) -> Tuple[bool, str]:
        """
        Auto-completa contenidos de lectura (texto, slides, videos) cuando se visualizan completamente.
        
        Args:
            virtual_content_id: ID del contenido virtual
            student_id: ID del estudiante  
            reading_data: Datos de lectura (tiempo, progreso de scroll, etc.)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        reading_data = reading_data or {}
        
        # Para contenidos de lectura, score siempre es 100% si se visualizó completamente
        completion_data = {
            "score": 1.0,
            "completion_percentage": 100,
            "session_data": {
                "time_spent": reading_data.get("time_spent", 0),
                "scroll_percentage": reading_data.get("scroll_percentage", 100),
                "interactions": reading_data.get("interactions", 1),
                "completion_method": "reading"
            }
        }
        
        return self.complete_content_automatically(virtual_content_id, student_id, completion_data)
    
    def get_student_progress_summary(self, student_id: str, virtual_module_id: str = None, workspace_info: Dict = None) -> Dict:
        """
        Obtiene un resumen completo del progreso del estudiante.
        
        Args:
            student_id: ID del estudiante
            virtual_module_id: ID del módulo virtual (opcional)
            workspace_info: Información del workspace para filtrado (opcional)
            
        Returns:
            Dict con estadísticas de progreso
        """
        try:
            # Filtro base
            base_filter = {"student_id": ObjectId(student_id)}
            
            # Aplicar filtro de workspace si está disponible
            if workspace_info:
                workspace_type = workspace_info.get('workspace_type')
                workspace_id = workspace_info.get('workspace_id')
                
                if workspace_type and workspace_id:
                    # Obtener módulos virtuales del workspace
                    module_filter = {"student_id": ObjectId(student_id)}
                    if workspace_type == 'INDIVIDUAL_STUDENT':
                        module_filter["workspace_id"] = ObjectId(workspace_id)
                    elif workspace_type == 'INSTITUTE':
                        module_filter["institute_id"] = ObjectId(workspace_id)
                    
                    workspace_modules = list(self.db.virtual_modules.find(module_filter))
                    workspace_module_ids = [vm["_id"] for vm in workspace_modules]
                    
                    if workspace_module_ids:
                        # Obtener temas de estos módulos
                        workspace_topics = list(self.db.virtual_topics.find({
                            "virtual_module_id": {"$in": workspace_module_ids}
                        }))
                        workspace_topic_ids = [vt["_id"] for vt in workspace_topics]
                        
                        if workspace_topic_ids:
                            base_filter["virtual_topic_id"] = {"$in": workspace_topic_ids}
                        else:
                            # No hay temas en el workspace, retornar vacío
                            base_filter["virtual_topic_id"] = {"$in": []}
                    else:
                        # No hay módulos en el workspace, retornar vacío
                        base_filter["virtual_topic_id"] = {"$in": []}
            
            if virtual_module_id:
                # Obtener temas del módulo específico
                module_filter = {"virtual_module_id": ObjectId(virtual_module_id)}
                
                # Si hay workspace_info, verificar que el módulo pertenezca al workspace
                if workspace_info:
                    workspace_type = workspace_info.get('workspace_type')
                    workspace_id = workspace_info.get('workspace_id')
                    
                    if workspace_type and workspace_id:
                        vm_filter = {"_id": ObjectId(virtual_module_id)}
                        if workspace_type == 'INDIVIDUAL_STUDENT':
                            vm_filter["workspace_id"] = ObjectId(workspace_id)
                        elif workspace_type == 'INSTITUTE':
                            vm_filter["institute_id"] = ObjectId(workspace_id)
                        
                        # Verificar que el módulo existe en el workspace
                        if not self.db.virtual_modules.find_one(vm_filter):
                            # Módulo no pertenece al workspace, retornar vacío
                            return {
                                "total_contents": 0,
                                "completed_contents": 0,
                                "completion_rate": 0,
                                "total_time_spent": 0,
                                "average_score": 0,
                                "content_types_progress": {},
                                "workspace_filtered": True
                            }
                
                virtual_topics = list(self.db.virtual_topics.find(module_filter))
                topic_ids = [vt["_id"] for vt in virtual_topics]
                base_filter["virtual_topic_id"] = {"$in": topic_ids}
            
            # Obtener todos los contenidos del estudiante
            contents = list(self.collection.find(base_filter))
            
            if not contents:
                return {
                    "total_contents": 0,
                    "completed_contents": 0,
                    "completion_rate": 0,
                    "total_time_spent": 0,
                    "average_score": 0,
                    "content_types_progress": {}
                }
            
            # Calcular estadísticas
            total_contents = len(contents)
            completed_contents = len([
                c for c in contents 
                if c.get("interaction_tracking", {}).get("completion_status") == "completed"
            ])
            
            total_time = sum([
                c.get("interaction_tracking", {}).get("total_time_spent", 0) 
                for c in contents
            ])
            
            # Obtener ContentResults para calcular promedio de scores
            from src.content.services import ContentResultService
            content_result_service = ContentResultService()
            
            # Esto es una simplificación - idealmente buscaríamos por virtual_content_id
            all_results = self.db.content_results.find({"student_id": ObjectId(student_id)})
            scores = [r.get("score", 0) for r in all_results if r.get("score") is not None]
            average_score = sum(scores) / len(scores) if scores else 0
            
            # Progreso por tipo de contenido
            content_types_progress = {}
            for content in contents:
                content_type = content.get("content_type", "unknown")
                if content_type not in content_types_progress:
                    content_types_progress[content_type] = {"total": 0, "completed": 0}
                
                content_types_progress[content_type]["total"] += 1
                if content.get("interaction_tracking", {}).get("completion_status") == "completed":
                    content_types_progress[content_type]["completed"] += 1
            
            # Calcular porcentajes
            for content_type in content_types_progress:
                total = content_types_progress[content_type]["total"]
                completed = content_types_progress[content_type]["completed"]
                content_types_progress[content_type]["percentage"] = (completed / total) * 100 if total > 0 else 0
            
            return {
                "total_contents": total_contents,
                "completed_contents": completed_contents,
                "completion_rate": round((completed_contents / total_contents) * 100, 2),
                "total_time_spent": total_time,
                "average_score": round(average_score * 100, 2),  # Convertir a porcentaje
                "content_types_progress": content_types_progress
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo resumen de progreso: {str(e)}")
            return {}

class AutoSyncService(VerificationBaseService):
    """
    Servicio avanzado para sincronización automática e inteligente de módulos virtuales.
    Detecta cambios y sincroniza en momentos apropiados.
    """
    
    def __init__(self):
        super().__init__(collection_name="virtual_modules")
        self.change_detector = ContentChangeDetector()
        self.fast_generator = FastVirtualModuleGenerator()
    
    def check_and_sync_if_needed(self, virtual_module_id: str, force: bool = False) -> Tuple[bool, Dict]:
        """
        Verifica si un módulo virtual necesita sincronización y la ejecuta si es necesario.
        
        Args:
            virtual_module_id: ID del módulo virtual
            force: Forzar sincronización aunque no haya cambios
            
        Returns:
            Tuple[bool, Dict]: (sincronizado, reporte)
        """
        try:
            # Obtener módulo virtual
            virtual_module = self.collection.find_one({"_id": ObjectId(virtual_module_id)})
            if not virtual_module:
                return False, {"error": "Módulo virtual no encontrado"}
            
            module_id = str(virtual_module["module_id"])
            student_id = str(virtual_module["student_id"])
            
            # Verificar si el estudiante está activo en el módulo
            is_appropriate_time = self._is_appropriate_sync_time(virtual_module)
            
            if not force and not is_appropriate_time:
                return False, {
                    "skipped": True,
                    "reason": "No es momento apropiado para sincronizar",
                    "student_active": False
                }
            
            # Detectar cambios en el módulo original
            change_report = self.change_detector.detect_changes(module_id)
            
            # Determinar si necesita sincronización
            needs_sync = force or self._needs_synchronization(virtual_module, change_report)
            
            if not needs_sync:
                return False, {
                    "skipped": True,
                    "reason": "Sin cambios significativos detectados",
                    "last_sync": virtual_module.get("last_sync_date"),
                    "change_report": change_report
                }
            
            # Ejecutar sincronización
            success, sync_report = self.fast_generator.synchronize_module_content(virtual_module_id)
            
            if success:
                # Actualizar información de sincronización
                self._update_sync_metadata(virtual_module_id, sync_report, change_report)
                
                # Notificar al estudiante si es necesario
                self._notify_student_if_needed(student_id, sync_report)
                
                return True, {
                    "synchronized": True,
                    "change_report": change_report,
                    "sync_report": sync_report,
                    "timestamp": datetime.now()
                }
            else:
                return False, {
                    "error": "Fallo en sincronización",
                    "details": sync_report
                }
                
        except Exception as e:
            logging.error(f"Error en check_and_sync_if_needed: {str(e)}")
            return False, {"error": f"Error interno: {str(e)}"}
    
    def _is_appropriate_sync_time(self, virtual_module: Dict) -> bool:
        """
        Determina si es un momento apropiado para sincronizar basado en la actividad del estudiante.
        
        Args:
            virtual_module: Documento del módulo virtual
            
        Returns:
            bool: True si es apropiado sincronizar
        """
        try:
            student_id = virtual_module["student_id"]
            
            # Verificar actividad reciente del estudiante
            last_activity = self._get_student_last_activity(student_id)
            if not last_activity:
                return True  # Si no hay actividad registrada, es seguro sincronizar
            
            # No sincronizar si el estudiante estuvo activo en los últimos 30 minutos
            thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
            if last_activity > thirty_minutes_ago:
                return False
            
            # Verificar progreso del módulo
            module_progress = virtual_module.get("progress", 0)
            completion_status = virtual_module.get("completion_status", "not_started")
            
            # No sincronizar módulos completados al 100%
            if completion_status == "completed" and module_progress >= 100:
                return False
            
            # Es apropiado sincronizar
            return True
            
        except Exception as e:
            logging.error(f"Error determinando momento apropiado: {str(e)}")
            return True  # En caso de error, permitir sincronización
    
    def _get_student_last_activity(self, student_id: ObjectId) -> Optional[datetime]:
        """
        Obtiene la última actividad del estudiante en contenidos virtuales.
        """
        try:
            # Buscar la última interacción en contenidos virtuales
            last_content_access = self.db.virtual_topic_contents.find_one(
                {"student_id": student_id},
                sort=[("interaction_tracking.last_accessed", -1)]
            )
            
            if last_content_access:
                return last_content_access.get("interaction_tracking", {}).get("last_accessed")
            
            # Buscar en ContentResults como alternativa
            last_result = self.db.content_results.find_one(
                {"student_id": student_id},
                sort=[("recorded_at", -1)]
            )
            
            if last_result:
                return last_result.get("recorded_at")
            
            return None
            
        except Exception as e:
            logging.error(f"Error obteniendo última actividad: {str(e)}")
            return None
    
    def _needs_synchronization(self, virtual_module: Dict, change_report: Dict) -> bool:
        """
        Determina si el módulo virtual necesita sincronización.
        
        Args:
            virtual_module: Documento del módulo virtual
            change_report: Reporte de cambios del ContentChangeDetector
            
        Returns:
            bool: True si necesita sincronización
        """
        try:
            # Si hay cambios detectados, sincronizar
            if change_report.get("has_changes", False):
                return True
            
            # Verificar si nunca se ha sincronizado
            last_sync = virtual_module.get("last_sync_date")
            if not last_sync:
                return True
            
            # Verificar si la sincronización es muy antigua (más de 7 días)
            week_ago = datetime.now() - timedelta(days=7)
            if last_sync < week_ago:
                return True
            
            # Verificar si hay temas bloqueados que podrían desbloquearse
            blocked_topics = self.db.virtual_topics.count_documents({
                "virtual_module_id": virtual_module["_id"],
                "locked": True,
                "status": {"$ne": "archived"}
            })
            
            if blocked_topics > 0:
                # Verificar si hay temas originales publicados que podrían desbloquear
                module_id = virtual_module["module_id"]
                published_topics = self.db.topics.count_documents({
                    "module_id": module_id,
                    "published": True
                })
                
                virtual_topics_count = self.db.virtual_topics.count_documents({
                    "virtual_module_id": virtual_module["_id"],
                    "status": {"$ne": "archived"}
                })
                
                # Si hay más temas publicados que virtualizados, sincronizar
                if published_topics > virtual_topics_count:
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error determinando necesidad de sincronización: {str(e)}")
            return False
    
    def _update_sync_metadata(self, virtual_module_id: str, sync_report: Dict, change_report: Dict):
        """
        Actualiza metadatos de sincronización del módulo virtual.
        """
        try:
            sync_metadata = {
                "last_sync_date": datetime.now(),
                "last_sync_report": {
                    "changes_detected": change_report.get("has_changes", False),
                    "items_added": len(sync_report.get("added", [])),
                    "items_updated": len(sync_report.get("updated", [])),
                    "items_removed": len(sync_report.get("removed", [])),
                    "errors": len(sync_report.get("errors", [])),
                    "sync_hash": change_report.get("current_hash", "")
                },
                "sync_count": {"$inc": 1}  # Incrementar contador
            }
            
            self.collection.update_one(
                {"_id": ObjectId(virtual_module_id)},
                {
                    "$set": {k: v for k, v in sync_metadata.items() if not isinstance(v, dict)},
                    "$inc": {"sync_count": 1}
                }
            )
            
            logging.info(f"Metadatos de sincronización actualizados para módulo {virtual_module_id}")
            
        except Exception as e:
            logging.error(f"Error actualizando metadatos de sincronización: {str(e)}")
    
    def _notify_student_if_needed(self, student_id: str, sync_report: Dict):
        """
        Notifica al estudiante si hay cambios significativos.
        """
        try:
            # Solo notificar si hay contenido añadido
            added_items = sync_report.get("added", [])
            if not added_items:
                return
            
            # Crear notificación simple (esto se podría extender con un sistema de notificaciones)
            notification_data = {
                "student_id": ObjectId(student_id),
                "type": "content_update",
                "title": "Nuevo contenido disponible",
                "message": f"Se han añadido {len(added_items)} nuevos elementos a tu módulo de estudio",
                "data": {
                    "added_count": len(added_items),
                    "sync_timestamp": datetime.now()
                },
                "read": False,
                "created_at": datetime.now()
            }
            
            # Insertar en colección de notificaciones (si existe)
            try:
                self.db.notifications.insert_one(notification_data)
                logging.info(f"Notificación creada para estudiante {student_id}")
            except Exception:
                logging.debug("No se pudo crear notificación - colección no existe")
                
        except Exception as e:
            logging.error(f"Error creando notificación: {str(e)}")
    
    def bulk_check_and_sync(self, student_id: str = None, module_id: str = None, 
                           max_modules: int = 50) -> Dict:
        """
        Verifica y sincroniza múltiples módulos virtuales en lote.
        
        Args:
            student_id: ID del estudiante (opcional)
            module_id: ID del módulo original (opcional)
            max_modules: Máximo número de módulos a procesar
            
        Returns:
            Dict con estadísticas del proceso
        """
        try:
            # Construir filtro
            filter_query = {}
            if student_id:
                filter_query["student_id"] = ObjectId(student_id)
            if module_id:
                filter_query["module_id"] = ObjectId(module_id)
            
            # Obtener módulos virtuales a verificar
            virtual_modules = list(self.collection.find(filter_query).limit(max_modules))
            
            if not virtual_modules:
                return {
                    "processed": 0,
                    "synchronized": 0,
                    "skipped": 0,
                    "errors": 0,
                    "details": []
                }
            
            # Procesar cada módulo
            stats = {
                "processed": 0,
                "synchronized": 0,
                "skipped": 0,
                "errors": 0,
                "details": []
            }
            
            for vm in virtual_modules:
                try:
                    vm_id = str(vm["_id"])
                    synced, report = self.check_and_sync_if_needed(vm_id)
                    
                    stats["processed"] += 1
                    
                    if synced:
                        stats["synchronized"] += 1
                        stats["details"].append({
                            "module_id": vm_id,
                            "status": "synchronized",
                            "items_changed": len(report.get("sync_report", {}).get("added", [])) + 
                                           len(report.get("sync_report", {}).get("updated", []))
                        })
                    elif report.get("skipped"):
                        stats["skipped"] += 1
                        stats["details"].append({
                            "module_id": vm_id,
                            "status": "skipped",
                            "reason": report.get("reason", "Unknown")
                        })
                    else:
                        stats["errors"] += 1
                        stats["details"].append({
                            "module_id": vm_id,
                            "status": "error",
                            "error": report.get("error", "Unknown error")
                        })
                        
                except Exception as vm_error:
                    stats["errors"] += 1
                    stats["details"].append({
                        "module_id": str(vm.get("_id", "unknown")),
                        "status": "error",
                        "error": str(vm_error)
                    })
            
            logging.info(f"Bulk sync completado: {stats}")
            return stats
            
        except Exception as e:
            logging.error(f"Error en bulk_check_and_sync: {str(e)}")
            return {
                "processed": 0,
                "synchronized": 0,
                "skipped": 0,
                "errors": 1,
                "error": str(e)
            }
    
    def schedule_auto_sync(self, interval_hours: int = 6) -> Dict:
        """
        Programa sincronización automática periódica.
        
        Args:
            interval_hours: Intervalo en horas entre sincronizaciones
            
        Returns:
            Dict con información del proceso programado
        """
        try:
            # Obtener módulos que necesitan verificación
            cutoff_time = datetime.now() - timedelta(hours=interval_hours)
            
            modules_to_check = list(self.collection.find({
                "$or": [
                    {"last_sync_date": {"$lt": cutoff_time}},
                    {"last_sync_date": {"$exists": False}}
                ],
                "completion_status": {"$ne": "completed"}  # No sincronizar módulos completados
            }))
            
            if not modules_to_check:
                return {
                    "scheduled": False,
                    "reason": "No hay módulos que requieran sincronización",
                    "next_check": datetime.now() + timedelta(hours=interval_hours)
                }
            
            # Ejecutar sincronización en lote
            sync_stats = self.bulk_check_and_sync(max_modules=100)
            
            return {
                "scheduled": True,
                "modules_checked": len(modules_to_check),
                "sync_stats": sync_stats,
                "next_check": datetime.now() + timedelta(hours=interval_hours)
            }
            
        except Exception as e:
            logging.error(f"Error en schedule_auto_sync: {str(e)}")
            return {
                "scheduled": False,
                "error": str(e)
            }

class OptimizedQueueService(VerificationBaseService):
    """
    Servicio optimizado para gestión de cola de generación de temas virtuales.
    Mantiene consistentemente 2 temas en cola y maneja triggers inteligentemente.
    """
    
    def __init__(self):
        super().__init__(collection_name="virtual_generation_tasks")
        self.fast_generator = FastVirtualModuleGenerator()
    
    def maintain_topic_queue(self, virtual_module_id: str, current_progress: float = 0) -> Dict:
        """
        Mantiene la cola de temas virtuales optimizada asegurando que siempre haya exactamente 2 temas por delante.
        
        Args:
            virtual_module_id: ID del módulo virtual
            current_progress: Progreso actual del módulo (0-100)
            
        Returns:
            Dict con información sobre los temas en cola
        """
        try:
            # Obtener módulo virtual
            virtual_module = self.db.virtual_modules.find_one({"_id": ObjectId(virtual_module_id)})
            if not virtual_module:
                return {"error": "Módulo virtual no encontrado"}
            
            student_id = str(virtual_module["student_id"])
            original_module_id = virtual_module["module_id"]
            
            # Obtener perfil cognitivo del estudiante
            student = self.db.users.find_one({"_id": ObjectId(student_id)})
            cognitive_profile = student.get("cognitive_profile", {}) if student else {}
            
            # Obtener temas virtuales existentes ordenados por orden de creación
            existing_virtual_topics = list(self.db.virtual_topics.find({
                "virtual_module_id": ObjectId(virtual_module_id)
            }).sort("order", 1))
            
            # Obtener temas originales publicados ordenados
            original_topics = list(self.db.topics.find({
                "module_id": original_module_id,
                "published": True
            }).sort("created_at", 1))
            
            if not original_topics:
                return {"error": "No hay temas publicados en el módulo original"}
            
            # Analizar estado actual de la cola
            generated_topic_ids = {str(vt["topic_id"]) for vt in existing_virtual_topics}
            available_topics = [t for t in original_topics if str(t["_id"]) not in generated_topic_ids]
            
            # Contar temas por estado
            active_topics = [vt for vt in existing_virtual_topics if vt.get("status") == "active"]
            locked_topics = [vt for vt in existing_virtual_topics if vt.get("status") == "locked"]
            completed_topics = [vt for vt in existing_virtual_topics if vt.get("completion_status") == "completed"]
            
            # Lógica optimizada: mantener exactamente 2 temas por delante
            total_topics = len(original_topics)
            current_active = len(active_topics)
            current_locked = len(locked_topics)
            
            # Calcular cuántos temas necesitamos generar
            # Regla: 1 activo + 2 bloqueados (por delante) = 3 temas disponibles máximo
            target_ahead = 2  # Siempre 2 temas por delante
            target_total = min(current_active + target_ahead, total_topics)
            
            # Si no hay temas activos, generar el primero como activo
            if current_active == 0 and len(existing_virtual_topics) == 0:
                target_total = min(3, total_topics)  # Inicial: 1 activo + 2 bloqueados
            
            topics_needed = max(0, target_total - len(existing_virtual_topics))
            
            # Verificar si ya tenemos suficientes temas en cola
            if topics_needed == 0 and current_locked >= target_ahead:
                return {
                    "status": "queue_optimal",
                    "message": f"Cola optimizada: {current_active} activo(s), {current_locked} en cola",
                    "active_topics": current_active,
                    "locked_ahead": current_locked,
                    "completed_topics": len(completed_topics),
                    "total_generated": len(existing_virtual_topics),
                    "remaining_original": len(available_topics)
                }
            
            # Generar temas faltantes si hay disponibles
            if not available_topics and topics_needed > 0:
                return {
                    "status": "queue_complete",
                    "message": "Todos los temas originales ya fueron generados",
                    "total_generated": len(existing_virtual_topics),
                    "active_topics": current_active,
                    "locked_ahead": current_locked
                }
            
            # Generar temas necesarios
            topics_to_generate = available_topics[:topics_needed]
            generated_topics = []
            
            for i, topic in enumerate(topics_to_generate):
                # Determinar si debe estar bloqueado (todos excepto el primero si no hay activos)
                should_lock = not (current_active == 0 and i == 0 and len(existing_virtual_topics) == 0)
                
                success, virtual_topic_id, topic_order = self._generate_single_virtual_topic(
                    topic, virtual_module_id, student_id, cognitive_profile, 
                    preferences=None, force_lock=should_lock
                )
                
                if success:
                    generated_topics.append({
                        "original_topic_id": str(topic["_id"]),
                        "virtual_topic_id": virtual_topic_id,
                        "name": topic.get("name", ""),
                        "locked": should_lock,
                        "order": topic_order,
                        "status": "locked" if should_lock else "active"
                    })
                    
                    # Actualizar contadores locales
                    if should_lock:
                        current_locked += 1
                    else:
                        current_active += 1
            
            return {
                "status": "success",
                "message": f"Cola actualizada: {len(generated_topics)} temas generados",
                "generated_topics": len(generated_topics),
                "active_topics": current_active,
                "locked_ahead": current_locked,
                "completed_topics": len(completed_topics),
                "total_generated": len(existing_virtual_topics) + len(generated_topics),
                "remaining_original": len(available_topics) - len(topics_to_generate),
                "details": generated_topics
            }
            
        except Exception as e:
            logging.error(f"Error manteniendo cola de temas optimizada: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    def _generate_single_virtual_topic(self, original_topic: Dict, virtual_module_id: str,
                                     student_id: str, cognitive_profile: Dict, preferences: Dict = None, force_lock: bool = None) -> Tuple[bool, str, int]:
        """
        Genera un único tema virtual optimizado.
        """
        try:
            # Determinar orden del tema
            existing_count = self.db.virtual_topics.count_documents({
                "virtual_module_id": ObjectId(virtual_module_id)
            })
            topic_order = existing_count
            
            # Determinar si debe estar bloqueado
            if force_lock is not None:
                is_locked = force_lock
            else:
                is_locked = existing_count > 0  # Solo el primer tema está desbloqueado por defecto
            
            # Crear tema virtual
            virtual_topic_data = {
                "topic_id": original_topic["_id"],
                "student_id": ObjectId(student_id),
                "virtual_module_id": ObjectId(virtual_module_id),
                "name": original_topic.get("name", ""),
                "description": original_topic.get("theory_content", ""),
                "adaptations": {
                    "cognitive_profile": cognitive_profile,
                    "difficulty_adjustment": self._calculate_difficulty_adjustment(cognitive_profile),
                    "personalization_applied": True
                },
                "order": topic_order,
                "status": "locked" if is_locked else "active",
                "locked": is_locked,
                "progress": 0.0,
                "completion_status": "not_started",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            result = self.db.virtual_topics.insert_one(virtual_topic_data)
            virtual_topic_id = str(result.inserted_id)
            
            # Generar contenidos personalizados
            self.fast_generator._generate_topic_contents_for_sync(
                topic_id=str(original_topic["_id"]),
                virtual_topic_id=virtual_topic_id,
                cognitive_profile=cognitive_profile,
                student_id=student_id,
                preferences=preferences
            )
            
            logging.info(f"Tema virtual generado: {virtual_topic_id} ({'bloqueado' if is_locked else 'activo'})")
            return True, virtual_topic_id, topic_order
            
        except Exception as e:
            logging.error(f"Error generando tema virtual individual: {str(e)}")
            return False, str(e), -1
    
    def _calculate_difficulty_adjustment(self, cognitive_profile: Dict) -> float:
        """
        Calcula ajuste de dificultad basado en perfil cognitivo.
        """
        try:
            difficulties = cognitive_profile.get("cognitive_difficulties", [])
            strengths = cognitive_profile.get("cognitive_strengths", [])
            
            adjustment = 0.0
            
            # Ajustes por dificultades
            if "memoria" in difficulties:
                adjustment -= 0.1
            if "atención" in difficulties:
                adjustment -= 0.1
            if "procesamiento" in difficulties:
                adjustment -= 0.2
            
            # Ajustes por fortalezas
            if "análisis" in strengths:
                adjustment += 0.1
            if "síntesis" in strengths:
                adjustment += 0.1
            
            return max(-0.5, min(0.5, adjustment))
            
        except Exception:
            return 0.0
    
    def trigger_on_progress(self, virtual_topic_id: str, progress_percentage: float) -> Dict:
        """
        Maneja el trigger cuando un tema alcanza cierto progreso.
        Optimizado para mantener la cola de 2 temas.
        
        Args:
            virtual_topic_id: ID del tema virtual
            progress_percentage: Progreso del tema (0-100)
            
        Returns:
            Dict con resultado del trigger
        """
        try:
            # Verificar umbral de trigger (80%)
            if progress_percentage < 80:
                return {
                    "triggered": False,
                    "reason": f"Progreso {progress_percentage}% < 80% requerido"
                }
            
            # Obtener tema virtual
            virtual_topic = self.db.virtual_topics.find_one({"_id": ObjectId(virtual_topic_id)})
            if not virtual_topic:
                return {"error": "Tema virtual no encontrado"}
            
            virtual_module_id = str(virtual_topic["virtual_module_id"])
            
            # Actualizar progreso si llegó al 100%
            if progress_percentage >= 100:
                self.db.virtual_topics.update_one(
                    {"_id": ObjectId(virtual_topic_id)},
                    {"$set": {
                        "progress": 100,
                        "completion_status": "completed",
                        "updated_at": datetime.now()
                    }}
                )
                
                # Desbloquear siguiente tema
                self._unlock_next_topic(virtual_module_id)
            
            # Mantener cola de temas
            queue_result = self.maintain_topic_queue(virtual_module_id, progress_percentage)
            
            return {
                "triggered": True,
                "progress": progress_percentage,
                "topic_completed": progress_percentage >= 100,
                "queue_maintenance": queue_result
            }
            
        except Exception as e:
            logging.error(f"Error en trigger_on_progress: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    def _unlock_next_topic(self, virtual_module_id: str) -> bool:
        """
        Desbloquea el siguiente tema en la secuencia.
        """
        try:
            # Buscar el siguiente tema bloqueado
            next_topic = self.db.virtual_topics.find_one({
                "virtual_module_id": ObjectId(virtual_module_id),
                "locked": True,
                "status": "locked"
            }, sort=[("created_at", 1)])
            
            if next_topic:
                self.db.virtual_topics.update_one(
                    {"_id": next_topic["_id"]},
                    {"$set": {
                        "locked": False,
                        "status": "active",
                        "updated_at": datetime.now()
                    }}
                )
                logging.info(f"Tema desbloqueado: {next_topic['_id']}")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error desbloqueando tema: {str(e)}")
            return False
    
    def get_queue_status(self, virtual_module_id: str) -> Dict:
        """
        Obtiene el estado actual de la cola de temas.
        """
        try:
            # Obtener módulo virtual
            virtual_module = self.db.virtual_modules.find_one({"_id": ObjectId(virtual_module_id)})
            if not virtual_module:
                return {"error": "Módulo virtual no encontrado"}
            
            # Obtener temas virtuales
            virtual_topics = list(self.db.virtual_topics.find({
                "virtual_module_id": ObjectId(virtual_module_id)
            }).sort("created_at", 1))
            
            # Obtener temas originales
            original_topics_count = self.db.topics.count_documents({
                "module_id": virtual_module["module_id"],
                "published": True
            })
            
            # Analizar estado
            active_topics = [vt for vt in virtual_topics if not vt.get("locked", False)]
            locked_topics = [vt for vt in virtual_topics if vt.get("locked", False)]
            completed_topics = [vt for vt in virtual_topics if vt.get("completion_status") == "completed"]
            
            # Calcular siguiente tema necesario
            current_topic = None
            if active_topics:
                current_topic = active_topics[0]  # Primer tema activo
                for topic in active_topics:
                    if topic.get("progress", 0) > current_topic.get("progress", 0):
                        current_topic = topic
            
            return {
                "virtual_module_id": virtual_module_id,
                "total_original_topics": original_topics_count,
                "generated_topics": len(virtual_topics),
                "active_topics": len(active_topics),
                "locked_topics": len(locked_topics),
                "completed_topics": len(completed_topics),
                "queue_ahead": len(locked_topics),
                "current_topic": {
                    "id": str(current_topic["_id"]) if current_topic else None,
                    "name": current_topic.get("name", "") if current_topic else "",
                    "progress": current_topic.get("progress", 0) if current_topic else 0
                } if current_topic else None,
                "needs_generation": len(virtual_topics) < min(3, original_topics_count),
                "can_generate_more": len(virtual_topics) < original_topics_count
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo estado de cola: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    def bulk_initialize_queues(self, max_modules: int = 100) -> Dict:
        """
        Inicializa colas para múltiples módulos virtuales.
        Útil para setup masivo o mantenimiento.
        """
        try:
            # Obtener módulos que necesitan inicialización
            modules_to_init = list(self.db.virtual_modules.find({
                "completion_status": {"$ne": "completed"}
            }).limit(max_modules))
            
            stats = {
                "processed": 0,
                "initialized": 0,
                "skipped": 0,
                "errors": 0,
                "details": []
            }
            
            for module in modules_to_init:
                try:
                    vm_id = str(module["_id"])
                    
                    # Verificar si ya tiene temas
                    existing_topics = self.db.virtual_topics.count_documents({
                        "virtual_module_id": module["_id"]
                    })
                    
                    if existing_topics >= 3:
                        stats["skipped"] += 1
                        stats["details"].append({
                            "module_id": vm_id,
                            "status": "skipped",
                            "reason": f"Ya tiene {existing_topics} temas"
                        })
                        continue
                    
                    # Mantener cola
                    result = self.maintain_topic_queue(vm_id)
                    
                    if result.get("error"):
                        stats["errors"] += 1
                        stats["details"].append({
                            "module_id": vm_id,
                            "status": "error",
                            "error": result["error"]
                        })
                    else:
                        stats["initialized"] += 1
                        stats["details"].append({
                            "module_id": vm_id,
                            "status": "initialized",
                            "generated": result.get("generated_topics", 0)
                        })
                    
                    stats["processed"] += 1
                    
                except Exception as module_error:
                    stats["errors"] += 1
                    stats["details"].append({
                        "module_id": str(module.get("_id", "unknown")),
                        "status": "error",
                        "error": str(module_error)
                    })
            
            return stats
            
        except Exception as e:
            logging.error(f"Error en bulk_initialize_queues: {str(e)}")
            return {"error": str(e)}


class AdaptiveLearningService:
    """
    IMPLEMENTACIÓN TEMPORAL - FASE 1 RL (Reinforcement Learning)
    
    Este servicio implementa una versión simplificada de aprendizaje adaptativo
    basado en análisis estadístico de resultados. Es una solución temporal hasta
    la implementación completa de RL en la Fase 2B.
    
    LIMITACIONES ACTUALES:
    - No utiliza algoritmos de RL avanzados
    - Análisis basado en métricas estadísticas simples
    - No considera contexto temporal profundo ni predicciones complejas
    
    TODO FASE 2B: Reemplazar con implementación completa de RL que incluya:
    - Algoritmos Q-Learning o Policy Gradient
    - Análisis de secuencias temporales
    - Predicción de rendimiento futuro
    - Optimización de rutas de aprendizaje personalizadas
    
    Actualiza el perfil cognitivo basándose en resultados de contenido.
    """

    def __init__(self):
        self.db = get_db()
        # Logging para indicar uso de implementación temporal
        logging.info("Iniciando AdaptiveLearningService - FASE 1 RL (implementación temporal)")

    def update_profile_from_results(self, student_id: str) -> bool:
        """
        TEMPORAL - Versión simplificada para Fase 1.
        
        Análisis estadístico básico de resultados para actualizar perfil cognitivo.
        No utiliza algoritmos de RL avanzados.
        
        FASE 2B implementará:
        - Análisis más sofisticado de resultados
        - Análisis de tiempo, dificultad, y patrones de interacción
        - Algoritmos de aprendizaje por refuerzo
        """
        logging.debug(f"Actualizando perfil adaptativo (FASE 1 RL) para estudiante: {student_id}")
        
        try:
            # Obtener resultados recientes (últimos 30 días para mejor relevancia)
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=30)
            
            results = list(self.db.content_results.find({
                "student_id": ObjectId(student_id),
                "created_at": {"$gte": cutoff_date}
            }).sort("created_at", -1))
            
            if not results:
                # Si no hay resultados recientes, usar todos los disponibles
                results = list(self.db.content_results.find({
                    "student_id": ObjectId(student_id)
                }).sort("created_at", -1).limit(100))
            
            if not results:
                logging.info(f"No se encontraron resultados para estudiante {student_id}")
                return False

            # Análisis avanzado por tipo de contenido
            content_analysis = {}
            
            for res in results:
                vc_id = res.get("virtual_content_id")
                if not vc_id:
                    continue
                    
                vc = self.db.virtual_topic_contents.find_one({"_id": ObjectId(vc_id)})
                if not vc:
                    continue
                
                content_type = vc.get("content_type", "unknown")
                if content_type == "unknown":
                    continue
                
                # Extraer métricas del resultado
                score = res.get("score", 0)
                session_data = res.get("session_data", {})
                learning_metrics = res.get("learning_metrics", {})
                
                # Métricas de rendimiento
                completion_time = session_data.get("completion_time_seconds", 0)
                attempts = session_data.get("attempts", 1)
                completion_percentage = session_data.get("completion_percentage", 100)
                
                # Métricas de engagement
                engagement_score = learning_metrics.get("engagement_score", score)
                difficulty_rating = learning_metrics.get("difficulty_rating", 3)  # 1-5 scale
                
                # Inicializar análisis para este tipo de contenido
                if content_type not in content_analysis:
                    content_analysis[content_type] = {
                        "scores": [],
                        "completion_times": [],
                        "attempts": [],
                        "engagement": [],
                        "difficulty_ratings": [],
                        "completion_rates": [],
                        "total_interactions": 0
                    }
                
                # Agregar métricas
                analysis = content_analysis[content_type]
                analysis["scores"].append(score)
                analysis["completion_times"].append(completion_time)
                analysis["attempts"].append(attempts)
                analysis["engagement"].append(engagement_score)
                analysis["difficulty_ratings"].append(difficulty_rating)
                analysis["completion_rates"].append(completion_percentage)
                analysis["total_interactions"] += 1

            if not content_analysis:
                logging.info(f"No se pudo analizar contenido para estudiante {student_id}")
                return False

            # Calcular métricas agregadas por tipo de contenido
            content_preferences = {}
            
            for content_type, analysis in content_analysis.items():
                if analysis["total_interactions"] < 2:  # Mínimo 2 interacciones para ser significativo
                    continue
                
                # Calcular promedios
                avg_score = sum(analysis["scores"]) / len(analysis["scores"])
                avg_engagement = sum(analysis["engagement"]) / len(analysis["engagement"])
                avg_completion_rate = sum(analysis["completion_rates"]) / len(analysis["completion_rates"])
                avg_attempts = sum(analysis["attempts"]) / len(analysis["attempts"])
                avg_difficulty = sum(analysis["difficulty_ratings"]) / len(analysis["difficulty_ratings"])
                
                # Calcular tiempo promedio (solo para interacciones completadas)
                completed_times = [t for t, c in zip(analysis["completion_times"], analysis["completion_rates"]) if c >= 80]
                avg_time = sum(completed_times) / len(completed_times) if completed_times else 0
                
                # Calcular puntuación de preferencia compuesta
                # Factores: rendimiento (40%), engagement (30%), eficiencia (20%), facilidad (10%)
                performance_score = min(avg_score / 100, 1.0)  # Normalizar a 0-1
                engagement_score = min(avg_engagement / 100, 1.0)
                efficiency_score = max(0, 1 - (avg_attempts - 1) * 0.2)  # Penalizar múltiples intentos
                ease_score = max(0, (6 - avg_difficulty) / 5)  # Invertir escala de dificultad
                
                preference_score = (
                    performance_score * 0.4 +
                    engagement_score * 0.3 +
                    efficiency_score * 0.2 +
                    ease_score * 0.1
                )
                
                content_preferences[content_type] = {
                    "preference_score": preference_score,
                    "avg_score": avg_score,
                    "avg_engagement": avg_engagement,
                    "avg_completion_rate": avg_completion_rate,
                    "avg_attempts": avg_attempts,
                    "avg_difficulty": avg_difficulty,
                    "avg_time_seconds": avg_time,
                    "total_interactions": analysis["total_interactions"]
                }

            # Determinar preferencias y tipos a evitar
            if len(content_preferences) > 1:
                # Ordenar por puntuación de preferencia
                sorted_prefs = sorted(content_preferences.items(), key=lambda x: x[1]["preference_score"], reverse=True)
                
                # Tipos preferidos: top 50% o puntuación >= 0.7
                prefer_threshold = max(0.7, sorted_prefs[len(sorted_prefs)//2][1]["preference_score"])
                prefer_types = [t for t, data in sorted_prefs if data["preference_score"] >= prefer_threshold]
                
                # Tipos a evitar: bottom 25% y puntuación < 0.4
                avoid_threshold = min(0.4, sorted_prefs[int(len(sorted_prefs)*0.75)][1]["preference_score"])
                avoid_types = [t for t, data in sorted_prefs if data["preference_score"] < avoid_threshold and t not in prefer_types]
                
                # Limitar listas para evitar extremos
                prefer_types = prefer_types[:3]  # Máximo 3 tipos preferidos
                avoid_types = avoid_types[:2]   # Máximo 2 tipos a evitar
            else:
                prefer_types = []
                avoid_types = []

            # Actualizar perfil cognitivo
            profile = self.db.cognitive_profiles.find_one({"user_id": ObjectId(student_id)})
            if not profile:
                logging.warning(f"No se encontró perfil cognitivo para estudiante {student_id}")
                return False

            try:
                import json
                profile_data = json.loads(profile.get("profile", "{}"))
            except Exception:
                profile_data = {}

            # Actualizar preferencias de contenido
            content_prefs = profile_data.get("contentPreferences", {})
            content_prefs.update({
                "prefer_types": prefer_types,
                "avoid_types": avoid_types,
                "last_analysis_date": datetime.now().isoformat(),
                "analysis_based_on_interactions": sum(data["total_interactions"] for data in content_preferences.values()),
                "content_analysis": content_preferences  # Guardar análisis detallado
            })
            
            profile_data["contentPreferences"] = content_prefs

            # Actualizar en base de datos
            self.db.cognitive_profiles.update_one(
                {"_id": profile["_id"]},
                {"$set": {
                    "profile": json.dumps(profile_data),
                    "updated_at": datetime.now()
                }}
            )

            logging.info(f"Perfil adaptativo actualizado para {student_id}: prefer={prefer_types}, avoid={avoid_types}")
            return True
            
        except Exception as e:
            logging.error(f"Error actualizando perfil cognitivo desde resultados: {str(e)}")
            return False
    
    def get_content_preferences(self, student_id: str) -> dict:
        """
        Obtiene las preferencias de contenido actuales de un estudiante.
        Útil para debugging y verificación.
        """
        try:
            profile = self.db.cognitive_profiles.find_one({"user_id": ObjectId(student_id)})
            if not profile:
                return {}
            
            import json
            profile_data = json.loads(profile.get("profile", "{}"))
            return profile_data.get("contentPreferences", {})
            
        except Exception as e:
            logging.error(f"Error obteniendo preferencias de contenido: {str(e)}")
            return {}


# Servicios adicionales para completar las Fases 2B y 3

class ContentChangeDetector:
    """
    Detector de cambios en contenido original para sincronización inteligente.
    """
    
    def __init__(self):
        self.db = get_db()
    
    def detect_changes(self, module_id: str, since_date: datetime = None) -> Dict:
        """
        Detecta cambios en un módulo desde una fecha específica.
        """
        try:
            if not since_date:
                since_date = datetime.now() - timedelta(days=7)  # Última semana por defecto
            
            # Detectar cambios en temas
            topic_changes = list(self.db.topics.find({
                "module_id": module_id,
                "updated_at": {"$gte": since_date}
            }))
            
            # Detectar cambios en contenidos
            content_changes = []
            for topic in topic_changes:
                contents = list(self.db.topic_contents.find({
                    "topic_id": str(topic["_id"]),
                    "updated_at": {"$gte": since_date}
                }))
                content_changes.extend(contents)
            
            return {
                "has_changes": len(topic_changes) > 0 or len(content_changes) > 0,
                "topic_changes": len(topic_changes),
                "content_changes": len(content_changes),
                "details": {
                    "topics": [str(t["_id"]) for t in topic_changes],
                    "contents": [str(c["_id"]) for c in content_changes]
                }
            }
            
        except Exception as e:
            logging.error(f"Error detectando cambios: {str(e)}")
            return {"has_changes": False, "error": str(e)}


# Completar implementaciones de servicios existentes (REMOVIDA duplicación de clase)


class UIPerformanceMetricsService:
    """
    Servicio para métricas de rendimiento de UI en tiempo real.
    Implementa tracking de rendimiento de interfaz y optimización automática.
    """
    
    def __init__(self):
        self.db = get_db()
        self.metrics_collection = self.db.ui_performance_metrics
        self.optimization_collection = self.db.ui_optimizations
    
    def record_ui_metrics(self, student_id: str, session_data: Dict) -> bool:
        """
        Registra métricas de rendimiento de UI para un estudiante.
        
        Args:
            student_id: ID del estudiante
            session_data: Datos de la sesión de UI
        """
        try:
            metrics_data = {
                "student_id": ObjectId(student_id),
                "session_id": session_data.get("session_id"),
                "device_info": {
                    "device_type": session_data.get("device_type", "unknown"),
                    "screen_resolution": session_data.get("screen_resolution"),
                    "browser": session_data.get("browser"),
                    "connection_speed": session_data.get("connection_speed")
                },
                "performance_metrics": {
                    "page_load_time": session_data.get("page_load_time", 0),
                    "content_render_time": session_data.get("content_render_time", 0),
                    "interaction_response_time": session_data.get("interaction_response_time", 0),
                    "scroll_performance": session_data.get("scroll_performance", 0),
                    "memory_usage": session_data.get("memory_usage", 0)
                },
                "user_interactions": {
                    "clicks_per_minute": session_data.get("clicks_per_minute", 0),
                    "scroll_events": session_data.get("scroll_events", 0),
                    "navigation_events": session_data.get("navigation_events", 0),
                    "error_events": session_data.get("error_events", 0)
                },
                "accessibility_metrics": {
                    "font_size_adjustments": session_data.get("font_size_adjustments", 0),
                    "contrast_adjustments": session_data.get("contrast_adjustments", 0),
                    "keyboard_navigation_usage": session_data.get("keyboard_navigation_usage", False)
                },
                "timestamp": datetime.now(),
                "session_duration": session_data.get("session_duration", 0)
            }
            
            self.metrics_collection.insert_one(metrics_data)
            
            # Trigger análisis de optimización si es necesario
            self._analyze_and_optimize(student_id, metrics_data)
            
            return True
            
        except Exception as e:
            logging.error(f"Error registrando métricas de UI: {str(e)}")
            return False
    
    def _analyze_and_optimize(self, student_id: str, current_metrics: Dict):
        """
        Analiza métricas y genera optimizaciones automáticas.
        """
        try:
            # Obtener historial de métricas del estudiante
            historical_metrics = list(self.metrics_collection.find({
                "student_id": ObjectId(student_id)
            }).sort("timestamp", -1).limit(10))
            
            if len(historical_metrics) < 3:
                return  # Necesitamos más datos para análisis
            
            # Analizar patrones de rendimiento
            performance_analysis = self._analyze_performance_patterns(historical_metrics)
            
            # Generar optimizaciones
            optimizations = self._generate_optimizations(student_id, performance_analysis)
            
            if optimizations:
                self._save_optimizations(student_id, optimizations)
                
        except Exception as e:
            logging.error(f"Error en análisis de optimización: {str(e)}")
    
    def _analyze_performance_patterns(self, metrics_history: List[Dict]) -> Dict:
        """
        Analiza patrones de rendimiento en el historial de métricas.
        """
        analysis = {
            "avg_load_time": 0,
            "avg_render_time": 0,
            "avg_interaction_time": 0,
            "performance_trend": "stable",
            "problem_areas": [],
            "device_patterns": {},
            "accessibility_usage": False
        }
        
        if not metrics_history:
            return analysis
        
        # Calcular promedios
        total_metrics = len(metrics_history)
        load_times = [m["performance_metrics"]["page_load_time"] for m in metrics_history]
        render_times = [m["performance_metrics"]["content_render_time"] for m in metrics_history]
        interaction_times = [m["performance_metrics"]["interaction_response_time"] for m in metrics_history]
        
        analysis["avg_load_time"] = sum(load_times) / total_metrics
        analysis["avg_render_time"] = sum(render_times) / total_metrics
        analysis["avg_interaction_time"] = sum(interaction_times) / total_metrics
        
        # Detectar problemas de rendimiento
        if analysis["avg_load_time"] > 3000:  # > 3 segundos
            analysis["problem_areas"].append("slow_loading")
        
        if analysis["avg_render_time"] > 1000:  # > 1 segundo
            analysis["problem_areas"].append("slow_rendering")
        
        if analysis["avg_interaction_time"] > 500:  # > 500ms
            analysis["problem_areas"].append("slow_interactions")
        
        # Analizar uso de accesibilidad
        accessibility_usage = any(
            m["accessibility_metrics"]["font_size_adjustments"] > 0 or
            m["accessibility_metrics"]["contrast_adjustments"] > 0 or
            m["accessibility_metrics"]["keyboard_navigation_usage"]
            for m in metrics_history
        )
        analysis["accessibility_usage"] = accessibility_usage
        
        return analysis
    
    def _generate_optimizations(self, student_id: str, analysis: Dict) -> List[Dict]:
        """
        Genera optimizaciones basadas en el análisis de rendimiento.
        """
        optimizations = []
        
        # Optimizaciones para carga lenta
        if "slow_loading" in analysis["problem_areas"]:
            optimizations.append({
                "type": "performance",
                "category": "loading",
                "action": "enable_lazy_loading",
                "description": "Habilitar carga diferida de contenido",
                "priority": "high",
                "estimated_improvement": "30-50% reducción en tiempo de carga"
            })
        
        # Optimizaciones para renderizado lento
        if "slow_rendering" in analysis["problem_areas"]:
            optimizations.append({
                "type": "performance",
                "category": "rendering",
                "action": "reduce_animations",
                "description": "Reducir animaciones complejas",
                "priority": "medium",
                "estimated_improvement": "40-60% mejora en renderizado"
            })
        
        # Optimizaciones de accesibilidad
        if analysis["accessibility_usage"]:
            optimizations.append({
                "type": "accessibility",
                "category": "visual",
                "action": "auto_adjust_contrast",
                "description": "Ajustar contraste automáticamente",
                "priority": "high",
                "estimated_improvement": "Mejor experiencia de accesibilidad"
            })
        
        return optimizations
    
    def _save_optimizations(self, student_id: str, optimizations: List[Dict]):
        """
        Guarda las optimizaciones generadas para el estudiante.
        """
        try:
            optimization_record = {
                "student_id": ObjectId(student_id),
                "optimizations": optimizations,
                "generated_at": datetime.now(),
                "status": "pending",
                "applied_optimizations": []
            }
            
            self.optimization_collection.insert_one(optimization_record)
            logging.info(f"Generadas {len(optimizations)} optimizaciones para estudiante {student_id}")
            
        except Exception as e:
            logging.error(f"Error guardando optimizaciones: {str(e)}")
    
    def get_student_optimizations(self, student_id: str) -> Dict:
        """
        Obtiene las optimizaciones pendientes para un estudiante.
        """
        try:
            optimization_record = self.optimization_collection.find_one({
                "student_id": ObjectId(student_id),
                "status": "pending"
            }, sort=[("generated_at", -1)])
            
            if not optimization_record:
                return {"optimizations": [], "status": "none"}
            
            return {
                "optimizations": optimization_record["optimizations"],
                "status": optimization_record["status"],
                "generated_at": optimization_record["generated_at"]
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo optimizaciones: {str(e)}")
            return {"optimizations": [], "status": "error"}
    
    def get_performance_analytics(self, student_id: str = None, days: int = 7) -> Dict:
        """
        Obtiene analíticas de rendimiento para un estudiante o globales.
        """
        try:
            since_date = datetime.now() - timedelta(days=days)
            
            query = {"timestamp": {"$gte": since_date}}
            if student_id:
                query["student_id"] = ObjectId(student_id)
            
            metrics = list(self.metrics_collection.find(query))
            
            if not metrics:
                return {"analytics": {}, "total_sessions": 0}
            
            # Calcular estadísticas
            total_sessions = len(metrics)
            avg_load_time = sum(m["performance_metrics"]["page_load_time"] for m in metrics) / total_sessions
            avg_render_time = sum(m["performance_metrics"]["content_render_time"] for m in metrics) / total_sessions
            
            # Calcular score de rendimiento general
            performance_score = max(0, 100 - (avg_load_time / 50) - (avg_render_time / 20))
            
            return {
                "analytics": {
                    "avg_load_time": avg_load_time,
                    "avg_render_time": avg_render_time,
                    "performance_score": performance_score
                },
                "total_sessions": total_sessions,
                "period_days": days
            }
            
        except Exception as e:
            logging.error(f"Error obteniendo analíticas de rendimiento: {str(e)}")
            return {"analytics": {}, "total_sessions": 0, "error": str(e)}


class AdaptiveUIOptimizationService:
    """
    Servicio para optimización automática de interfaz basada en patrones de uso.
    """
    
    def __init__(self):
        self.db = get_db()
        self.ui_metrics_service = UIPerformanceMetricsService()
    
    def generate_adaptive_ui_config(self, student_id: str) -> Dict:
        """
        Genera configuración de UI adaptativa para un estudiante.
        """
        try:
            # Obtener perfil cognitivo
            student = self.db.users.find_one({"_id": ObjectId(student_id)})
            if not student:
                return self._get_default_ui_config()
            
            cognitive_profile = student.get("cognitive_profile", {})
            
            # Obtener métricas de rendimiento
            performance_analytics = self.ui_metrics_service.get_performance_analytics(student_id, days=30)
            
            # Obtener optimizaciones pendientes
            optimizations = self.ui_metrics_service.get_student_optimizations(student_id)
            
            # Generar configuración adaptativa
            ui_config = self._build_adaptive_config(cognitive_profile, performance_analytics, optimizations)
            
            return ui_config
            
        except Exception as e:
            logging.error(f"Error generando configuración UI adaptativa: {str(e)}")
            return self._get_default_ui_config()
    
    def _build_adaptive_config(self, cognitive_profile: Dict, performance_analytics: Dict, optimizations: Dict) -> Dict:
        """
        Construye la configuración de UI adaptativa.
        """
        config = {
            "layout": {
                "sidebar_collapsed": False,
                "content_width": "normal",
                "navigation_style": "standard"
            },
            "visual": {
                "theme": "light",
                "font_size": "medium",
                "contrast": "normal",
                "animations": "enabled"
            },
            "performance": {
                "lazy_loading": False,
                "image_compression": False,
                "reduced_animations": False
            },
            "accessibility": {
                "high_contrast": False,
                "dyslexia_font": False,
                "keyboard_navigation_enhanced": False
            }
        }
        
        # Adaptaciones basadas en perfil cognitivo
        if cognitive_profile:
            # Adaptaciones para TDAH
            if self._has_adhd(cognitive_profile):
                config["layout"]["sidebar_collapsed"] = True
                config["visual"]["animations"] = "reduced"
            
            # Adaptaciones para dislexia
            if self._has_dyslexia(cognitive_profile):
                config["accessibility"]["dyslexia_font"] = True
                config["visual"]["font_size"] = "large"
                config["accessibility"]["high_contrast"] = True
        
        # Adaptaciones basadas en rendimiento
        analytics = performance_analytics.get("analytics", {})
        if analytics:
            performance_score = analytics.get("performance_score", 100)
            
            if performance_score < 60:  # Rendimiento bajo
                config["performance"]["lazy_loading"] = True
                config["visual"]["animations"] = "disabled"
        
        # Aplicar optimizaciones pendientes
        for optimization in optimizations.get("optimizations", []):
            if optimization["action"] == "enable_lazy_loading":
                config["performance"]["lazy_loading"] = True
            elif optimization["action"] == "reduce_animations":
                config["visual"]["animations"] = "reduced"
            elif optimization["action"] == "auto_adjust_contrast":
                config["accessibility"]["high_contrast"] = True
        
        return config
    
    def _has_adhd(self, cognitive_profile: Dict) -> bool:
        """
        Detecta si el perfil indica TDAH.
        """
        diagnosis = cognitive_profile.get("diagnosis", "").lower()
        difficulties = " ".join(cognitive_profile.get("cognitive_difficulties", [])).lower()
        
        return ("tda" in diagnosis or "hiperactividad" in diagnosis or
                "distractibilidad" in difficulties or "concentración" in difficulties)
    
    def _has_dyslexia(self, cognitive_profile: Dict) -> bool:
        """
        Detecta si el perfil indica dislexia.
        """
        diagnosis = cognitive_profile.get("diagnosis", "").lower()
        difficulties = " ".join(cognitive_profile.get("cognitive_difficulties", [])).lower()
        
        return ("dislexia" in diagnosis or "lectura" in difficulties or
                "escritura" in difficulties)
    
    def _get_default_ui_config(self) -> Dict:
        """
        Retorna configuración de UI por defecto.
        """
        return {
            "layout": {
                "sidebar_collapsed": False,
                "content_width": "normal",
                "navigation_style": "standard"
            },
            "visual": {
                "theme": "light",
                "font_size": "medium",
                "contrast": "normal",
                "animations": "enabled"
            },
            "performance": {
                "lazy_loading": False,
                "image_compression": False,
                "reduced_animations": False
            },
            "accessibility": {
                "high_contrast": False,
                "dyslexia_font": False,
                "keyboard_navigation_enhanced": False
            }
        }
