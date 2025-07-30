from typing import Tuple, List, Dict, Optional
from bson import ObjectId
from datetime import datetime, timedelta
import logging

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

    def get_student_modules(self, study_plan_id: str, student_id: str) -> List[Dict]:
        """
        Obtiene todos los módulos virtuales de un estudiante para un plan de estudios dado.
        """
        try:
            # Obtener IDs de módulos del plan de estudios
            module_objs = self.db.modules.find({"study_plan_id": ObjectId(study_plan_id)}, {"_id": 1})
            module_ids = [m["_id"] for m in module_objs]
            # Buscar módulos virtuales del estudiante para esos módulos
            vmods = list(self.collection.find({
                "student_id": ObjectId(student_id),
                "module_id": {"$in": module_ids}
            }))
            # Convertir ObjectId a string
            for vm in vmods:
                vm["_id"] = str(vm["_id"])
                vm["module_id"] = str(vm["module_id"])
                vm["student_id"] = str(vm["student_id"])
            return vmods
        except Exception as e:
            logging.error(f"Error al listar módulos virtuales: {str(e)}")
            return []

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
            virtual_contents = list(self.db.virtual_topic_contents.find(
                {"virtual_topic_id": ObjectId(virtual_topic_id)}
            ).sort("created_at", 1))

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
                    content["original_slide_template"] = original_content.get("slide_template", {})
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
                    "original_slide_template": {},
                    "original_content_type": "legacy_resource"
                })

            return all_content
        except Exception as e:
            logging.error(f"Error al obtener contenidos del tema virtual: {str(e)}")
            return []

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
            
            # Obtener evaluaciones del módulo
            evaluations = list(self.db.evaluations.find({"module_id": ObjectId(module_id)}))
            
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
                cognitive_profile
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
                                    initial_batch_size: int = 2):
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
                        student_id=student_id
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
                        student_id=str(student_id)
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

    def _generate_topic_contents_for_sync(self, topic_id: str, virtual_topic_id: str, cognitive_profile: Dict, student_id: str):
        """
        Genera contenidos virtuales personalizados para un tema específico durante sincronización.
        
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
                "status": {"$in": ["active", "draft", "approved"]}
            }))
            
            if not original_contents:
                logging.warning(f"No se encontraron contenidos para el tema {topic_id}")
                return
            
            # Filtrar y seleccionar contenidos según perfil cognitivo
            selected_contents = self._select_personalized_contents(original_contents, cognitive_profile)
            
            if not selected_contents:
                logging.warning(f"No se pudieron personalizar contenidos para el tema {topic_id}")
                # Como fallback, usar los primeros 3 contenidos disponibles
                selected_contents = original_contents[:3]
            
            # Crear VirtualTopicContent para cada contenido seleccionado
            for content in selected_contents:
                try:
                    # Generar adaptaciones específicas para este contenido
                    personalization_data = self._generate_content_personalization(content, cognitive_profile)
                    
                    virtual_content_data = {
                        "virtual_topic_id": ObjectId(virtual_topic_id),
                        "content_id": content["_id"],
                        "student_id": ObjectId(student_id),
                        "content_type": content.get("content_type", "unknown"),
                        "content": content.get("content", ""),
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
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                    
                    # Insertar contenido virtual
                    result = self.db.virtual_topic_contents.insert_one(virtual_content_data)
                    logging.debug(f"Contenido virtual personalizado creado: {result.inserted_id} para tema {virtual_topic_id}")
                    
                except Exception as e_content:
                    logging.error(f"Error creando contenido virtual para {content.get('_id')}: {e_content}")
            
        except Exception as e:
            logging.error(f"Error en _generate_topic_contents_for_sync: {str(e)}")
    
    def _select_personalized_contents(self, original_contents: List[Dict], cognitive_profile: Dict) -> List[Dict]:
        """
        Selecciona y filtra contenidos según el perfil cognitivo del estudiante.
        *** CORREGIDO PARA MANEJAR LA ESTRUCTURA REAL DE LA BASE DE DATOS ***
        """
        try:
            # --- INICIO DE LA LÓGICA CORREGIDA ---
            
            # PASO 1: Extraer y parsear los datos del perfil cognitivo
            profile_str = cognitive_profile.get("profile", "{}")
            profile_data = {}
            if isinstance(profile_str, str):
                try:
                    import json
                    profile_data = json.loads(profile_str)
                except json.JSONDecodeError:
                    logging.warning("El campo 'profile' no es un JSON válido.")
            
            # Usar datos del nivel raíz si existen (como fallback)
            learning_style = profile_data.get("learningStyle", cognitive_profile.get("learning_style", {}))
            diagnosis = profile_data.get("diagnosis", cognitive_profile.get("diagnosis", ""))
            cognitive_difficulties = profile_data.get("cognitiveDifficulties", cognitive_profile.get("cognitive_difficulties", []))

            # PASO 2: Normalizar puntuaciones VAK (de 0-100 a 0-1)
            visual_score = learning_style.get("visual", 0) / 100.0
            auditory_score = learning_style.get("auditory", 0) / 100.0
            kinesthetic_score = learning_style.get("kinesthetic", 0) / 100.0
            reading_writing_score = learning_style.get("readingWriting", 0) / 100.0 # Corregido a camelCase

            # PASO 3: Inferir discapacidades desde los campos de texto
            diagnosis_lower = diagnosis.lower()
            difficulties_str = " ".join(cognitive_difficulties).lower()
            
            has_adhd = "tda" in diagnosis_lower or "hiperactividad" in diagnosis_lower or \
                       "distractibilidad" in difficulties_str or "concentración" in difficulties_str
            
            has_dyslexia = "dislexia" in diagnosis_lower or "lectura" in difficulties_str or \
                           "escritura" in difficulties_str
            
            # --- FIN DE LA LÓGICA CORREGIDA ---

            # El resto de la lógica de selección de contenidos permanece igual,
            # ya que ahora opera con los datos normalizados y extraídos correctamente.
            
            # ... (el resto del método desde la categorización de contenidos no cambia) ...
            
            # PASO 4: Categorizar contenidos por cobertura y tipo
            complete_contents = []
            specific_contents = []
            evaluative_contents = []
            
            for content in original_contents:
                content_type = content.get("content_type", "")
                
                # Contenidos completos (cubren todo el tema)
                if content_type in ["text", "slides", "video", "feynman", "story", "summary", "narrated_presentation"]:
                    complete_contents.append(content)
                # Contenidos evaluativos
                elif content_type in ["quiz", "exam", "formative_test", "project"]:
                    evaluative_contents.append(content)
                # Contenidos específicos
                else:
                    specific_contents.append(content)
            
            # PASO 5: Validar que hay contenidos para trabajar
            if not complete_contents and len(original_contents) < 2:
                logging.warning(f"Contenidos insuficientes para personalización. Usando todos los disponibles.")
                return original_contents
            
            # PASO 6: Inicializar selección con balance garantizado
            selected_contents = []
            
            # REGLA DE BALANCE #1: Asegurar al menos UN contenido completo
            if complete_contents:
                preferred_complete = self._select_by_vak_preference(
                    complete_contents, visual_score, auditory_score, reading_writing_score, kinesthetic_score
                )
                if preferred_complete:
                    selected_contents.append(preferred_complete)
                    logging.debug(f"Contenido completo seleccionado: {preferred_complete.get('content_type')}")
                else:
                    # Fallback: tomar el primer contenido completo disponible
                    selected_contents.append(complete_contents[0])
                    logging.debug(f"Contenido completo fallback: {complete_contents[0].get('content_type')}")
            else:
                # Si no hay contenidos completos, tomar los 2 primeros específicos
                if len(specific_contents) >= 2:
                    selected_contents.extend(specific_contents[:2])
                    logging.warning("No hay contenidos completos. Usando contenidos específicos como base.")
            
            # PASO 7: Seleccionar contenidos específicos según fortalezas VAK
            preferred_specific = []
            
            # Contenidos visuales (para visual > 0.6)
            if visual_score > 0.6:
                visual_contents = [c for c in specific_contents 
                                if c.get("content_type") in ["diagram", "infographic", "mindmap", "chart", "illustration", "timeline"]]
                preferred_specific.extend(visual_contents[:2])
                logging.debug(f"Agregados {len(visual_contents[:2])} contenidos visuales")
            
            # Contenidos auditivos (para auditory > 0.6)
            if auditory_score > 0.6:
                audio_contents = [c for c in specific_contents 
                               if c.get("content_type") in ["audio", "music"]]
                preferred_specific.extend(audio_contents[:1])
                logging.debug(f"Agregados {len(audio_contents[:1])} contenidos auditivos")
            
            # Contenidos kinestésicos/interactivos (para kinesthetic > 0.6)
            if kinesthetic_score > 0.6:
                interactive_contents = [c for c in specific_contents 
                                     if c.get("content_type") in ["game", "simulation", "virtual_lab", "interactive_exercise", "mini_game"]]
                preferred_specific.extend(interactive_contents[:2])
                logging.debug(f"Agregados {len(interactive_contents[:2])} contenidos interactivos")
            
            # Contenidos para lectura/escritura (para reading > 0.6)
            if reading_writing_score > 0.6:
                text_contents = [c for c in specific_contents 
                               if c.get("content_type") in ["glossary", "examples", "guided_questions", "documents"]]
                preferred_specific.extend(text_contents[:1])
                logging.debug(f"Agregados {len(text_contents[:1])} contenidos de texto")
            
            # PASO 8: Adaptaciones especiales por discapacidades
            if has_adhd:
                # REGLA DE BALANCE #2: ADHD necesita contenidos cortos e interactivos
                adhd_friendly = [c for c in specific_contents 
                               if c.get("content_type") in ["game", "mini_game", "interactive_exercise", "flashcards"]]
                preferred_specific.extend(adhd_friendly[:2])
                logging.debug(f"Agregados {len(adhd_friendly[:2])} contenidos para ADHD")
            
            if has_dyslexia:
                # REGLA DE BALANCE #3: Dislexia prioriza visual/auditivo sobre texto
                dyslexia_friendly = [c for c in specific_contents 
                                   if c.get("content_type") in ["diagram", "audio", "video", "infographic"]]
                preferred_specific.extend(dyslexia_friendly[:2])
                logging.debug(f"Agregados {len(dyslexia_friendly[:2])} contenidos para dislexia")
                
                # Filtrar contenidos de solo texto si hay alternativas suficientes
                if len(preferred_specific) >= 2:
                    original_count = len(selected_contents)
                    selected_contents = [c for c in selected_contents if c.get("content_type") != "text"]
                    if len(selected_contents) < original_count:
                        logging.debug("Removido contenido de texto por dislexia")
            
            # PASO 9: Agregar contenidos específicos seleccionados (sin duplicados)
            seen_ids = {c["_id"] for c in selected_contents}
            for content in preferred_specific:
                if content["_id"] not in seen_ids and len(selected_contents) < 6:
                    selected_contents.append(content)
                    seen_ids.add(content["_id"])
            
            # PASO 10: REGLA DE BALANCE #4 - Incluir contenido evaluativo
            if evaluative_contents and len(selected_contents) < 6:
                eval_content = evaluative_contents[0]
                if eval_content["_id"] not in seen_ids:
                    selected_contents.append(eval_content)
                    logging.debug(f"Agregado contenido evaluativo: {eval_content.get('content_type')}")
            
            # PASO 11: REGLA DE BALANCE #5 - Garantizar mínimo 3 contenidos
            if len(selected_contents) < 3:
                remaining_contents = [c for c in original_contents 
                                    if c["_id"] not in seen_ids]
                needed = 3 - len(selected_contents)
                for content in remaining_contents[:needed]:
                    selected_contents.append(content)
                    logging.debug(f"Agregado contenido de relleno: {content.get('content_type')}")
            
            # PASO 12: Validación final del balance
            final_types = [c.get('content_type') for c in selected_contents]
            complete_types_in_selection = [ct for ct in final_types 
                                         if ct in ["text", "slides", "video", "feynman", "story", "summary", "narrated_presentation"]]
            
            if not complete_types_in_selection and len(selected_contents) > 1:
                logging.warning("ADVERTENCIA: Selección sin contenidos completos. Balance puede estar comprometido.")
            
            # PASO 13: Limitar a máximo 6 contenidos
            if len(selected_contents) > 6:
                selected_contents = selected_contents[:6]
                logging.debug("Limitado a 6 contenidos máximo")
            
            # PASO 14: Validación final del balance con métricas
            balance_metrics = self._validate_content_balance(selected_contents, original_contents)
            
            # Logging final con métricas de calidad
            logging.info(f"BALANCE FINAL - Contenidos personalizados: {len(selected_contents)} de {len(original_contents)} disponibles")
            logging.info(f"Tipos balanceados: {final_types}")
            logging.info(f"Score de balance: {balance_metrics['balance_score']} - Calidad: {balance_metrics['quality_level']}")
            logging.info(f"Cobertura - Completos: {balance_metrics['coverage']['complete']}, Específicos: {balance_metrics['coverage']['specific']}, Evaluativos: {balance_metrics['coverage']['evaluative']}")
            
            # Reportar advertencias si las hay
            if balance_metrics['warnings']:
                for warning in balance_metrics['warnings']:
                    logging.warning(f"BALANCE: {warning}")
            
            # Reportar recomendaciones para futuras mejoras
            if balance_metrics['recommendations']:
                for recommendation in balance_metrics['recommendations']:
                    logging.debug(f"RECOMENDACIÓN: {recommendation}")
            
            return selected_contents
            
        except Exception as e:
            logging.error(f"Error en _select_personalized_contents (con nueva lógica): {str(e)}")
            # Fallback crítico: devolver primeros contenidos disponibles con balance básico
            fallback_contents = original_contents[:min(3, len(original_contents))]
            logging.warning(f"Usando fallback con {len(fallback_contents)} contenidos")
            return fallback_contents
    
    def _select_by_vak_preference(self, contents: List[Dict], visual: float, auditory: float, reading: float, kinesthetic: float) -> Optional[Dict]:
        """
        Selecciona el contenido completo más apropiado según las preferencias VAK.
        
        Args:
            contents: Lista de contenidos completos disponibles
            visual, auditory, reading, kinesthetic: Puntuaciones VAK del estudiante
            
        Returns:
            Contenido seleccionado o None
        """
        if not contents:
            return None
        
        # Mapear tipos de contenido a preferencias VAK
        content_scores = []
        
        for content in contents:
            content_type = content.get("content_type", "")
            score = 0
            
            # Calcular score según tipo de contenido y preferencias
            if content_type in ["video", "slides"] and visual > 0.5:
                score += visual * 2
            elif content_type in ["audio", "narrated_presentation"] and auditory > 0.5:
                score += auditory * 2
            elif content_type in ["text", "feynman", "summary"] and reading > 0.5:
                score += reading * 2
            elif content_type in ["story"] and kinesthetic > 0.5:
                score += kinesthetic * 1.5
            else:
                # Score base para cualquier contenido
                score = 0.5
            
            content_scores.append((content, score))
        
        # Seleccionar el contenido con mayor score
        content_scores.sort(key=lambda x: x[1], reverse=True)
        return content_scores[0][0]
    
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
                "text": 10, "feynman": 15, "slides": 12, "video": 8,
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
            if learning_disabilities.get("dyslexia") and content_type in ["text", "slides"]:
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
            complete_types = ["text", "slides", "video", "feynman", "story", "summary", "narrated_presentation"]
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
            "slides": 1.0, 
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
            content_result_data = {
                "content_id": str(virtual_content.get("content_id", virtual_content["_id"])),
                "student_id": student_id,
                "score": score,
                "feedback": "Contenido completado automáticamente",
                "metrics": {
                    "content_type": virtual_content.get("content_type", "unknown"),
                    "virtual_content_id": str(virtual_content["_id"]),
                    "auto_completed": True,
                    "completion_time": session_data.get("time_spent", 0),
                    "interaction_count": session_data.get("interactions", 1),
                    "personalization_applied": bool(virtual_content.get("personalization_data"))
                },
                "session_type": "auto_completion"
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
            update_data = {
                "interaction_tracking.last_accessed": datetime.now(),
                "interaction_tracking.completion_percentage": completion_percentage,
                "interaction_tracking.completion_status": "completed" if completion_percentage >= 100 else "in_progress",
                "interaction_tracking.sessions": {"$inc": 1} if completion_percentage >= 100 else 0,
                "updated_at": datetime.now()
            }
            
            # Agregar datos de sesión si están disponibles
            if session_data.get("time_spent"):
                update_data["interaction_tracking.total_time_spent"] = {"$inc": session_data["time_spent"]}
            
            # Actualizar documento
            operations = {"$set": {k: v for k, v in update_data.items() if not isinstance(v, dict)}}
            
            # Agregar operaciones de incremento
            inc_operations = {}
            for k, v in update_data.items():
                if isinstance(v, dict) and "$inc" in v:
                    inc_operations[k.replace({"$inc": 1}, "")] = v["$inc"]
            
            if inc_operations:
                operations["$inc"] = inc_operations
            operations["$inc"] = {"interaction_tracking.access_count": 1}
            
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
    
    def get_student_progress_summary(self, student_id: str, virtual_module_id: str = None) -> Dict:
        """
        Obtiene un resumen completo del progreso del estudiante.
        
        Args:
            student_id: ID del estudiante
            virtual_module_id: ID del módulo virtual (opcional)
            
        Returns:
            Dict con estadísticas de progreso
        """
        try:
            # Filtro base
            base_filter = {"student_id": ObjectId(student_id)}
            if virtual_module_id:
                # Obtener temas del módulo específico
                virtual_topics = list(self.db.virtual_topics.find({
                    "virtual_module_id": ObjectId(virtual_module_id)
                }))
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
        Mantiene la cola de temas virtuales asegurando que siempre haya 2 temas disponibles.
        
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
            
            # Obtener temas virtuales existentes
            existing_virtual_topics = list(self.db.virtual_topics.find({
                "virtual_module_id": ObjectId(virtual_module_id)
            }).sort("created_at", 1))
            
            # Obtener temas originales publicados
            original_topics = list(self.db.topics.find({
                "module_id": original_module_id,
                "published": True
            }).sort("created_at", 1))
            
            if not original_topics:
                return {"error": "No hay temas publicados en el módulo original"}
            
            # Analizar estado actual
            generated_topic_ids = {str(vt["topic_id"]) for vt in existing_virtual_topics}
            available_topics = [t for t in original_topics if str(t["_id"]) not in generated_topic_ids]
            
            # Calcular cuántos temas deberían estar disponibles según el progreso
            total_topics = len(original_topics)
            topics_to_have = min(3, total_topics)  # Inicial: 3 temas (1 actual + 2 en cola)
            
            # Si hay progreso, ajustar la cantidad necesaria
            if current_progress > 0:
                completed_topics = len([vt for vt in existing_virtual_topics 
                                     if vt.get("completion_status") == "completed"])
                topics_to_have = min(completed_topics + 3, total_topics)  # Mantener 2 temas por delante
            
            # Determinar cuántos temas generar
            topics_needed = max(0, topics_to_have - len(existing_virtual_topics))
            topics_to_generate = available_topics[:topics_needed]
            
            if not topics_to_generate:
                return {
                    "status": "queue_full",
                    "message": "Cola de temas completa",
                    "existing_topics": len(existing_virtual_topics),
                    "available_ahead": len(available_topics),
                    "total_original": total_topics
                }
            
            # Generar temas faltantes
            generated_topics = []
            for topic in topics_to_generate:
                success, virtual_topic_id, topic_order = self._generate_single_virtual_topic(
                    topic, virtual_module_id, student_id, cognitive_profile
                )
                if success:
                    generated_topics.append({
                        "original_topic_id": str(topic["_id"]),
                        "virtual_topic_id": virtual_topic_id,
                        "name": topic.get("name", ""),
                        "locked": len(existing_virtual_topics) > 0,  # Bloquear si no es el primero
                        "order": topic_order
                    })
                    existing_virtual_topics.append({"_id": ObjectId(virtual_topic_id)})
            
            return {
                "status": "success",
                "generated_topics": len(generated_topics),
                "queue_size": len(existing_virtual_topics),
                "topics_ahead": len(available_topics) - len(topics_to_generate),
                "details": generated_topics
            }
            
        except Exception as e:
            logging.error(f"Error manteniendo cola de temas: {str(e)}")
            return {"error": f"Error interno: {str(e)}"}
    
    def _generate_single_virtual_topic(self, original_topic: Dict, virtual_module_id: str,
                                     student_id: str, cognitive_profile: Dict) -> Tuple[bool, str, int]:
        """
        Genera un único tema virtual optimizado.
        """
        try:
            # Determinar si debe estar bloqueado
            existing_count = self.db.virtual_topics.count_documents({
                "virtual_module_id": ObjectId(virtual_module_id)
            })
            is_locked = existing_count > 0  # Solo el primer tema está desbloqueado
            topic_order = existing_count
            
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
                student_id=student_id
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
