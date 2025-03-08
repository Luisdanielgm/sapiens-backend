from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

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
                 difficulty: str = "medium"):
        self.topic_id = ObjectId(topic_id)
        self.title = title
        self.description = description
        self.game_type = game_type  # "quiz", "adventure", "puzzle", etc.
        self.code = code  # Código del juego generado por IA
        self.metadata = metadata or {}  # Configuración, parámetros, etc.
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.tags = tags or []
        self.difficulty = difficulty
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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }

class VirtualGame:
    """
    Versión personalizada de un juego para un estudiante específico.
    Se adapta según el perfil cognitivo del estudiante.
    """
    def __init__(self,
                 game_id: str,
                 virtual_topic_id: str,
                 student_id: str,
                 adaptations: Dict,
                 code: str = None,
                 status: str = "active"):
        self.game_id = ObjectId(game_id)
        self.virtual_topic_id = ObjectId(virtual_topic_id)
        self.student_id = ObjectId(student_id)
        self.adaptations = adaptations  # Adaptaciones específicas para el estudiante
        self.code = code  # Si es None, se usa el código del juego original
        self.status = status
        self.created_at = datetime.now()
        self.last_played = None
        self.completion_status = "not_started"  # "not_started", "in_progress", "completed"
        self.score = 0

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "virtual_topic_id": self.virtual_topic_id,
            "student_id": self.student_id,
            "adaptations": self.adaptations,
            "code": self.code,
            "status": self.status,
            "created_at": self.created_at,
            "last_played": self.last_played,
            "completion_status": self.completion_status,
            "score": self.score
        } 