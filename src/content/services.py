from typing import Tuple, List, Dict, Optional, Any
from bson import ObjectId
from datetime import datetime
import json
import logging

from src.shared.database import get_db
from src.shared.constants import STATUS
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import ContentType, TopicContent, VirtualTopicContent, ContentResult, ContentTypes
import re
from src.ai_monitoring.services import AIMonitoringService

class ContentTypeService(VerificationBaseService):
    """
    Servicio para gestionar tipos de contenido unificados.
    Reemplaza servicios separados de game types, simulation types, etc.
    """
    def __init__(self):
        super().__init__(collection_name="content_types")

    def create_content_type(self, content_type_data: Dict) -> Tuple[bool, str]:
        """
        Crea un nuevo tipo de contenido.
        
        Args:
            content_type_data: Datos del tipo de contenido
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Verificar que no exista el código
            existing = self.collection.find_one({"code": content_type_data.get("code")})
            if existing:
                return False, "Ya existe un tipo de contenido con ese código"

            content_type = ContentType(**content_type_data)
            result = self.collection.insert_one(content_type.to_dict())
            
            return True, str(result.inserted_id)
        except Exception as e:
            logging.error(f"Error creando tipo de contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_content_types(self, subcategory: str = None) -> List[Dict]:
        """
        Obtiene tipos de contenido filtrados.
        
        Args:
            subcategory: Subcategoría a filtrar ("game", "simulation", "quiz", etc.)
            
        Returns:
            Lista de tipos de contenido
        """
        query = {"status": "active"}
        if subcategory:
            query["subcategory"] = subcategory
            
        content_types = list(self.collection.find(query))
        for ct in content_types:
            ct["_id"] = str(ct["_id"])
        return content_types

    def get_content_type(self, code: str) -> Optional[Dict]:
        """
        Obtiene un tipo de contenido específico por código.
        """
        content_type = self.collection.find_one({"code": code, "status": "active"})
        if content_type:
            content_type["_id"] = str(content_type["_id"])
        return content_type

class ContentService(VerificationBaseService):
    """
    Servicio unificado para gestionar TODO tipo de contenido.
    Reemplaza GameService, SimulationService, QuizService, etc.
    """
    def __init__(self):
        super().__init__(collection_name="topic_contents")
        self.content_type_service = ContentTypeService()

    def check_topic_exists(self, topic_id: str) -> bool:
        """Verifica si un tema existe."""
        try:
            topic = self.db.topics.find_one({"_id": ObjectId(topic_id)})
            return topic is not None
        except Exception:
            return False

    def create_content(self, content_data: Dict) -> Tuple[bool, str]:
        """
        Crea contenido de cualquier tipo (estático o interactivo).
        
        Args:
            content_data: Datos del contenido a crear
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Validaciones básicas
            topic_id = content_data.get("topic_id")
            content_type = content_data.get("content_type")
            
            if not topic_id or not self.check_topic_exists(topic_id):
                return False, "El tema especificado no existe"
                
            # Verificar que el tipo de contenido existe
            content_type_def = self.content_type_service.get_content_type(content_type)
            if not content_type_def:
                return False, f"Tipo de contenido '{content_type}' no válido"

            # Validaciones específicas para diapositivas
            if content_type == "slides":
                slide_template = content_data.get("slide_template", {})
                if not slide_template:
                    return False, "El contenido de tipo 'slides' requiere un campo 'slide_template' con la plantilla de fondo"
                
                # Validar estructura básica de slide_template
                required_template_fields = ["background", "styles"]
                for field in required_template_fields:
                    if field not in slide_template:
                        return False, f"El slide_template debe incluir el campo '{field}'"

            # Crear contenido explícitamente para mapear campos
            # Convertir content a string si es dict para el extractor de marcadores
            content_for_markers = content_data.get("content", "")
            if isinstance(content_for_markers, dict):
                content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
            markers = ContentPersonalizationService.extract_markers(
                content_for_markers or json.dumps(content_data.get("interactive_data", {}))
            )
            content = TopicContent(
                topic_id=topic_id,
                content_type=content_type,
                content=content_data.get("content", ""),
                interactive_data=content_data.get("interactive_data"),
                learning_methodologies=content_data.get("learning_methodologies"),
                adaptation_options=content_data.get("metadata"), # Mapeo clave
                resources=content_data.get("resources"),
                web_resources=content_data.get("web_resources"),
                generation_prompt=content_data.get("generation_prompt"),
                ai_credits=content_data.get("ai_credits", True),
                personalization_markers=markers,
                slide_template=content_data.get("slide_template", {}),  # Incluir slide_template
                status=content_data.get("status", "draft")
            )
            result = self.collection.insert_one(content.to_dict())
            
            # Actualizar métricas del tipo de contenido
            self.content_type_service.collection.update_one(
                {"code": content_type},
                {"$inc": {"usage_count": 1}}
            )
            
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error creando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_topic_content(self, topic_id: str, content_type: str = None) -> List[Dict]:
        """
        Obtiene contenido de un tema, opcionalmente filtrado por tipo.
        
        Args:
            topic_id: ID del tema
            content_type: Tipo específico de contenido (opcional)
            
        Returns:
            Lista de contenidos
        """
        try:
            query = {
                "topic_id": ObjectId(topic_id),
                "status": {"$in": ["draft", "active", "published"]}
            }
            
            if content_type:
                query["content_type"] = content_type
                
            contents = list(self.collection.find(query).sort("created_at", -1))
            
            # Convertir ObjectIds a strings
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
                if content.get("creator_id"):
                    content["creator_id"] = str(content["creator_id"])
                    
            return contents
            
        except Exception as e:
            logging.error(f"Error obteniendo contenido del tema: {str(e)}")
            return []

    def get_interactive_content(self, topic_id: str) -> List[Dict]:
        """
        Obtiene solo contenido interactivo de un tema.
        """
        try:
            # Obtener tipos interactivos
            type_codes = ContentTypes.get_categories().get("interactive", [])
            
            query = {
                "topic_id": ObjectId(topic_id),
                "content_type": {"$in": type_codes},
                "status": {"$in": ["active", "published"]}
            }
            
            contents = list(self.collection.find(query))
            
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
                
            return contents
            
        except Exception as e:
            logging.error(f"Error obteniendo contenido interactivo: {str(e)}")
            return []

    def update_content(self, content_id: str, update_data: Dict) -> Tuple[bool, str]:
        """
        Actualiza contenido existente.
        """
        try:
            # Obtener contenido actual para validaciones
            current_content = self.get_content(content_id)
            if not current_content:
                return False, "Contenido no encontrado"

            # Validaciones específicas para diapositivas
            content_type = update_data.get("content_type", current_content.get("content_type"))
            if content_type == "slides" and "slide_template" in update_data:
                slide_template = update_data.get("slide_template", {})
                if slide_template:  # Solo validar si se proporciona slide_template
                    # Validar estructura básica de slide_template
                    required_template_fields = ["background", "styles"]
                    for field in required_template_fields:
                        if field not in slide_template:
                            return False, f"El slide_template debe incluir el campo '{field}'"

            update_data["updated_at"] = datetime.now()

            if "content" in update_data or "interactive_data" in update_data:
                # Convertir content a string si es dict para el extractor de marcadores
                content_for_markers = update_data.get("content", "")
                if isinstance(content_for_markers, dict):
                    content_for_markers = json.dumps(content_for_markers, ensure_ascii=False)
                markers = ContentPersonalizationService.extract_markers(
                    content_for_markers or json.dumps(update_data.get("interactive_data", {}))
                )
                update_data["personalization_markers"] = markers

            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return True, "Contenido actualizado exitosamente"
            else:
                return False, "No se encontró el contenido o no hubo cambios"
                
        except Exception as e:
            logging.error(f"Error actualizando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def delete_content(self, content_id: str) -> Tuple[bool, str]:
        """
        Elimina contenido (soft delete).
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": {"status": "deleted", "updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                return True, "Contenido eliminado exitosamente"
            else:
                return False, "No se encontró el contenido"
                
        except Exception as e:
            logging.error(f"Error eliminando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_content(self, content_id: str) -> Optional[Dict]:
        """Obtiene un contenido específico por su ID."""
        try:
            content = self.collection.find_one({"_id": ObjectId(content_id)})
            if not content:
                return None

            content["_id"] = str(content["_id"])
            content["topic_id"] = str(content["topic_id"])
            if content.get("creator_id"):
                content["creator_id"] = str(content["creator_id"])

            return content
        except Exception as e:
            logging.error(f"Error obteniendo contenido: {str(e)}")
            return None

    def adapt_content_to_methodology(self, content_id: str, methodology_code: str) -> Tuple[bool, Dict]:
        """Adapta un contenido según una metodología de aprendizaje."""
        try:
            from src.study_plans.services import TopicContentService

            topic_content_service = TopicContentService()
            return topic_content_service.adapt_content_to_methodology(content_id, methodology_code)
        except Exception as e:
            logging.error(f"Error adaptando contenido: {str(e)}")
            return False, {"error": str(e)}

class VirtualContentService(VerificationBaseService):
    """
    Servicio para contenido personalizado por estudiante.
    Unifica virtual_games, virtual_simulations, etc.
    """
    def __init__(self):
        super().__init__(collection_name="virtual_topic_contents")

    def personalize_content(self, virtual_topic_id: str, content_id: str, 
                          student_id: str, cognitive_profile: Dict) -> Tuple[bool, str]:
        """
        Personaliza contenido para un estudiante específico.
        
        Args:
            virtual_topic_id: ID del tema virtual
            content_id: ID del contenido base
            student_id: ID del estudiante
            cognitive_profile: Perfil cognitivo del estudiante
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            # Obtener contenido base
            content = get_db().topic_contents.find_one({"_id": ObjectId(content_id)})
            if not content:
                return False, "Contenido no encontrado"

            # Generar adaptaciones basadas en perfil cognitivo
            personalization_data = self._generate_personalization(content, cognitive_profile)
            
            # Verificar si ya existe personalización
            existing = self.collection.find_one({
                "virtual_topic_id": ObjectId(virtual_topic_id),
                "content_id": ObjectId(content_id),
                "student_id": ObjectId(student_id)
            })
            
            if existing:
                # Actualizar personalización existente
                result = self.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "personalization_data": personalization_data,
                        "updated_at": datetime.now()
                    }}
                )
                return True, str(existing["_id"])
            else:
                # Crear nueva personalización
                virtual_content = VirtualTopicContent(
                    virtual_topic_id=virtual_topic_id,
                    content_id=content_id,
                    student_id=student_id,
                    personalization_data=personalization_data
                )
                
                result = self.collection.insert_one(virtual_content.to_dict())
                return True, str(result.inserted_id)
                
        except Exception as e:
            logging.error(f"Error personalizando contenido: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def _generate_personalization(self, content: Dict, cognitive_profile: Dict) -> Dict:
        """
        Genera adaptaciones basadas en perfil cognitivo.
        """
        personalization = {
            "difficulty_adjustment": 0,
            "time_allocation": 1.0,
            "interface_adaptations": {},
            "content_adaptations": {},
            "accessibility_options": {}
        }
        
        # Adaptaciones por tipo de contenido
        content_type = content.get("content_type", "")
        
        # Adaptaciones generales por perfil VAK
        vak_scores = cognitive_profile.get("vak_scores", {})
        
        if vak_scores.get("visual", 0) > 0.7:
            personalization["content_adaptations"]["enhance_visuals"] = True
            personalization["interface_adaptations"]["visual_emphasis"] = True
            
        if vak_scores.get("auditory", 0) > 0.7:
            personalization["content_adaptations"]["add_audio"] = True
            personalization["accessibility_options"]["audio_descriptions"] = True
            
        if vak_scores.get("kinesthetic", 0) > 0.7:
            personalization["content_adaptations"]["increase_interactivity"] = True
            personalization["interface_adaptations"]["tactile_feedback"] = True
        
        # Adaptaciones por dificultades de aprendizaje
        learning_disabilities = cognitive_profile.get("learning_disabilities", {})
        
        if learning_disabilities.get("dyslexia"):
            personalization["accessibility_options"]["high_contrast"] = True
            personalization["accessibility_options"]["dyslexia_font"] = True
            personalization["content_adaptations"]["reduce_text_density"] = True
            
        if learning_disabilities.get("adhd"):
            personalization["interface_adaptations"]["minimize_distractions"] = True
            personalization["content_adaptations"]["shorter_segments"] = True
            personalization["time_allocation"] = 1.5  # Más tiempo
            
        # Adaptaciones específicas por tipo de contenido interactivo
        if content_type in ["game", "simulation", "quiz"]:
            if cognitive_profile.get("attention_span") == "short":
                personalization["content_adaptations"]["break_into_segments"] = True
                personalization["interface_adaptations"]["progress_indicators"] = True
                
        return personalization

    def track_interaction(self, virtual_content_id: str, interaction_data: Dict) -> bool:
        """
        Registra interacción con contenido personalizado.
        """
        try:
            update_data = {
                "interaction_tracking.last_accessed": datetime.now(),
                "interaction_tracking.access_count": {"$inc": 1},
                "updated_at": datetime.now()
            }
            
            # Agregar datos específicos de la interacción
            if interaction_data.get("time_spent"):
                update_data["interaction_tracking.total_time_spent"] = {"$inc": interaction_data["time_spent"]}
                
            if interaction_data.get("completion_percentage"):
                update_data["interaction_tracking.completion_percentage"] = interaction_data["completion_percentage"]
                
            if interaction_data.get("completion_status"):
                update_data["interaction_tracking.completion_status"] = interaction_data["completion_status"]
                
            result = self.collection.update_one(
                {"_id": ObjectId(virtual_content_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logging.error(f"Error registrando interacción: {str(e)}")
            return False

class ContentResultService(VerificationBaseService):
    """
    Servicio unificado para resultados de contenido interactivo.
    Reemplaza GameResultService, SimulationResultService, QuizResultService.
    """
    def __init__(self):
        super().__init__(collection_name="content_results")

    def record_result(self, result_data: Dict) -> Tuple[bool, str]:
        """
        Registra resultado de interacción con contenido.
        
        Args:
            result_data: Datos del resultado
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje/ID)
        """
        try:
            content_result = ContentResult(**result_data)
            result = self.collection.insert_one(content_result.to_dict())
            
            # Actualizar tracking solo si es un resultado de contenido virtual
            if result_data.get("virtual_content_id"):
                virtual_content_service = VirtualContentService()
                virtual_content_service.track_interaction(
                    result_data["virtual_content_id"],
                    result_data.get("session_data", {})
                )
            
            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error registrando resultado: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_student_results(self, student_id: str, content_type: str = None, evaluation_id: str = None) -> List[Dict]:
        """
        Obtiene resultados de un estudiante, opcionalmente filtrados.
        """
        try:
            # Si se especifica tipo de contenido, primero buscar contenidos virtuales de ese tipo
            query = {"student_id": ObjectId(student_id)}
            
            if evaluation_id:
                query["evaluation_id"] = ObjectId(evaluation_id)

            if content_type:
                # Buscar contenidos virtuales del tipo especificado
                virtual_contents = list(get_db().virtual_topic_contents.find({
                    "student_id": ObjectId(student_id)
                }))
                
                # Filtrar por tipo de contenido
                content_ids = []
                for vc in virtual_contents:
                    content = get_db().topic_contents.find_one({
                        "_id": vc["content_id"],
                        "content_type": content_type
                    })
                    if content:
                        content_ids.append(vc["_id"])
                
                query["virtual_content_id"] = {"$in": content_ids}
            
            results = list(self.collection.find(query).sort("created_at", -1))
            
            for result in results:
                result["_id"] = str(result["_id"])
                result["virtual_content_id"] = str(result["virtual_content_id"])
                result["student_id"] = str(result["student_id"])
                
            return results
            
        except Exception as e:
            logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
            return []


class ContentPersonalizationService:
    """Procesa contenido para identificar marcadores de personalización"""

    marker_pattern = re.compile(r"{{(.*?)}}")

    @classmethod
    def extract_markers(cls, text: str) -> Dict:
        segments = []
        last_idx = 0
        for match in cls.marker_pattern.finditer(text):
            start, end = match.span()
            if start > last_idx:
                segments.append({"type": "static", "content": text[last_idx:start]})
            marker_id = match.group(1)
            segments.append({"type": "marker", "id": marker_id})
            last_idx = end
        if last_idx < len(text):
            segments.append({"type": "static", "content": text[last_idx:]})
        return {"segments": segments}

class ContentGenerationService(VerificationBaseService):
    """
    Servicio para gestionar la generación de contenido en lote y de forma asíncrona.
    """
    def __init__(self):
        super().__init__(collection_name="content_generation_tasks")
        self.ai_monitoring_service = AIMonitoringService()

    def create_generation_task(self, topic_id: str, user_id: str, requested_types: List[str]) -> Tuple[bool, str]:
        """
        Crea una nueva tarea de generación de contenido en lote.

        Args:
            topic_id: ID del tema para el cual generar contenido.
            user_id: ID del usuario que solicita la generación.
            requested_types: Lista de content_type a generar.

        Returns:
            Tuple[bool, str]: (Éxito, ID de la tarea o mensaje de error)
        """
        try:
            # Validaciones
            if not self.check_topic_exists(topic_id):
                return False, "El tema especificado no existe."
            if not self.check_user_exists(user_id):
                return False, "El usuario especificado no existe."
            if not requested_types:
                return False, "Debe solicitar al menos un tipo de contenido."

            # Crear sub-tareas iniciales
            subtasks = [{"content_type": c_type, "status": "pending", "attempts": 0} for c_type in requested_types]

            # Crear la tarea principal
            task_data = {
                "topic_id": ObjectId(topic_id),
                "user_id": ObjectId(user_id),
                "requested_content_types": requested_types,
                "subtasks": subtasks,
                "status": "pending",
            }
            
            # Usar el modelo Pydantic para validar y crear el diccionario
            from .models import ContentGenerationTask
            task_model = ContentGenerationTask(**task_data)
            task_to_insert = task_model.to_db()

            result = self.collection.insert_one(task_to_insert)
            task_id = str(result.inserted_id)

            # Aquí se podría encolar la tarea para un worker asíncrono.
            # Por ahora, la dejamos en estado 'pending'.
            # process_generation_task.delay(task_id) # Ejemplo con Celery

            return True, task_id
        except Exception as e:
            logging.error(f"Error creando la tarea de generación de contenido: {str(e)}")
            return False, "Ocurrió un error interno al crear la tarea."

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Obtiene el estado y progreso de una tarea de generación.
        """
        try:
            task = self.collection.find_one({"_id": ObjectId(task_id)})
            if not task:
                return None
            
            # Calcular progreso
            completed_subtasks = len([st for st in task.get("subtasks", []) if st["status"] == "completed"])
            total_subtasks = len(task.get("requested_content_types", []))
            progress = (completed_subtasks / total_subtasks) * 100 if total_subtasks > 0 else 0
            
            task["progress"] = round(progress, 2)
            
            # Enriquecer con información de contenidos generados
            generated_content = []
            for subtask in task.get("subtasks", []):
                if subtask.get("status") == "completed" and subtask.get("content_id"):
                    content_info = get_db().topic_contents.find_one(
                        {"_id": ObjectId(subtask["content_id"])},
                        {"content_type": 1, "title": 1, "status": 1} # Proyectar solo campos necesarios
                    )
                    if content_info:
                        generated_content.append(ensure_json_serializable(content_info))

            task["generated_content"] = generated_content
            return ensure_json_serializable(task)
        except Exception as e:
            logging.error(f"Error obteniendo estado de la tarea {task_id}: {str(e)}")
            return None
