from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class StudyPlanPerSubject:
    def __init__(self,
                 version: str,
                 author_id: str,
                 name: str,
                 description: Optional[str] = None,
                 status: str = "draft",
                 subject_id: Optional[str] = None,
                 approval_date: Optional[datetime] = None):
        self.version = version
        self.author_id = ObjectId(author_id)
        self.name = name
        self.description = description
        self.status = status
        self.subject_id = ObjectId(subject_id) if subject_id else None
        self.approval_date = approval_date
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "author_id": self.author_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "subject_id": self.subject_id,
            "approval_date": self.approval_date,
            "created_at": self.created_at
        }

class StudyPlanAssignment:
    def __init__(self,
                 study_plan_id: str,
                 class_id: str,
                 subperiod_id: str,
                 assigned_by: str,
                 is_active: bool = True):
        self.study_plan_id = ObjectId(study_plan_id)
        self.class_id = ObjectId(class_id)
        self.subperiod_id = ObjectId(subperiod_id)
        self.assigned_by = ObjectId(assigned_by)
        self.is_active = is_active
        self.assigned_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "study_plan_id": self.study_plan_id,
            "class_id": self.class_id,
            "subperiod_id": self.subperiod_id,
            "assigned_by": self.assigned_by,
            "is_active": self.is_active,
            "assigned_at": self.assigned_at
        }

class Module:
    def __init__(self,
                 study_plan_id: str,
                 name: str,
                 learning_outcomes: List[str],
                 evaluation_rubric: Dict[str, any]):
        self.study_plan_id = ObjectId(study_plan_id)
        self.name = name
        self.learning_outcomes = learning_outcomes
        self.evaluation_rubric = evaluation_rubric
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "study_plan_id": self.study_plan_id,
            "name": self.name,
            "learning_outcomes": self.learning_outcomes,
            "evaluation_rubric": self.evaluation_rubric,
            "created_at": self.created_at
        }

class Topic:
    def __init__(self,
                 module_id: str,
                 name: str,
                 difficulty: str,
                 theory_content: str = ""):
        self.module_id = ObjectId(module_id)
        self.name = name
        self.difficulty = difficulty
        self.theory_content = theory_content
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "name": self.name,
            "difficulty": self.difficulty,
            "theory_content": self.theory_content,
            "created_at": self.created_at
        }

class Evaluation:
    def __init__(self,
                 module_id: str,
                 title: str,
                 description: str,
                 weight: float,
                 criteria: List[Dict],
                 due_date: datetime):
        self.module_id = ObjectId(module_id)
        self.title = title
        self.description = description
        self.weight = weight
        self.criteria = criteria
        self.due_date = due_date
        self.created_at = datetime.now()
        self.status = "pending"

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "title": self.title,
            "description": self.description,
            "weight": self.weight,
            "criteria": self.criteria,
            "due_date": self.due_date,
            "created_at": self.created_at,
            "status": self.status
        }

class EvaluationResult:
    def __init__(self,
                 evaluation_id: str,
                 student_id: str,
                 score: float,
                 feedback: str = ""):
        self.evaluation_id = ObjectId(evaluation_id)
        self.student_id = ObjectId(student_id)
        self.score = score
        self.feedback = feedback
        self.submitted_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "student_id": self.student_id,
            "score": self.score,
            "feedback": self.feedback,
            "submitted_at": self.submitted_at
        }

# Nuevos modelos para soportar múltiples tipos de contenido

class ContentTypeDefinition:
    """
    Catálogo de tipos de contenido disponibles en el sistema.
    Define los diferentes formatos en que se puede presentar el material educativo.
    """
    def __init__(self,
                 code: str,  # Identificador único (text, feynman, diagram, etc.)
                 name: str,
                 category: str,  # teórico, visual, multimedia, interactivo, evaluación
                 description: str,
                 compatible_methodologies: List[str] = None):
        self.code = code
        self.name = name
        self.category = category
        self.description = description
        self.compatible_methodologies = compatible_methodologies or []
        self.created_at = datetime.now()
        self.status = "active"
        
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category,
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
                 cognitive_profile_match: Dict = None):
        self.code = code
        self.name = name
        self.description = description
        self.compatible_content_types = compatible_content_types or []
        self.cognitive_profile_match = cognitive_profile_match or {}
        self.created_at = datetime.now()
        self.status = "active"
        
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
                 content: str,
                 content_type: str,  # Código del tipo de contenido (text, feynman, diagram, etc.)
                 learning_methodologies: List[str] = None,
                 adaptation_options: Dict = None,
                 resources: List[str] = None,
                 web_resources: List[Dict] = None,
                 generation_prompt: str = None,
                 ai_credits: bool = True,
                 status: str = "draft"):
        self.topic_id = ObjectId(topic_id)
        self.content = content
        self.content_type = content_type
        self.learning_methodologies = learning_methodologies or []
        self.adaptation_options = adaptation_options or {}
        self.resources = resources or []
        self.web_resources = web_resources or []
        self.generation_prompt = generation_prompt
        self.ai_credits = ai_credits
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "content": self.content,
            "content_type": self.content_type,
            "learning_methodologies": self.learning_methodologies,
            "adaptation_options": self.adaptation_options,
            "resources": self.resources,
            "web_resources": self.web_resources,
            "generation_prompt": self.generation_prompt,
            "ai_credits": self.ai_credits,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class LearningResource:
    """
    Modelo para recursos de aprendizaje asociados a temas.
    """
    def __init__(self,
                 topic_id: str,
                 title: str,
                 description: str,
                 resource_type: str,  # pdf, video, link, etc.
                 url: str,
                 tags: List[str] = None,
                 metadata: Dict = None,
                 status: str = "active"):
        self.topic_id = ObjectId(topic_id)
        self.title = title
        self.description = description
        self.resource_type = resource_type
        self.url = url
        self.tags = tags or []
        self.metadata = metadata or {}
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type,
            "url": self.url,
            "tags": self.tags,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

