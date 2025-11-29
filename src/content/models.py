import logging
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Union
from src.shared.constants import STATUS
from pydantic import BaseModel, Field

class ContentType:
    """
    Catálogo de tipos de contenido disponibles en el sistema.
    Define los diferentes formatos en que se puede presentar el material educativo.
    """
    def __init__(self,
                 code: str,  # Identificador único (text, feynman, diagram, etc.)
                 name: str,
                 description: str,
                 compatible_methodologies: Optional[List[str]] = None,
                 status: str = "active"):
        self.code = code
        self.name = name
        self.description = description
        self.compatible_methodologies = compatible_methodologies or []
        self.created_at = datetime.now()
        self.status = status
        
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "compatible_methodologies": self.compatible_methodologies,
            "created_at": self.created_at,
            "status": self.status
        }

class LearningMethodology:
    """
    Define metodologías de aprendizaje y su compatibilidad con diferentes perfiles cognitivos.
    """
    def __init__(self,
                 code: str,
                 name: str,
                 description: str,
                 compatible_content_types: Optional[List[str]] = None,
                 cognitive_profile_match: Optional[Dict] = None,
                 status: str = "active"):
        self.code = code
        self.name = name
        self.description = description
        self.compatible_content_types = compatible_content_types or []
        self.cognitive_profile_match = cognitive_profile_match or {}
        self.created_at = datetime.now()
        self.status = status
        
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "compatible_content_types": self.compatible_content_types,
            "cognitive_profile_match": self.cognitive_profile_match,
            "created_at": self.created_at,
            "status": self.status
        }

