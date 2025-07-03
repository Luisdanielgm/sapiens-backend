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
    ContentTemplate
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
            topics = list(self.collection.find(
                {"virtual_module_id": ObjectId(module_id)}
            ).sort("order", 1))
            
            # Convertir ObjectIds a strings
            for topic in topics:
                topic["_id"] = str(topic["_id"])
                topic["virtual_module_id"] = str(topic["virtual_module_id"])
                
            return topics
        except Exception as e:
            print(f"Error al obtener temas del módulo: {str(e)}")
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
        self.templates_collection = self.db["content_templates"]
        
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
            
            # Añadir referencia al módulo original
            virtual_module_data["module_id"] = module_id
            
            # El constructor de VirtualModule ya no espera name/description
            result = self.collection.insert_one(virtual_module_data)
            virtual_module_id = str(result.inserted_id)
            
            # 5. Generar temas virtuales de forma optimizada
            self._generate_virtual_topics_fast(
                module_id, student_id, virtual_module_id, 
                cognitive_profile, timeout - 10
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
                                    remaining_time: int, initial_batch_size: int = 2):
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
            
            logging.info(f"Generando lote inicial de {len(topics_to_generate)} temas para el módulo virtual {virtual_module_id}. "
                         f"({len(topics) - len(topics_to_generate)} pendientes)")

            # Generar contenido para cada tema
            for topic in topics_to_generate:
                try:
                    topic_id = str(topic["_id"])
                    
                    # Crear tema virtual básico
                    virtual_topic_data = {
                        "topic_id": topic_id,
                        "student_id": student_id,
                        "virtual_module_id": virtual_module_id,
                        "adaptations": {
                            "cognitive_profile": cognitive_profile,
                            "difficulty_adjustment": self._calculate_quick_difficulty_adjustment(
                                topic, cognitive_profile
                            )
                        },
                        "status": "active",
                        "progress": 0.0,
                        "completion_status": "not_started"
                    }
                    
                    # Insertar tema virtual
                    # El diccionario ya no contiene 'name'
                    result = self.db.virtual_topics.insert_one(virtual_topic_data)
                    virtual_topic_id = str(result.inserted_id)
                    
                    # Generar contenido personalizado para el tema
                    self._generate_basic_content_from_templates(
                        topic_id=str(topic["_id"]),
                        virtual_topic_id=virtual_topic_id,
                        cognitive_profile=cognitive_profile,
                        virtual_topic_data=virtual_topic_data
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
                        "adaptations": {
                            "cognitive_profile": cognitive_profile,
                            "difficulty_adjustment": self._calculate_quick_difficulty_adjustment(
                                topic, cognitive_profile
                            )
                        },
                        "status": "active",
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
                        cognitive_profile=cognitive_profile
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
    
    def _generate_basic_content_from_templates(self, topic_id: str, 
                                             cognitive_profile: Dict,
                                             virtual_topic_data: Dict):
        """
        Genera contenido básico usando templates pre-generados.
        """
        try:
            # Determinar tipos de contenido preferidos según perfil
            preferred_types = self._get_preferred_content_types(cognitive_profile)
            
            # Obtener templates disponibles
            for content_type in preferred_types[:3]:  # Limitar a 3 tipos
                template = self._get_cached_template(content_type, cognitive_profile)
                
                if template:
                    # Crear contenido basado en template
                    content_data = {
                        "virtual_topic_id": ObjectId(virtual_topic_data["virtual_module_id"]),
                        "content_type": content_type,
                        "content": template["template_data"].get("content", ""),
                        "template_id": template.get("_id"),
                        "created_at": datetime.now(),
                        "generated_from_template": True
                    }
                    
                    self.db.virtual_topic_contents.insert_one(content_data)
                    
        except Exception as e:
            logging.error(f"Error al generar contenido desde templates: {str(e)}")
    
    def _get_preferred_content_types(self, cognitive_profile: Dict) -> List[str]:
        """
        Determina tipos de contenido preferidos según perfil cognitivo.
        """
        types = ["text"]  # Siempre incluir texto como base
        
        # Añadir tipos según fortalezas
        if cognitive_profile.get("visual_strength", 0) > 0.6:
            types.extend(["diagram", "infographic"])
        if cognitive_profile.get("auditory_strength", 0) > 0.6:
            types.append("audio")
        if cognitive_profile.get("kinesthetic_strength", 0) > 0.6:
            types.append("interactive_exercise")
            
        return types
    
    def _get_cached_template(self, content_type: str, cognitive_profile: Dict) -> Optional[Dict]:
        """
        Obtiene un template cacheado para el tipo de contenido especificado.
        """
        try:
            # Buscar template que coincida con tipo y perfil
            template = self.templates_collection.find_one({
                "content_type": content_type,
                "template_type": "content",
                "status": "active"
            })
            
            return template
            
        except Exception as e:
            logging.error(f"Error al obtener template cacheado: {str(e)}")
            return None

    def _generate_topic_contents_for_sync(self, topic_id: str, virtual_topic_id: str, cognitive_profile: Dict):
        """
        Genera contenidos virtuales para un tema específico durante sincronización.
        
        Args:
            topic_id: ID del tema original
            virtual_topic_id: ID del tema virtual recién creado
            cognitive_profile: Perfil cognitivo del estudiante
        """
        try:
            # Obtener contenidos originales del tema
            original_contents = list(self.db.topic_contents.find({
                "topic_id": ObjectId(topic_id),
                "status": "active"
            }))
            
            if not original_contents:
                logging.warning(f"No se encontraron contenidos para el tema {topic_id}")
                return
            
            # Crear VirtualTopicContent para cada contenido original
            for content in original_contents:
                try:
                    virtual_content_data = {
                        "virtual_topic_id": ObjectId(virtual_topic_id),
                        "content_id": content["_id"],
                        "student_id": ObjectId(cognitive_profile.get("student_id")) if cognitive_profile.get("student_id") else None,
                        "personalization_data": {
                            "adapted_for_profile": cognitive_profile,
                            "sync_generated": True,
                            "sync_date": datetime.now(),
                            "content_type": content.get("content_type", "unknown")
                        },
                        "adapted_content": None,  # Usar contenido original
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
                    self.db.virtual_topic_contents.insert_one(virtual_content_data)
                    logging.debug(f"Contenido virtual creado para {content['_id']} en tema {virtual_topic_id}")
                    
                except Exception as e_content:
                    logging.error(f"Error creando contenido virtual para {content.get('_id')}: {e_content}")
            
        except Exception as e:
            logging.error(f"Error en _generate_topic_contents_for_sync: {str(e)}")