# Constantes para tipos de contenido
class ContentTypes:
    # Contenido Teórico
    TEXT = "text"                     # Texto explicativo
    FEYNMAN = "feynman"               # Método Feynman
    STORY = "story"                   # Historias/Narrativas
    SUMMARY = "summary"               # Resúmenes
    GLOSSARY = "glossary"             # Glosarios
    GUIDED_QUESTIONS = "guided_questions" # Preguntas guiadas
    EXAMPLES = "examples"             # Ejemplos prácticos
    
    # Contenido Visual
    DIAGRAM = "diagram"               # Diagramas
    INFOGRAPHIC = "infographic"       # Infografías
    MINDMAP = "mindmap"               # Mapas mentales/conceptuales
    TIMELINE = "timeline"             # Líneas de tiempo
    ILLUSTRATION = "illustration"     # Ilustraciones
    CHART = "chart"                   # Gráficos estadísticos
    PICTOGRAM = "pictogram"           # Pictogramas
    
    # Contenido Multimedia
    VIDEO = "video"                   # Videos
    AUDIO = "audio"                   # Podcasts/Audio
    MUSIC = "music"                   # Música
    ANIMATION = "animation"           # Animaciones
    SCREENCAST = "screencast"         # Screencast
    NARRATED_PRESENTATION = "narrated_presentation" # Presentaciones narradas
    
    # Contenido Interactivo
    GAME = "game"                     # Juegos educativos
    SIMULATION = "simulation"         # Simulaciones
    VIRTUAL_LAB = "virtual_lab"       # Laboratorios virtuales
    AR = "ar"                         # Realidad aumentada
    MINI_GAME = "mini_game"           # Minijuegos adaptados
    INTERACTIVE_EXERCISE = "interactive_exercise" # Ejercicios interactivos
    CHALLENGE = "challenge"           # Desafíos progresivos
    
    # Contenido de Evaluación
    QUIZ = "quiz"                     # Cuestionarios
    EXAM = "exam"                     # Exámenes adaptados
    PROJECT = "project"               # Proyectos
    RUBRIC = "rubric"                 # Rúbricas personalizadas
    FORMATIVE_TEST = "formative_test" # Tests formativos
    PEER_REVIEW = "peer_review"       # Evaluación por pares
    PORTFOLIO = "portfolio"           # Portfolio digital

    @classmethod
    def get_categories(cls):
        return {
            "theoretical": [cls.TEXT, cls.FEYNMAN, cls.STORY, cls.SUMMARY, cls.GLOSSARY, 
                          cls.GUIDED_QUESTIONS, cls.EXAMPLES],
            "visual": [cls.DIAGRAM, cls.INFOGRAPHIC, cls.MINDMAP, cls.TIMELINE, 
                     cls.ILLUSTRATION, cls.CHART, cls.PICTOGRAM],
            "multimedia": [cls.VIDEO, cls.AUDIO, cls.MUSIC, cls.ANIMATION, 
                         cls.SCREENCAST, cls.NARRATED_PRESENTATION],
            "interactive": [cls.GAME, cls.SIMULATION, cls.VIRTUAL_LAB, cls.AR, 
                          cls.MINI_GAME, cls.INTERACTIVE_EXERCISE, cls.CHALLENGE],
            "evaluation": [cls.QUIZ, cls.EXAM, cls.PROJECT, cls.RUBRIC, 
                         cls.FORMATIVE_TEST, cls.PEER_REVIEW, cls.PORTFOLIO]
        }
        
    @classmethod
    def get_all_types(cls):
        types = []
        for category in cls.get_categories().values():
            types.extend(category)
        return types 