class TopicContent:
    """
    Almacena un tipo específico de contenido para un tema.
    Permite tener múltiples representaciones del mismo tema.

    Note sobre el campo legacy_raw en content:
    Para content_type 'slide' y 'quiz', si el campo original 'content' no era un dict,
    se preserva el valor original en content['legacy_raw']. Este campo temporal
    mantiene datos históricos que fueron convertidos durante la migración.

    Plan de limpieza:
    - legacy_raw debe ser eliminado después de verificar que los datos han sido migrados correctamente
    - Se recomienda implementar un script de limpieza que ejecute después de un período de prueba
    - El script debe verificar que no hay referencias activas a legacy_raw antes de eliminarlo
    """
    def __init__(self,
                 topic_id: str,
                 content: Union[str, Dict],  # Puede ser texto o estructura compleja
                 content_type: str,  # Código del tipo de contenido (text, feynman, diagram, etc.)
                 interactive_data: Optional[Dict] = None,  # Para quizzes, simulaciones, etc.
                 learning_methodologies: Optional[List[str]] = None,
                 adaptation_options: Optional[Dict] = None,
                 resources: Optional[List[str]] = None,
                 web_resources: Optional[List[Dict]] = None,
                 generation_prompt: Optional[str] = None,
                 ai_credits: bool = True,
                 personalization_markers: Optional[Dict] = None,
                 # Nuevos campos para sistema de plantillas
                 render_engine: str = "legacy",  # legacy | html_template
                 instance_id: Optional[str] = None,  # Referencia a TemplateInstance
                 template_id: Optional[str] = None,  # Referencia directa a Template
                 template_version: Optional[str] = None,  # Versión de plantilla usada
                 learning_mix: Optional[Dict] = None,  # Mix VARK para este contenido
                 baseline_mix: Optional[Dict] = None,
                 # Nuevos campos para Fase 1 y 2
                 order: Optional[int] = None,  # Orden secuencial para diapositivas
                 parent_content_id: Optional[str] = None,  # Vinculación con diapositiva padre
                 status: str = "draft",
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 **kwargs):
        self._id = _id or ObjectId()
        self.topic_id = ObjectId(topic_id)
        self.content = content
        self.content_type = content_type
        self.interactive_data = interactive_data or {}
        self.learning_methodologies = learning_methodologies or []
        self.adaptation_options = adaptation_options or {}
        self.resources = resources or []
        self.web_resources = web_resources or []
        self.generation_prompt = generation_prompt
        self.ai_credits = ai_credits
        self.personalization_markers = personalization_markers or {}
        # Nuevos campos de plantillas
        self.render_engine = render_engine
        self.instance_id = ObjectId(instance_id) if instance_id else None
        self.template_id = ObjectId(template_id) if template_id else None
        self.template_version = template_version
        self.learning_mix = learning_mix.copy() if isinstance(learning_mix, dict) else {}
        processed_baseline_mix = baseline_mix if isinstance(baseline_mix, dict) else None
        if processed_baseline_mix is None and self.learning_mix:
            processed_baseline_mix = self.learning_mix
        self.baseline_mix = processed_baseline_mix.copy() if isinstance(processed_baseline_mix, dict) else {}
        # Nuevos campos para Fase 1 y 2
        self.order = order
        self.parent_content_id = ObjectId(parent_content_id) if parent_content_id else None
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

        # Manejo de campos específicos de slides y quizzes
        if content_type in ['slide', 'quiz']:
            if not isinstance(self.content, dict):
                if self.content is None or (isinstance(self.content, str) and not self.content.strip()):
                    logging.warning(f"TopicContent {self._id} has empty/None content for type {content_type}")
                # Preservar valor original como legacy_raw antes de convertir a dict
                original_content = self.content
                self.content = {
                    'legacy_raw': original_content
                }
                logging.info(f"TopicContent {self._id}: Converting content to dict for {content_type}, preserving original as legacy_raw")
            if 'full_text' in kwargs:
                if 'full_text' not in self.content:
                    self.content['full_text'] = kwargs.pop('full_text')
                else:
                    kwargs.pop('full_text')
            if 'content_html' in kwargs:
                if 'content_html' not in self.content:
                    self.content['content_html'] = kwargs.pop('content_html')
                else:
                    kwargs.pop('content_html')
            if 'narrative_text' in kwargs:
                if 'narrative_text' not in self.content:
                    self.content['narrative_text'] = kwargs.pop('narrative_text')
                else:
                    kwargs.pop('narrative_text')
                if 'slide_plan' in kwargs:
                    if 'slide_plan' not in self.content:
                        self.content['slide_plan'] = kwargs.pop('slide_plan')
                    else:
                        kwargs.pop('slide_plan')

        if isinstance(self.content, dict):
            if self.baseline_mix:
                self.content.setdefault('baseline_mix', self.baseline_mix.copy())
            elif isinstance(self.content.get('baseline_mix'), dict):
                self.baseline_mix = self.content['baseline_mix']


        if kwargs:
            logging.warning(f"TopicContent received unexpected arguments, which were ignored: {list(kwargs.keys())}")
        
    def to_dict(self) -> dict:
        data = {
            "_id": self._id,
            "topic_id": self.topic_id,
            "content": self.content,
            "content_type": self.content_type,
            "interactive_data": self.interactive_data,
            "learning_methodologies": self.learning_methodologies,
            "adaptation_options": self.adaptation_options,
            "resources": self.resources,
            "web_resources": self.web_resources,
            "generation_prompt": self.generation_prompt,
            "ai_credits": self.ai_credits,
            "personalization_markers": self.personalization_markers,
            "render_engine": self.render_engine,
            "learning_mix": self.learning_mix,
            "baseline_mix": self.baseline_mix,
            "order": self.order,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        # Campos opcionales de plantillas
        if self.instance_id:
            data["instance_id"] = self.instance_id
        if self.template_id:
            data["template_id"] = self.template_id
        if self.template_version:
            data["template_version"] = self.template_version
        if self.parent_content_id:
            data["parent_content_id"] = self.parent_content_id

        # Fix content field duplication: ensure content-specific fields are only inside content object
        if self.content_type in ['slide', 'quiz'] and isinstance(self.content, dict):
            # Remove any root-level copies of these fields to prevent duplication
            content_specific_fields = ['content_html', 'narrative_text', 'full_text', 'slide_plan']
            # Only iterate if any of the content-specific fields exist at root level
            if any(field in data for field in content_specific_fields):
                for field in content_specific_fields:
                    if field in data and field in self.content:
                        # If field exists both at root and in content, remove the root-level copy
                        del data[field]

        return data

    def _get_slide_field(self, field_name):
        """
        Helper method for backward compatibility during transition.
        Looks for the field first in self.content[field_name], then at root level.
        """
        if isinstance(self.content, dict) and field_name in self.content:
            return self.content[field_name]
        return getattr(self, field_name, None)

class VirtualTopicContent:
    """
    Representa una instancia de contenido de un tema, adaptada o generada para un estudiante específico.
    """
    def __init__(self,
                 virtual_topic_id: str,
                 original_content_id: str,
                 student_id: str,
                 content_type: str,
                 adapted_content: Optional[Dict] = None,
                 status: str = "not_started", # not_started, in_progress, completed
                 interaction_history: Optional[List[Dict]] = None,
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.virtual_topic_id = ObjectId(virtual_topic_id)
        self.original_content_id = ObjectId(original_content_id)
        self.student_id = ObjectId(student_id)
        self.content_type = content_type
        self.adapted_content = adapted_content or {}
        self.status = status
        self.interaction_history = interaction_history or []
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "virtual_topic_id": self.virtual_topic_id,
            "original_content_id": self.original_content_id,
            "student_id": self.student_id,
            "content_type": self.content_type,
            "adapted_content": self.adapted_content,
            "status": self.status,
            "interaction_history": self.interaction_history,
            "created_at": self.created_at,
        }

class ContentResult:
    """Stores the outcome of a student's interaction with content."""

    # Tipos de normalizacion para tracking
    NORMALIZATION_SLIDE_VIEW = "slide_view"           # Slide normal: binario (visto/no visto)
    NORMALIZATION_INTERACTIVE = "interactive"         # Slide interactiva: score del artefacto
    NORMALIZATION_QUIZ = "quiz"                       # Quiz: score de respuestas correctas
    NORMALIZATION_DEFAULT = "default"                 # Fallback generico

    # Score minimo requerido para desbloquear avance por tipo
    MINIMUM_SCORES = {
        "quiz": 0.6,              # 60% para quizzes
        "interactive": 0.0,       # Solo completar para interactivos
        "slide_view": 0.0,        # Sin minimo para slides normales
        "default": 0.0,
    }

    # Pesos para calculo de score ponderado del tema
    CONTENT_WEIGHTS = {
        "quiz": 0.6,              # 60% del peso total
        "interactive": 0.3,       # 30% del peso total
        "slide_view": 0.1,        # 10% del peso total
        "default": 0.1,
    }

    def __init__(
        self,
        student_id: str,
        score: float,
        content_id: Optional[str] = None,
        virtual_content_id: Optional[str] = None,
        evaluation_id: Optional[str] = None,
        feedback: Optional[str] = None,
        metrics: Optional[Dict] = None,
        session_type: str = "content_interaction",
        topic_id: Optional[str] = None,
        content_type: Optional[str] = None,
        variant_label: Optional[str] = None,
        template_instance_id: Optional[str] = None,
        template_usage_id: Optional[str] = None,
        baseline_mix: Optional[Dict] = None,
        prediction_id: Optional[str] = None,
        rl_context: Optional[Dict] = None,
        session_data: Optional[Dict] = None,
        learning_metrics: Optional[Dict] = None,
        normalization_type: Optional[str] = None,
        is_interactive: Optional[bool] = None,
        minimum_score_required: Optional[float] = None,
        _id: Optional[ObjectId] = None,
        recorded_at: Optional[datetime] = None,
    ):
        if not content_id and not virtual_content_id:
            raise ValueError("content_id or virtual_content_id is required")

        self._id = _id or ObjectId()
        self.content_id = ObjectId(content_id) if content_id else None
        self.virtual_content_id = ObjectId(virtual_content_id) if virtual_content_id else None
        self.evaluation_id = ObjectId(evaluation_id) if evaluation_id else None
        self.student_id = ObjectId(student_id)
        self.score = score
        self.feedback = feedback
        self.metrics = metrics or {}
        self.session_type = session_type
        self.topic_id = ObjectId(topic_id) if topic_id else None
        self.content_type = content_type
        self.variant_label = variant_label
        self.template_instance_id = ObjectId(template_instance_id) if template_instance_id else None
        self.template_usage_id = ObjectId(template_usage_id) if template_usage_id else None
        self.baseline_mix = baseline_mix or {}
        self.prediction_id = prediction_id
        self.rl_context = rl_context or {}
        self.session_data = session_data or {}
        self.learning_metrics = learning_metrics or {}
        self.normalization_type = normalization_type or self.NORMALIZATION_DEFAULT
        self.is_interactive = is_interactive
        self.minimum_score_required = minimum_score_required
        self.recorded_at = recorded_at or datetime.now()

    def to_dict(self) -> dict:
        data = {
            "_id": self._id,
            "student_id": self.student_id,
            "score": self.score,
            "feedback": self.feedback,
            "metrics": self.metrics,
            "session_type": self.session_type,
            "baseline_mix": self.baseline_mix,
            "rl_context": self.rl_context,
            "session_data": self.session_data,
            "learning_metrics": self.learning_metrics,
            "recorded_at": self.recorded_at,
        }
        if self.content_id:
            data["content_id"] = self.content_id
        if self.virtual_content_id:
            data["virtual_content_id"] = self.virtual_content_id
        if self.evaluation_id:
            data["evaluation_id"] = self.evaluation_id
        if self.topic_id:
            data["topic_id"] = self.topic_id
        if self.content_type:
            data["content_type"] = self.content_type
        if self.variant_label:
            data["variant_label"] = self.variant_label
        if self.template_instance_id:
            data["template_instance_id"] = self.template_instance_id
        if self.template_usage_id:
            data["template_usage_id"] = self.template_usage_id
        if self.prediction_id:
            data["prediction_id"] = self.prediction_id
        if self.normalization_type:
            data["normalization_type"] = self.normalization_type
        if self.is_interactive is not None:
            data["is_interactive"] = self.is_interactive
        if self.minimum_score_required is not None:
            data["minimum_score_required"] = self.minimum_score_required
        return data


class ContentGenerationTask(BaseModel):
    """
    Representa una tarea de generación de contenido en lote, que puede incluir
    múltiples tipos de contenido para un mismo tema.
    """
    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    topic_id: ObjectId
    user_id: ObjectId
    requested_content_types: List[str]
    
    status: str = "pending"  # pending, processing, completed, partially_completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Tracking de sub-tareas
    subtasks: List[Dict] = []
    # Ejemplo de subtask:
    # { "content_type": "slide", "status": "completed", "content_id": ObjectId(...) }
    # { "content_type": "diagram", "status": "processing" }

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    def to_db(self) -> Dict:
        """Convierte el modelo Pydantic a un diccionario para MongoDB."""
        data = self.model_dump(by_alias=True)
        return data

class ContentTypes:
    # Contenido Teórico
    TEXT = "text"
    FEYNMAN = "feynman"
    STORY = "story"
    SUMMARY = "summary"
    GLOSSARY = "glossary"
    GUIDED_QUESTIONS = "guided_questions"
    EXAMPLES = "examples"
    DOCUMENTS = "documents"
    SLIDE = "slide"  # Diapositiva individual
    IMAGE = "image"
    LINK = "link"
    
    # Contenido Visual
    DIAGRAM = "diagram"
    INFOGRAPHIC = "infographic"
    MINDMAP = "mindmap"
    TIMELINE = "timeline"
    ILLUSTRATION = "illustration"
    CHART = "chart"
    PICTOGRAM = "pictogram"
    
    # Contenido Multimedia
    VIDEO = "video"
    AUDIO = "audio"
    MUSIC = "music"
    ANIMATION = "animation"
    SCREENCAST = "screencast"
    NARRATED_PRESENTATION = "narrated_presentation"
    
    # Contenido Interactivo
    GAME = "game"  # DEPRECATED: Usar templates interactivos (ver DeprecatedContentTypes)
    SIMULATION = "simulation"  # DEPRECATED: Usar templates interactivos (ver DeprecatedContentTypes)
    VIRTUAL_LAB = "virtual_lab"
    AR = "ar"
    MINI_GAME = "mini_game"
    INTERACTIVE_EXERCISE = "interactive_exercise"
    COMPLETION_EXERCISE = "completion_exercise"
    MATH_EXERCISE = "math_exercise"
    CHALLENGE = "challenge"
    FLASHCARDS = "flashcards"
    GEMINI_LIVE = "gemini_live"
    
    # Contenido de Evaluación
    QUIZ = "quiz"
    EXAM = "exam"
    PROJECT = "project"
    RUBRIC = "rubric"
    FORMATIVE_TEST = "formative_test"
    PEER_REVIEW = "peer_review"
    PORTFOLIO = "portfolio"

    @classmethod
    def get_categories(cls):
        """
        Retorna las categorías de tipos de contenido. Los tipos marcados como deprecated
        (p.ej. game y simulation) se agrupan bajo la categoría 'deprecated' para
        facilitar su visibilidad y control por parte de servicios y endpoints.
        """
        categories = {
            "theoretical": [cls.TEXT, cls.FEYNMAN, cls.STORY, cls.SUMMARY, cls.GLOSSARY, 
                          cls.GUIDED_QUESTIONS, cls.EXAMPLES, cls.DOCUMENTS, cls.LINK],
            "visual": [cls.DIAGRAM, cls.INFOGRAPHIC, cls.MINDMAP, cls.TIMELINE, 
                     cls.ILLUSTRATION, cls.CHART, cls.PICTOGRAM, cls.IMAGE, cls.SLIDE],
            "multimedia": [cls.VIDEO, cls.AUDIO, cls.MUSIC, cls.ANIMATION, 
                         cls.SCREENCAST, cls.NARRATED_PRESENTATION],
            "interactive": [cls.VIRTUAL_LAB, cls.AR, cls.MINI_GAME, cls.INTERACTIVE_EXERCISE, 
                          cls.COMPLETION_EXERCISE, cls.MATH_EXERCISE, cls.CHALLENGE, cls.FLASHCARDS, cls.GEMINI_LIVE],
            "evaluation": [cls.QUIZ, cls.EXAM, cls.PROJECT, cls.RUBRIC, 
                         cls.FORMATIVE_TEST, cls.PEER_REVIEW, cls.PORTFOLIO]
        }
        # Agregar categoría específica para tipos deprecated para que los servicios puedan manejarla de forma separada
        deprecated = cls.get_deprecated_types()
        if deprecated:
            categories["deprecated"] = deprecated
        return categories
        
    @classmethod
    def get_all_types(cls):
        types = []
        for category in cls.get_categories().values():
            types.extend(category)
        return types

    @classmethod
    def get_deprecated_types(cls) -> List[str]:
        """
        Retorna la lista de tipos de contenido marcados como deprecated.
        Esto facilita la validación en servicios y la migración de contenidos existentes.
        """
        # Actualmente los tipos deprecated se mantienen para compatibilidad pero no deben crearse nuevos.
        return [cls.GAME, cls.SIMULATION]

class DeprecatedContentTypes:
    """
    Clase que contiene metadatos y mensajes de migración para tipos de contenido deprecated.
    Proporciona información que puede ser usada por servicios y endpoints para mostrar
    mensajes coherentes al usuario y sugerir reemplazos.
    """
    # Estructura interna: type_code -> metadata
    _DATA = {
        ContentTypes.GAME: {
            "type": ContentTypes.GAME,
            "replacement": "interactive_template",  # Recomendación genérica de plantilla interactiva
            "deprecated_at": datetime(2024, 7, 1),
            "sunset_date": datetime(2025, 12, 31),
            "message": "El tipo 'game' está en desuso. Se recomienda migrar a templates interactivos "
                       "o instancias de plantillas (interactive_template). Para casos excepcionales, "
                       "use los endpoints legacy con el flag 'force_legacy=true' (administradores)."
        },
        ContentTypes.SIMULATION: {
            "type": ContentTypes.SIMULATION,
            "replacement": "interactive_simulation_template",
            "deprecated_at": datetime(2024, 7, 1),
            "sunset_date": datetime(2025, 12, 31),
            "message": "El tipo 'simulation' está en desuso. Se recomienda migrar a plantillas de simulación "
                       "o instancias de Template. Para casos excepcionales, use los endpoints legacy con 'force_legacy=true'."
        }
    }

    @classmethod
    def list_all(cls) -> List[Dict]:
        """Retorna lista de metadatos para todos los tipos deprecated."""
        return list(cls._DATA.values())

    @classmethod
    def info_for(cls, type_code: str) -> Optional[Dict]:
        """Retorna metadatos para un tipo deprecated específico, o None si no está en deprecados."""
        return cls._DATA.get(type_code)

    @classmethod
    def is_deprecated(cls, type_code: str) -> bool:
        """Indica si un tipo de contenido está marcado como deprecated."""
        return type_code in cls._DATA

class LearningMethodologyTypes:
    # Estilos de aprendizaje sensoriales
    VISUAL = "visual"
    AUDITORY = "auditory"
    READ_WRITE = "read_write"
    KINESTHETIC = "kinesthetic"  # DEPRECATED MAPPING: ahora se mapea a templates interactivos / kinesthetic templates
    
    # Enfoques pedagógicos
    GAMIFICATION = "gamification"  # DEPRECATED MAPPING: mapear a templates interactivos (p. ej. challenge/points templates)
    PROBLEM_BASED = "problem_based"
    POMODORO = "pomodoro"
    CONCEPT_MAPPING = "concept_mapping"
    COLLABORATIVE = "collaborative"
    PERSONALIZED = "personalized"
    MICROLEARNING = "microlearning"
    DISCOVERY = "discovery"
    PROJECT_BASED = "project_based"
    
    # Técnicas de memoria y retención
    SPACED_REPETITION = "spaced_repetition"
    RETRIEVAL_PRACTICE = "retrieval_practice"
    FEYNMAN = "feynman"
    MIND_MAP = "mind_map"
    SOCRATIC = "socratic"

    # Adaptaciones específicas
    ADHD_ADAPTED = "adhd_adapted"
    DYSLEXIA_ADAPTED = "dyslexia_adapted"
    AUTISM_ADAPTED = "autism_adapted"
    
    @classmethod
    def get_categories(cls):
        return {
            "sensory": [cls.VISUAL, cls.AUDITORY, cls.READ_WRITE, cls.KINESTHETIC],
            "pedagogical": [cls.GAMIFICATION, cls.PROBLEM_BASED, cls.POMODORO, 
                          cls.CONCEPT_MAPPING, cls.COLLABORATIVE, cls.PERSONALIZED,
                          cls.MICROLEARNING, cls.DISCOVERY, cls.PROJECT_BASED],
            "memory": [cls.SPACED_REPETITION, cls.RETRIEVAL_PRACTICE, cls.FEYNMAN,
                     cls.MIND_MAP, cls.SOCRATIC],
            "adaptations": [cls.ADHD_ADAPTED, cls.DYSLEXIA_ADAPTED, cls.AUTISM_ADAPTED]
        }

    @classmethod
    def get_template_compatible_methodologies(cls) -> List[str]:
        """
        Retorna las metodologías que son compatibles o recomendadas para ser representadas
        mediante templates interactivos (templates HTML/JS, instancias de Template, etc.).
        Incluye metodologías que anteriormente se mapeaban principalmente a games/simulations.
        """
        # Incluir kinesthetic y gamification (que antes se apoyaban en games/simulations),
        # además de enfoques colaborativos y project_based que también se benefician de templates interactivos.
        return [
            cls.KINESTHETIC,
            cls.GAMIFICATION,
            cls.COLLABORATIVE,
            cls.PROJECT_BASED,
            cls.DISCOVERY
        ]

    @classmethod
    def map_kinesthetic_to_templates(cls) -> Dict[str, List[str]]:
        """
        Provee un mapeo explícito de metodologías kinestésicas/pedagógicas a tipos de templates
        recomendados. Los valores son identificadores de plantillas recomendadas que los
        servicios de creación y migración pueden usar como sugerencia.
        """
        # Los nombres de template son recomendaciones genéricas; los servicios deben mapear a IDs concretos.
        return {
            cls.KINESTHETIC: [
                "kinesthetic_interactive_template",    # Plantilla para actividades físicas/hands-on
                "virtual_lab_template",                # Plantilla que simula laboratorios / interacción directa
                "interactive_exercise_template"        # Plantilla genérica de ejercicios interactivos
            ],
            cls.GAMIFICATION: [
                "gamified_challenge_template",         # Plantilla con sistema de puntos/retos
                "leaderboard_template",                # Plantilla con ranking/insignias
                "interactive_exercise_template"
            ],
            cls.COLLABORATIVE: [
                "collaborative_workspace_template",
                "shared_project_template"
            ],
            cls.PROJECT_BASED: [
                "project_based_template",
                "portfolio_template"
            ]
        }
    
    @classmethod
    def get_default_content_compatibility(cls) -> Dict[str, List[str]]:
        """
        Retorna el mapeo de compatibilidad por defecto entre metodologías de aprendizaje
        y tipos de contenido recomendados.
        
        Returns:
            Dict: Mapeo de metodología a lista de tipos de contenido compatibles
        """
        return {
            cls.VISUAL: [ContentTypes.DIAGRAM, ContentTypes.INFOGRAPHIC, ContentTypes.MINDMAP, 
                        ContentTypes.TIMELINE, ContentTypes.ILLUSTRATION, ContentTypes.CHART, 
                        ContentTypes.IMAGE, ContentTypes.VIDEO, ContentTypes.ANIMATION],
            
            cls.AUDITORY: [ContentTypes.AUDIO, ContentTypes.MUSIC, ContentTypes.VIDEO, 
                          ContentTypes.NARRATED_PRESENTATION, ContentTypes.SCREENCAST],
            
            cls.READ_WRITE: [ContentTypes.TEXT, ContentTypes.SUMMARY, ContentTypes.GLOSSARY, 
                            ContentTypes.EXAMPLES, ContentTypes.DOCUMENTS, ContentTypes.SLIDE,
                            ContentTypes.GUIDED_QUESTIONS],
            
            cls.KINESTHETIC: [ContentTypes.INTERACTIVE_EXERCISE, ContentTypes.COMPLETION_EXERCISE,
                             ContentTypes.MATH_EXERCISE, ContentTypes.CHALLENGE, ContentTypes.FLASHCARDS,
                             ContentTypes.VIRTUAL_LAB],
            
            cls.GAMIFICATION: [ContentTypes.CHALLENGE, ContentTypes.INTERACTIVE_EXERCISE,
                              ContentTypes.FLASHCARDS, ContentTypes.QUIZ],
            
            cls.PROBLEM_BASED: [ContentTypes.INTERACTIVE_EXERCISE, ContentTypes.EXAMPLES,
                               ContentTypes.GUIDED_QUESTIONS, ContentTypes.PROJECT],
            
            cls.SPACED_REPETITION: [ContentTypes.FLASHCARDS, ContentTypes.QUIZ,
                                   ContentTypes.FORMATIVE_TEST],
            
            cls.RETRIEVAL_PRACTICE: [ContentTypes.QUIZ, ContentTypes.FORMATIVE_TEST,
                                    ContentTypes.FLASHCARDS],
            
            cls.FEYNMAN: [ContentTypes.TEXT, ContentTypes.SUMMARY, ContentTypes.EXAMPLES,
                         ContentTypes.GUIDED_QUESTIONS],
            
            cls.MIND_MAP: [ContentTypes.MINDMAP, ContentTypes.DIAGRAM],
            
            cls.SOCRATIC: [ContentTypes.GUIDED_QUESTIONS, ContentTypes.INTERACTIVE_EXERCISE,
                          ContentTypes.PEER_REVIEW],
            
            cls.ADHD_ADAPTED: [ContentTypes.SLIDE, ContentTypes.VIDEO, ContentTypes.INTERACTIVE_EXERCISE,
                              ContentTypes.CHALLENGE, ContentTypes.FLASHCARDS],
            
            cls.DYSLEXIA_ADAPTED: [ContentTypes.AUDIO, ContentTypes.VIDEO, ContentTypes.DIAGRAM,
                                  ContentTypes.INTERACTIVE_EXERCISE],
            
            cls.AUTISM_ADAPTED: [ContentTypes.SLIDE, ContentTypes.DIAGRAM, ContentTypes.CHALLENGE]
        }
