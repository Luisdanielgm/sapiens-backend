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
from .slide_style_service import SlideStyleService
import re
from src.ai_monitoring.services import AIMonitoringService
from .structured_sequence_service import StructuredSequenceService
from .template_recommendation_service import TemplateRecommendationService
from .embedded_content_service import EmbeddedContentService

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
        self.slide_style_service = SlideStyleService()
        self.structured_sequence_service = StructuredSequenceService(get_db())
        self.template_recommendation_service = TemplateRecommendationService()
        self.embedded_content_service = EmbeddedContentService(self.db)

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
            
            # TEMPORAL: Comentar validación de topic_id para pruebas
            # if not topic_id or not self.check_topic_exists(topic_id):
            #     return False, "El tema especificado no existe"
                
            # Verificar que el tipo de contenido existe
            content_type_def = self.content_type_service.get_content_type(content_type)
            if not content_type_def:
                return False, f"Tipo de contenido '{content_type}' no válido"

            # Validaciones específicas para diapositivas (tanto 'slides' como 'slide')
            if content_type in ["slides", "slide"]:
                slide_template = content_data.get("slide_template", {})
                if not slide_template:
                    return False, f"El contenido de tipo '{content_type}' requiere un campo 'slide_template' con la plantilla de fondo"
                
                # Validar estructura del slide_template usando el servicio
                if not self.slide_style_service.validate_slide_template(slide_template):
                    return False, "El slide_template no tiene una estructura válida"

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
        Ordena por campo 'order' ascendente, con fallback a created_at descendente.
        
        Args:
            topic_id: ID del tema
            content_type: Tipo específico de contenido (opcional)
            
        Returns:
            Lista de contenidos ordenados
        """
        try:
            query = {
                "topic_id": ObjectId(topic_id),
                "status": {"$in": ["draft", "active", "published"]}
            }
            
            if content_type:
                query["content_type"] = content_type
                
            # Ordenamiento: primero por 'order' ascendente (nulls last), luego por created_at descendente
            contents = list(self.collection.find(query).sort([
                ("order", 1),  # Ascendente, valores null van al final
                ("created_at", -1)  # Descendente como fallback
            ]))
            
            # Convertir ObjectIds a strings
            for content in contents:
                content["_id"] = str(content["_id"])
                content["topic_id"] = str(content["topic_id"])
                if content.get("creator_id"):
                    content["creator_id"] = str(content["creator_id"])
                if content.get("parent_content_id"):
                    content["parent_content_id"] = str(content["parent_content_id"])
                    
            return contents
            
        except Exception as e:
            logging.error(f"Error obteniendo contenido del tema: {str(e)}")
            return []
    
    def get_structured_topic_content(self, topic_id: str, student_id: str = None) -> List[Dict]:
        """
        Obtiene contenido de un tema usando la secuencia estructurada.
        Reemplaza la intercalación aleatoria con una secuencia predecible:
        diapositivas → contenidos opcionales → evaluación
        
        Args:
            topic_id: ID del tema
            student_id: ID del estudiante (para personalización futura)
            
        Returns:
            Lista de contenidos en secuencia estructurada
        """
        try:
            return self.structured_sequence_service.get_structured_content_sequence(
                topic_id=topic_id,
                student_id=student_id
            )
        except Exception as e:
            logging.error(f"Error obteniendo secuencia estructurada: {str(e)}")
            # Fallback al método tradicional si falla la secuencia estructurada
            return self.get_topic_content(topic_id)
    
    def validate_topic_sequence(self, topic_id: str) -> Tuple[bool, List[str]]:
        """
        Valida la integridad de la secuencia estructurada de un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Tuple[bool, List[str]]: (es_válida, lista_de_errores)
        """
        try:
            return self.structured_sequence_service.validate_sequence_integrity(topic_id)
        except Exception as e:
            logging.error(f"Error validando secuencia del tema: {str(e)}")
            return False, [f"Error interno: {str(e)}"]
    
    def reorder_topic_slides(self, topic_id: str, slide_order_mapping: Dict[str, int]) -> Tuple[bool, str]:
        """
        Reordena las diapositivas de un tema.
        
        Args:
            topic_id: ID del tema
            slide_order_mapping: Dict {slide_id: new_order}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            return self.structured_sequence_service.reorder_slides(topic_id, slide_order_mapping)
        except Exception as e:
            logging.error(f"Error reordenando diapositivas: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_topic_sequence_statistics(self, topic_id: str) -> Dict:
        """
        Obtiene estadísticas de la secuencia estructurada de un tema.
        
        Args:
            topic_id: ID del tema
            
        Returns:
            Dict con estadísticas de la secuencia
        """
        try:
            return self.structured_sequence_service.get_sequence_statistics(topic_id)
        except Exception as e:
            logging.error(f"Error obteniendo estadísticas de secuencia: {str(e)}")
            return {}
    
    def generate_slide_template(self, palette_name: str = None, font_family: str = None, custom_colors: Dict = None) -> Dict:
        """
        Genera un slide_template usando el servicio de estilo de diapositivas.
        
        Args:
            palette_name: Nombre de la paleta predefinida (opcional)
            font_family: Familia de fuente específica (opcional)
            custom_colors: Colores personalizados (opcional)
            
        Returns:
            Dict con el slide_template generado
        """
        return self.slide_style_service.generate_slide_template(
            palette_name=palette_name,
            font_family=font_family,
            custom_colors=custom_colors
        )
    
    def get_available_slide_palettes(self) -> List[str]:
        """
        Obtiene las paletas de colores disponibles para diapositivas.
        
        Returns:
            Lista de nombres de paletas disponibles
        """
        return self.slide_style_service.get_available_palettes()
    
    def get_slide_palette_preview(self, palette_name: str) -> Optional[Dict]:
        """
        Obtiene una vista previa de una paleta específica.
        
        Args:
            palette_name: Nombre de la paleta
            
        Returns:
            Dict con los colores de la paleta o None si no existe
        """
        return self.slide_style_service.get_palette_preview(palette_name)

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

    def get_template_recommendations(self, topic_id: str, student_id: str = None) -> Dict:
        """
        Obtiene recomendaciones de plantillas para cada diapositiva de un tema.
        
        Args:
            topic_id: ID del tema
            student_id: ID del estudiante (para personalización futura)
            
        Returns:
            Dict con recomendaciones por diapositiva
        """
        try:
            return self.template_recommendation_service.get_topic_recommendations(
                topic_id=topic_id,
                student_id=student_id
            )
        except Exception as e:
            logging.error(f"Error obteniendo recomendaciones de plantillas: {str(e)}")
            return {}
    
    def apply_template_recommendations(self, topic_id: str, recommendations: Dict) -> Tuple[bool, str]:
        """
        Aplica recomendaciones de plantillas a las diapositivas de un tema.
        
        Args:
            topic_id: ID del tema
            recommendations: Dict con recomendaciones {slide_id: template_id}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            return self.template_recommendation_service.apply_recommendations(
                topic_id=topic_id,
                recommendations=recommendations
            )
        except Exception as e:
            logging.error(f"Error aplicando recomendaciones de plantillas: {str(e)}")
            return False, f"Error interno: {str(e)}"
    
    def get_slide_template_compatibility(self, slide_id: str, template_id: str) -> Dict:
        """
        Analiza la compatibilidad entre una diapositiva y una plantilla.
        
        Args:
            slide_id: ID de la diapositiva
            template_id: ID de la plantilla
            
        Returns:
            Dict con análisis de compatibilidad
        """
        try:
            return self.template_recommendation_service.analyze_slide_template_compatibility(
                slide_id=slide_id,
                template_id=template_id
            )
        except Exception as e:
            logging.error(f"Error analizando compatibilidad de plantilla: {str(e)}")
            return {}
    
    def submit_template_feedback(self, student_id: str, topic_id: str, slide_id: str,
                               template_id: str, feedback_data: Dict) -> Tuple[bool, str]:
        """
        Envía feedback sobre el uso de una plantilla al sistema RL.
        
        Args:
            student_id: ID del estudiante
            topic_id: ID del tema
            slide_id: ID de la diapositiva
            template_id: ID de la plantilla utilizada
            feedback_data: Datos de feedback
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        return self.template_recommendation_service.submit_template_feedback(
            student_id, topic_id, slide_id, template_id, feedback_data
        )
    
    # Métodos para contenido embebido vs separado
    def analyze_content_embedding_strategy(self, slide_id: str, content_id: str):
        """
        Analiza si un contenido debe ser embebido o separado de una diapositiva.
        """
        return self.embedded_content_service.analyze_content_embedding_strategy(slide_id, content_id)
    
    def embed_content_in_slide(self, slide_id: str, content_id: str, embed_position: str = 'bottom'):
        """
        Embebe un contenido dentro de una diapositiva.
        """
        return self.embedded_content_service.embed_content_in_slide(slide_id, content_id, embed_position)
    
    def extract_embedded_content(self, slide_id: str, content_id: str):
        """
        Extrae un contenido embebido y lo convierte en contenido separado.
        """
        return self.embedded_content_service.extract_embedded_content(slide_id, content_id)
    
    def get_embedding_recommendations(self, topic_id: str):
        """
        Obtiene recomendaciones de embedding para todos los contenidos de un tema.
        """
        return self.embedded_content_service.get_embedding_recommendations(topic_id)
    
    def get_embedding_statistics(self, topic_id: str):
        """
        Obtiene estadísticas de embedding para un tema.
        """
        return self.embedded_content_service.get_embedding_statistics(topic_id)

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
        Elimina contenido (soft delete) y sus contenidos hijos en cascada.
        """
        try:
            # Primero eliminar contenidos hijos (cascada)
            child_contents = self.collection.find({"parent_content_id": ObjectId(content_id)})
            child_count = 0
            
            for child in child_contents:
                child_result = self.collection.update_one(
                    {"_id": child["_id"]},
                    {"$set": {"status": "deleted", "updated_at": datetime.now()}}
                )
                if child_result.modified_count > 0:
                    child_count += 1
            
            # Luego eliminar el contenido principal
            result = self.collection.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": {"status": "deleted", "updated_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                message = "Contenido eliminado exitosamente"
                if child_count > 0:
                    message += f" (incluyendo {child_count} contenidos hijos)"
                return True, message
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
            # Derivar score y métricas desde session_data/learning_metrics
            session_data = result_data.pop("session_data", {}) or {}
            learning_metrics = result_data.pop("learning_metrics", {}) or {}

            if "score" not in result_data:
                score = session_data.get("score")
                if score is None:
                    completion = session_data.get("completion_percentage")
                    if completion is not None:
                        score = completion / 100.0
                result_data["score"] = score if score is not None else 0.0

            metrics = result_data.get("metrics", {})
            metrics.update(session_data)
            metrics.update(learning_metrics)
            result_data["metrics"] = metrics

            # Asegurar que virtual_content_id esté presente si existe información suficiente
            if not result_data.get("virtual_content_id"):
                student_id = result_data.get("student_id")
                content_id = result_data.get("content_id")
                if student_id and content_id:
                    virtual_content = get_db().virtual_topic_contents.find_one({
                        "student_id": ObjectId(student_id),
                        "content_id": ObjectId(content_id)
                    })
                    if virtual_content:
                        result_data["virtual_content_id"] = str(virtual_content["_id"])
                    else:
                        logging.warning(
                            f"No se encontró virtual_content_id para content_id: {content_id}, student_id: {student_id}"
                        )

            # Validar y convertir evaluation_id si está presente
            if result_data.get("evaluation_id"):
                try:
                    ObjectId(result_data["evaluation_id"])  # Validar formato
                except Exception:
                    logging.warning(f"evaluation_id inválido: {result_data['evaluation_id']}")
                    result_data.pop("evaluation_id", None)

            content_result = ContentResult(**result_data)
            result = self.collection.insert_one(content_result.to_dict())

            if result_data.get("virtual_content_id"):
                try:
                    virtual_content_service = VirtualContentService()
                    virtual_content_service.track_interaction(
                        result_data["virtual_content_id"],
                        session_data,
                    )
                except Exception as track_error:
                    logging.warning(
                        f"Error actualizando tracking de contenido virtual: {track_error}"
                    )

            # Enviar feedback automático al sistema RL para aprendizaje granular
            try:
                from src.personalization.services import AdaptivePersonalizationService
                
                # Preparar datos de feedback para el modelo RL
                feedback_data = {
                    "student_id": result_data["student_id"],
                    "content_id": result_data.get("virtual_content_id") or result_data.get("content_id"),
                    "interaction_type": result_data.get("session_type", "content_interaction"),
                    "performance_score": result_data["score"],
                    "engagement_metrics": result_data.get("metrics", {})
                }
                
                # Enviar feedback al sistema RL de forma asíncrona
                personalization_service = AdaptivePersonalizationService()
                success, message = personalization_service.submit_learning_feedback(feedback_data)
                
                if success:
                    logging.info(f"Feedback RL enviado exitosamente para ContentResult {result.inserted_id}")
                else:
                    logging.warning(f"Error enviando feedback RL: {message}")
                    
            except Exception as rl_error:
                logging.warning(f"Error enviando feedback al sistema RL: {str(rl_error)}")

            return True, str(result.inserted_id)
            
        except Exception as e:
            logging.error(f"Error registrando resultado: {str(e)}")
            return False, f"Error interno: {str(e)}"

    def get_student_results(self, student_id: str, virtual_content_id: str = None, content_type: str = None, evaluation_id: str = None) -> List[Dict]:
        """
        Obtiene resultados de un estudiante, filtrados por virtual_content_id como clave principal.
        
        Args:
            student_id: ID del estudiante
            virtual_content_id: ID del contenido virtual (clave principal)
            content_type: Tipo de contenido (opcional, para compatibilidad)
            evaluation_id: ID de evaluación (opcional)
        """
        try:
            query = {"student_id": ObjectId(student_id)}
            
            # Usar virtual_content_id como filtro principal si se proporciona
            if virtual_content_id:
                query["virtual_content_id"] = ObjectId(virtual_content_id)
            elif content_type:
                # Fallback: buscar por tipo de contenido si no hay virtual_content_id
                # Buscar contenidos virtuales del tipo especificado
                virtual_contents = list(get_db().virtual_topic_contents.find({
                    "student_id": ObjectId(student_id),
                    "content_type": content_type
                }))
                
                if virtual_contents:
                    virtual_content_ids = [vc["_id"] for vc in virtual_contents]
                    query["virtual_content_id"] = {"$in": virtual_content_ids}
                else:
                    return []  # No hay contenidos virtuales de este tipo
            
            if evaluation_id:
                query["evaluation_id"] = ObjectId(evaluation_id)
            
            results = list(self.collection.find(query).sort("recorded_at", -1))
            
            # Convertir ObjectIds a strings para JSON
            for result in results:
                result["_id"] = str(result["_id"])
                result["student_id"] = str(result["student_id"])
                if result.get("content_id"):
                    result["content_id"] = str(result["content_id"])
                if result.get("virtual_content_id"):
                    result["virtual_content_id"] = str(result["virtual_content_id"])
                if result.get("evaluation_id"):
                    result["evaluation_id"] = str(result["evaluation_id"])
                
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
    
    @classmethod
    def apply_markers(cls, content: Dict, student: Dict) -> Dict:
        """
        Aplica marcadores de personalización reemplazando placeholders con datos del estudiante.
        
        Args:
            content: Contenido con posibles marcadores {{student.campo}}
            student: Datos del estudiante para reemplazar
            
        Returns:
            Dict: Contenido con marcadores reemplazados
        """
        try:
            # Crear una copia del contenido para no modificar el original
            personalized_content = content.copy()
            
            # Función auxiliar para reemplazar marcadores en texto
            def replace_markers_in_text(text: str) -> str:
                if not isinstance(text, str):
                    return text
                    
                def replace_marker(match):
                    marker = match.group(1).strip()
                    
                    # Soportar notación de punto para acceder a campos anidados
                    if marker.startswith('student.'):
                        field_path = marker[8:]  # Remover 'student.'
                        value = cls._get_nested_value(student, field_path)
                        return str(value) if value is not None else f"{{{{{marker}}}}}"
                    
                    # Marcadores directos del estudiante
                    if marker in student:
                        return str(student[marker])
                    
                    # Si no se encuentra el marcador, mantenerlo sin cambios
                    return f"{{{{{marker}}}}}"
                
                return cls.marker_pattern.sub(replace_marker, text)
            
            # Función auxiliar para procesar recursivamente estructuras de datos
            def process_data_structure(data):
                if isinstance(data, str):
                    return replace_markers_in_text(data)
                elif isinstance(data, dict):
                    return {key: process_data_structure(value) for key, value in data.items()}
                elif isinstance(data, list):
                    return [process_data_structure(item) for item in data]
                else:
                    return data
            
            # Aplicar reemplazo a todos los campos del contenido
            for key, value in personalized_content.items():
                personalized_content[key] = process_data_structure(value)
            
            return personalized_content
            
        except Exception as e:
            logging.error(f"Error aplicando marcadores de personalización: {str(e)}")
            return content  # Retornar contenido original en caso de error
    
    @classmethod
    def _get_nested_value(cls, data: Dict, field_path: str):
        """
        Obtiene un valor anidado usando notación de punto (ej: 'profile.name')
        """
        try:
            keys = field_path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except Exception:
            return None
