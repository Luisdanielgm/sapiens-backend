from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional
from src.shared.constants import STATUS

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
                 evaluation_rubric: Dict[str, any],
                 date_start: datetime,
                 date_end: datetime,
                 content_completeness_score: int = 0,
                 virtualization_requirements: Optional[Dict] = None,
                 last_content_update: Optional[datetime] = None,
                 content_versions: Optional[List[Dict]] = None):
        self.study_plan_id = ObjectId(study_plan_id)
        self.name = name
        self.learning_outcomes = learning_outcomes
        self.evaluation_rubric = evaluation_rubric
        self.date_start = date_start
        self.date_end = date_end
        self.content_completeness_score = content_completeness_score
        self.virtualization_requirements = virtualization_requirements or {}
        self.last_content_update = last_content_update or datetime.now()
        self.content_versions = content_versions or []
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "study_plan_id": self.study_plan_id,
            "name": self.name,
            "learning_outcomes": self.learning_outcomes,
            "evaluation_rubric": self.evaluation_rubric,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "content_completeness_score": self.content_completeness_score,
            "virtualization_requirements": self.virtualization_requirements,
            "last_content_update": self.last_content_update,
            "content_versions": self.content_versions,
            "created_at": self.created_at
        }

class Topic:
    def __init__(self,
                 module_id: str,
                 name: str,
                 difficulty: str,
                 date_start: datetime,
                 date_end: datetime,
                 theory_content: str = "",
                 published: bool = False):
        self.module_id = ObjectId(module_id)
        self.name = name
        self.difficulty = difficulty
        self.theory_content = theory_content
        self.date_start = date_start
        self.date_end = date_end
        self.published = published
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "name": self.name,
            "difficulty": self.difficulty,
            "theory_content": self.theory_content,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "published": self.published,
            "created_at": self.created_at
        }

class Evaluation:
    def __init__(self,
                 module_id: str,
                 title: str,
                 description: str,
                 weight: float,
                 criteria: List[Dict],
                 due_date: datetime,
                 use_quiz_score: bool = False,
                 requires_submission: bool = False,
                 linked_quiz_id: Optional[str] = None):
        self.module_id = ObjectId(module_id)
        self.title = title
        self.description = description
        self.weight = weight
        self.criteria = criteria
        self.due_date = due_date
        self.use_quiz_score = use_quiz_score
        self.requires_submission = requires_submission
        self.linked_quiz_id = ObjectId(linked_quiz_id) if linked_quiz_id else None
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
            "status": self.status,
            "use_quiz_score": self.use_quiz_score,
            "requires_submission": self.requires_submission,
            "linked_quiz_id": self.linked_quiz_id
        }

# DEPRECATED: Usar ContentResult en su lugar.
# class EvaluationResult:
#     def __init__(self,
#                  evaluation_id: str,
#                  student_id: str,
#                  score: float,
#                  feedback: str = ""):
#         self.evaluation_id = ObjectId(evaluation_id)
#         self.student_id = ObjectId(student_id)
#         self.score = score
#         self.feedback = feedback
#         self.recorded_at = datetime.now()

#     def to_dict(self) -> dict:
#         return {
#             "evaluation_id": self.evaluation_id,
#             "student_id": self.student_id,
#             "score": self.score,
#             "feedback": self.feedback,
#             "recorded_at": self.recorded_at
#         }

class EvaluationResource:
    """
    Modelo para la vinculación entre una Evaluación y un Recurso.
    Define el rol del recurso en la evaluación (plantilla, entregable, material de apoyo).
    """
    def __init__(self,
                 evaluation_id: str,
                 resource_id: str,
                 role: str,  # e.g., "template", "submission", "supporting_material"
                 created_by: str,
                 status: str = STATUS["ACTIVE"],
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.evaluation_id = ObjectId(evaluation_id)
        self.resource_id = ObjectId(resource_id)
        self.role = role
        self.created_by = ObjectId(created_by)
        self.status = status
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "evaluation_id": self.evaluation_id,
            "resource_id": self.resource_id,
            "role": self.role,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at
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
                 interactive_data: Optional[Dict] = None,  # Para quizzes, simulaciones, etc.
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
        self.interactive_data = interactive_data or {}
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
            "interactive_data": self.interactive_data,
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

class ContentTypes:
    # Contenido Teórico
    TEXT = "text"                     # Texto explicativo
    FEYNMAN = "feynman"               # Método Feynman
    STORY = "story"                   # Historias/Narrativas
    SUMMARY = "summary"               # Resúmenes
    GLOSSARY = "glossary"             # Glosarios
    GUIDED_QUESTIONS = "guided_questions" # Preguntas guiadas
    EXAMPLES = "examples"             # Ejemplos prácticos
    DOCUMENTS = "documents"           # Para PDFs y otros documentos (NUEVO)
    SLIDES = "slides"                 # Diapositivas/Presentaciones
    IMAGE = "image"                   # Imagen estática
    LINK = "link"                     # Enlace web (NUEVO)
    
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
    # Nota: Para quizzes interactivos con lógica de backend (envío, score, resultados),
    #       usar el módulo dedicado 'quizzes' (API /api/quizzes).
    #       Este tipo 'QUIZ' es ideal para incrustar cuestionarios simples como contenido.
    QUIZ = "quiz"                     # Cuestionarios (principalmente contenido embedido)
    EXAM = "exam"                     # Exámenes adaptados (usar EvaluationService para la lógica)
    PROJECT = "project"               # Proyectos (usar EvaluationService para la lógica)
    RUBRIC = "rubric"                 # Rúbricas personalizadas (usar EvaluationService para la lógica)
    FORMATIVE_TEST = "formative_test" # Tests formativos (podría ser QUIZ o un quiz dedicado)
    PEER_REVIEW = "peer_review"       # Evaluación por pares (lógica específica requerida)
    PORTFOLIO = "portfolio"           # Portfolio digital (lógica específica requerida)

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