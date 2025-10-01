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
                 slide_template: Optional[str] = None,  # Prompt para generar plantilla de diapositivas
                 # Nuevos campos para sistema de plantillas
                 render_engine: str = "legacy",  # legacy | html_template
                 instance_id: Optional[str] = None,  # Referencia a TemplateInstance
                 template_id: Optional[str] = None,  # Referencia directa a Template
                 template_version: Optional[str] = None,  # Versión de plantilla usada
                 learning_mix: Optional[Dict] = None,  # Mix VARK para este contenido
                 # Nuevos campos para Fase 1 y 2
                 order: Optional[int] = None,  # Orden secuencial para diapositivas
                 parent_content_id: Optional[str] = None,  # Vinculación con diapositiva padre
                 status: str = "draft",
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 # Nuevos campos para soporte de diapositivas HTML - Fase 2A
                 content_html: Optional[str] = None,
                 narrative_text: Optional[str] = None,
                 full_text: Optional[str] = None,
                 # Campo para snapshot de plantilla de estilos
                 template_snapshot: Optional[Dict] = None,
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
        self.slide_template = slide_template or ""
        # Nuevos campos de plantillas
        self.render_engine = render_engine
        self.instance_id = ObjectId(instance_id) if instance_id else None
        self.template_id = ObjectId(template_id) if template_id else None
        self.template_version = template_version
        self.learning_mix = learning_mix or {}
        # Nuevos campos para Fase 1 y 2
        self.order = order
        self.parent_content_id = ObjectId(parent_content_id) if parent_content_id else None
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

        # Nuevos campos para diapositivas HTML (Fase 2A)
        self.content_html = content_html
        self.narrative_text = narrative_text
        self.full_text = full_text
        self.template_snapshot = template_snapshot

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
            "slide_template": self.slide_template,
            "render_engine": self.render_engine,
            "learning_mix": self.learning_mix,
            "order": self.order,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Campos nuevos para diapositivas HTML
            "content_html": self.content_html,
            "narrative_text": self.narrative_text,
            "full_text": self.full_text,
            "template_snapshot": self.template_snapshot,
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
        return data

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
        self.recorded_at = recorded_at or datetime.now()

    def to_dict(self) -> dict:
        data = {
            "_id": self._id,
            "student_id": self.student_id,
            "score": self.score,
            "feedback": self.feedback,
            "metrics": self.metrics,
            "session_type": self.session_type,
            "recorded_at": self.recorded_at,
        }
        if self.content_id:
            data["content_id"] = self.content_id
        if self.virtual_content_id:
            data["virtual_content_id"] = self.virtual_content_id
        if self.evaluation_id:
            data["evaluation_id"] = self.evaluation_id
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