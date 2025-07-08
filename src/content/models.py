import logging
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Union
from src.shared.constants import STATUS

class ContentType:
    """
    Catálogo de tipos de contenido disponibles en el sistema.
    Define los diferentes formatos en que se puede presentar el material educativo.
    """
    def __init__(self,
                 code: str,  # Identificador único (text, feynman, diagram, etc.)
                 name: str,
                 description: str,
                 compatible_methodologies: List[str] = None,
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
                 compatible_content_types: List[str] = None,
                 cognitive_profile_match: Dict = None,
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
                 learning_methodologies: List[str] = None,
                 adaptation_options: Dict = None,
                 resources: List[str] = None,
                 web_resources: List[Dict] = None,
                 generation_prompt: str = None,
                 ai_credits: bool = True,
                 personalization_markers: Dict = None,
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
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

        if kwargs:
            logging.warning(f"TopicContent received unexpected arguments, which were ignored: {list(kwargs.keys())}")
        
    def to_dict(self) -> dict:
        return {
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
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

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
                 interaction_history: List[Dict] = None,
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
    """
    Almacena el resultado de la interacción de un estudiante con una pieza de contenido.
    Unifica los resultados de quizzes, juegos, simulaciones, etc.
    """
    def __init__(self,
                 content_id: str,
                 student_id: str,
                 score: float,
                 feedback: Optional[str] = None,
                 metrics: Optional[Dict] = None,
                 session_type: str = "content_interaction",
                 _id: Optional[ObjectId] = None,
                 recorded_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.content_id = ObjectId(content_id)
        self.student_id = ObjectId(student_id)
        self.score = score
        self.feedback = feedback
        self.metrics = metrics or {} # e.g., time_spent, attempts, etc.
        self.session_type = session_type
        self.recorded_at = recorded_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "content_id": self.content_id,
            "student_id": self.student_id,
            "score": self.score,
            "feedback": self.feedback,
            "metrics": self.metrics,
            "session_type": self.session_type,
            "recorded_at": self.recorded_at,
        }


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
    SLIDES = "slides"
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
    GAME = "game"
    SIMULATION = "simulation"
    VIRTUAL_LAB = "virtual_lab"
    AR = "ar"
    MINI_GAME = "mini_game"
    INTERACTIVE_EXERCISE = "interactive_exercise"
    CHALLENGE = "challenge"
    FLASHCARDS = "flashcards"
    
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
        return {
            "theoretical": [cls.TEXT, cls.FEYNMAN, cls.STORY, cls.SUMMARY, cls.GLOSSARY, 
                          cls.GUIDED_QUESTIONS, cls.EXAMPLES, cls.DOCUMENTS, cls.LINK],
            "visual": [cls.DIAGRAM, cls.INFOGRAPHIC, cls.MINDMAP, cls.TIMELINE, 
                     cls.ILLUSTRATION, cls.CHART, cls.PICTOGRAM, cls.IMAGE, cls.SLIDES],
            "multimedia": [cls.VIDEO, cls.AUDIO, cls.MUSIC, cls.ANIMATION, 
                         cls.SCREENCAST, cls.NARRATED_PRESENTATION],
            "interactive": [cls.GAME, cls.SIMULATION, cls.VIRTUAL_LAB, cls.AR, 
                          cls.MINI_GAME, cls.INTERACTIVE_EXERCISE, cls.CHALLENGE, cls.FLASHCARDS],
            "evaluation": [cls.QUIZ, cls.EXAM, cls.PROJECT, cls.RUBRIC, 
                         cls.FORMATIVE_TEST, cls.PEER_REVIEW, cls.PORTFOLIO]
        }
        
    @classmethod
    def get_all_types(cls):
        types = []
        for category in cls.get_categories().values():
            types.extend(category)
        return types

class LearningMethodologyTypes:
    # Estilos de aprendizaje sensoriales
    VISUAL = "visual"
    AUDITORY = "auditory"
    READ_WRITE = "read_write"
    KINESTHETIC = "kinesthetic"
    
    # Enfoques pedagógicos
    GAMIFICATION = "gamification"
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
