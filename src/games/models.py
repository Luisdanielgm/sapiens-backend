from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Any, Union

class Game:
    """
    Modelo base para juegos educativos asociados a un tema específico.
    Creado por un profesor y puede ser personalizado para estudiantes.
    """
    def __init__(self,
                 topic_id: str,
                 title: str,
                 description: str,
                 game_type: str,
                 code: str,
                 metadata: Optional[Dict] = None,
                 creator_id: str = None,
                 tags: List[str] = None,
                 difficulty: str = "medium",
                 time_limit: Optional[int] = None,  # En segundos
                 visual_style: Optional[Dict] = None,
                 audio_enabled: bool = False,
                 accessibility_options: Optional[Dict] = None,
                 cognitive_adaptations: Optional[Dict] = None,
                 is_template: bool = False,
                 estimated_duration: int = 15,  # En minutos
                 learning_objectives: List[str] = None,
                 is_evaluation: bool = False):
        self.topic_id = ObjectId(topic_id)
        self.title = title
        self.description = description
        self.game_type = game_type  # Ver GameTypes para valores válidos
        self.code = code  # Código del juego generado por IA
        self.metadata = metadata or {}  # Configuración, parámetros, etc.
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.tags = tags or []
        self.difficulty = difficulty
        self.time_limit = time_limit  # Opcional, tiempo en segundos
        self.visual_style = visual_style or {}
        self.audio_enabled = audio_enabled
        self.accessibility_options = accessibility_options or {}
        self.cognitive_adaptations = cognitive_adaptations or {}
        self.is_template = is_template
        self.estimated_duration = estimated_duration
        self.learning_objectives = learning_objectives or []
        self.is_evaluation = is_evaluation
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.status = "active"

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "description": self.description,
            "game_type": self.game_type,
            "code": self.code,
            "metadata": self.metadata,
            "creator_id": self.creator_id,
            "tags": self.tags,
            "difficulty": self.difficulty,
            "time_limit": self.time_limit,
            "visual_style": self.visual_style,
            "audio_enabled": self.audio_enabled,
            "accessibility_options": self.accessibility_options,
            "cognitive_adaptations": self.cognitive_adaptations,
            "is_template": self.is_template,
            "estimated_duration": self.estimated_duration,
            "learning_objectives": self.learning_objectives,
            "is_evaluation": self.is_evaluation,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }

class GameTemplate:
    """
    Plantilla parametrizable para crear juegos educativos.
    Permite definir estructuras base que pueden ser adaptadas para diferentes temas.
    """
    def __init__(self,
                 name: str,
                 game_type: str,
                 description: str,
                 template_schema: Dict,
                 default_code: str,
                 preview_image_url: Optional[str] = None,
                 creator_id: Optional[str] = None,
                 tags: List[str] = None,
                 compatibility: Dict[str, Union[List[str], Dict[str, int]]] = None):
        self.name = name
        self.game_type = game_type
        self.description = description
        self.template_schema = template_schema  # Define los parámetros configurables
        self.default_code = default_code  # Código base con marcadores para variables
        self.preview_image_url = preview_image_url
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.tags = tags or []
        self.compatibility = compatibility or {}  # Compatibilidad con perfiles cognitivos
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.status = "active"
        
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "game_type": self.game_type,
            "description": self.description,
            "template_schema": self.template_schema,
            "default_code": self.default_code,
            "preview_image_url": self.preview_image_url,
            "creator_id": self.creator_id,
            "tags": self.tags,
            "compatibility": self.compatibility,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }

class VirtualGame:
    """
    Versión personalizada de un juego para un estudiante específico.
    """
    def __init__(self,
                 game_id: str,
                 virtual_topic_id: str,
                 student_id: str,
                 adaptations: Dict,
                 code: str = None,
                 status: str = "active",
                 performance_data: Dict = None,
                 last_played: datetime = None,
                 completion_percentage: float = 0.0):
        self.game_id = ObjectId(game_id)
        self.virtual_topic_id = ObjectId(virtual_topic_id)
        self.student_id = ObjectId(student_id)
        self.adaptations = adaptations
        self.code = code  # Si es None, usa el código del juego original
        self.status = status
        self.performance_data = performance_data or {}
        self.last_played = last_played
        self.completion_percentage = completion_percentage
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "virtual_topic_id": self.virtual_topic_id,
            "student_id": self.student_id,
            "adaptations": self.adaptations,
            "code": self.code,
            "status": self.status,
            "performance_data": self.performance_data,
            "last_played": self.last_played,
            "completion_percentage": self.completion_percentage,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class GameResult:
    """
    Registra resultados y análisis de sesiones de juego.
    """
    def __init__(self,
                 virtual_game_id: str,
                 student_id: str,
                 session_date: datetime = None,
                 completion_percentage: float = 0.0,
                 score: Optional[float] = None,
                 time_spent: int = 0,  # En segundos
                 actions_log: List[Dict] = None,
                 learning_metrics: Dict = None,
                 feedback: str = None):
        self.virtual_game_id = ObjectId(virtual_game_id)
        self.student_id = ObjectId(student_id)
        self.session_date = session_date or datetime.now()
        self.completion_percentage = completion_percentage
        self.score = score
        self.time_spent = time_spent
        self.actions_log = actions_log or []
        self.learning_metrics = learning_metrics or {}
        self.feedback = feedback
        self.created_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "virtual_game_id": self.virtual_game_id,
            "student_id": self.student_id,
            "session_date": self.session_date,
            "completion_percentage": self.completion_percentage,
            "score": self.score,
            "time_spent": self.time_spent,
            "actions_log": self.actions_log,
            "learning_metrics": self.learning_metrics,
            "feedback": self.feedback,
            "created_at": self.created_at
        }

# Constantes para tipos de juegos
class GameTypes:
    QUIZ = "quiz"                   # Preguntas y respuestas
    MEMORY = "memory"               # Juego de memoria/pares
    CROSSWORD = "crossword"         # Crucigrama
    WORDSEARCH = "wordsearch"       # Sopa de letras
    MATCHING = "matching"           # Asociación de términos/conceptos
    SEQUENCE = "sequence"           # Ordenar secuencias
    PUZZLE = "puzzle"               # Rompecabezas
    ADVENTURE = "adventure"         # Juego de aventura/narrativo
    DRAG_DROP = "drag_drop"         # Arrastar y soltar
    FLASHCARDS = "flashcards"       # Tarjetas de estudio
    HANGMAN = "hangman"             # Ahorcado
    LABYRINTH = "labyrinth"         # Laberinto
    SIMULATION_GAME = "simulation_game" # Juego de simulación simple 