# Constantes para metodologías de aprendizaje
class LearningMethodologyTypes:
    # Estilos de aprendizaje sensoriales
    VISUAL = "visual"                 # Aprendizaje visual
    AUDITORY = "auditory"             # Aprendizaje auditivo
    READ_WRITE = "read_write"         # Aprendizaje por lectura/escritura
    KINESTHETIC = "kinesthetic"       # Aprendizaje kinestésico
    
    # Enfoques pedagógicos
    GAMIFICATION = "gamification"     # Gamificación
    PROBLEM_BASED = "problem_based"   # Aprendizaje basado en problemas
    POMODORO = "pomodoro"             # Método Pomodoro
    CONCEPT_MAPPING = "concept_mapping" # Mapeo conceptual
    COLLABORATIVE = "collaborative"   # Aprendizaje colaborativo
    PERSONALIZED = "personalized"     # Aprendizaje personalizado
    MICROLEARNING = "microlearning"   # Microaprendizaje
    DISCOVERY = "discovery"           # Aprendizaje por descubrimiento
    PROJECT_BASED = "project_based"   # Aprendizaje basado en proyectos
    
    # Técnicas de memoria y retención
    SPACED_REPETITION = "spaced_repetition" # Repetición espaciada
    RETRIEVAL_PRACTICE = "retrieval_practice" # Práctica de recuperación
    FEYNMAN = "feynman"               # Técnica Feynman
    MIND_MAP = "mind_map"             # Mapas mentales
    SOCRATIC = "socratic"             # Método socrático

    # Adaptaciones específicas
    ADHD_ADAPTED = "adhd_adapted"     # Adaptado para TDAH
    DYSLEXIA_ADAPTED = "dyslexia_adapted" # Adaptado para dislexia
    AUTISM_ADAPTED = "autism_adapted" # Adaptado para autismo
    
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
    def get_default_content_compatibility(cls):
        """
        Devuelve mapeo de compatibilidad por defecto entre metodologías y tipos de contenido.
        """
        return {
            # Estilos sensoriales
            cls.VISUAL: ContentTypes.get_categories()["visual"] + [ContentTypes.ANIMATION, ContentTypes.VIDEO],
            cls.AUDITORY: [ContentTypes.AUDIO, ContentTypes.NARRATED_PRESENTATION, ContentTypes.VIDEO],
            cls.READ_WRITE: [ContentTypes.TEXT, ContentTypes.SUMMARY, ContentTypes.GLOSSARY],
            cls.KINESTHETIC: [ContentTypes.SIMULATION, ContentTypes.GAME, ContentTypes.INTERACTIVE_EXERCISE],
            
            # Enfoques pedagógicos
            cls.GAMIFICATION: [ContentTypes.GAME, ContentTypes.CHALLENGE, ContentTypes.MINI_GAME],
            cls.PROBLEM_BASED: [ContentTypes.INTERACTIVE_EXERCISE, ContentTypes.CHALLENGE, ContentTypes.PROJECT],
            cls.CONCEPT_MAPPING: [ContentTypes.MINDMAP, ContentTypes.DIAGRAM, ContentTypes.INFOGRAPHIC],
            cls.DISCOVERY: [ContentTypes.SIMULATION, ContentTypes.VIRTUAL_LAB, ContentTypes.GUIDED_QUESTIONS],
            cls.PROJECT_BASED: [ContentTypes.PROJECT, ContentTypes.PORTFOLIO, ContentTypes.RUBRIC],
            
            # Técnicas de memoria
            cls.SPACED_REPETITION: [ContentTypes.QUIZ, ContentTypes.FLASHCARDS, ContentTypes.FORMATIVE_TEST],
            cls.FEYNMAN: [ContentTypes.FEYNMAN, ContentTypes.SUMMARY, ContentTypes.EXAMPLES],
            cls.MIND_MAP: [ContentTypes.MINDMAP, ContentTypes.DIAGRAM, ContentTypes.INFOGRAPHIC],
            cls.SOCRATIC: [ContentTypes.GUIDED_QUESTIONS, ContentTypes.PEER_REVIEW]
        } 

class TopicResource:
    """
    Modelo para relacionar temas con recursos.
    Permite asociar recursos a temas con metadatos específicos de la relación.
    """
    def __init__(self,
                 topic_id: str,
                 resource_id: str,
                 relevance_score: float = 0.5,
                 recommended_for: List[str] = None,
                 usage_context: str = "supplementary",
                 content_types: List[str] = None,
                 created_by: str = None,
                 status: str = "active"):
        self.topic_id = ObjectId(topic_id)
        self.resource_id = ObjectId(resource_id)
        self.relevance_score = relevance_score
        self.recommended_for = recommended_for or []
        self.usage_context = usage_context
        self.content_types = content_types or []
        self.created_by = ObjectId(created_by) if created_by else None
        self.created_at = datetime.now()
        self.status = status

    def to_dict(self) -> dict:
        """Convierte el objeto a un diccionario para almacenamiento en MongoDB"""
        result = {
            "topic_id": self.topic_id,
            "resource_id": self.resource_id,
            "relevance_score": self.relevance_score,
            "recommended_for": self.recommended_for,
            "usage_context": self.usage_context,
            "content_types": self.content_types,
            "created_at": self.created_at,
            "status": self.status
        }
        
        if self.created_by:
            result["created_by"] = self.created_by
            
        return result 