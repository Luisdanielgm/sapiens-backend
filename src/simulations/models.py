from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class Simulation:
    """
    Modelo para simulaciones educativas asociadas a un tema específico.
    Las simulaciones son entornos interactivos más complejos que los juegos.
    """
    def __init__(self,
                 topic_id: str,
                 title: str,
                 description: str,
                 simulation_type: str,
                 code: str,
                 parameters: Dict,
                 visual_assets: Optional[Dict] = None,
                 creator_id: str = None,
                 complexity: str = "medium",
                 estimated_duration: int = 30,  # En minutos
                 learning_objectives: List[str] = None,
                 tags: List[str] = None):
        self.topic_id = ObjectId(topic_id)
        self.title = title
        self.description = description
        self.simulation_type = simulation_type  # "physics", "chemistry", "biology", etc.
        self.code = code  # Código de la simulación generado por IA
        self.parameters = parameters  # Parámetros configurables de la simulación
        self.visual_assets = visual_assets or {}  # Referencias a recursos visuales
        self.creator_id = ObjectId(creator_id) if creator_id else None
        self.complexity = complexity
        self.estimated_duration = estimated_duration
        self.learning_objectives = learning_objectives or []
        self.tags = tags or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.status = "active"
        self.is_evaluation = False  # Indica si la simulación se usa como evaluación

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "description": self.description,
            "simulation_type": self.simulation_type,
            "code": self.code,
            "parameters": self.parameters,
            "visual_assets": self.visual_assets,
            "creator_id": self.creator_id,
            "complexity": self.complexity,
            "estimated_duration": self.estimated_duration,
            "learning_objectives": self.learning_objectives,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "is_evaluation": self.is_evaluation
        }

class VirtualSimulation:
    """
    Versión personalizada de una simulación para un estudiante específico.
    Se adapta según el perfil cognitivo del estudiante.
    """
    def __init__(self,
                 simulation_id: str,
                 virtual_topic_id: str,
                 student_id: str,
                 adaptations: Dict,
                 code: str = None,
                 status: str = "active"):
        self.simulation_id = ObjectId(simulation_id)
        self.virtual_topic_id = ObjectId(virtual_topic_id)
        self.student_id = ObjectId(student_id)
        self.adaptations = adaptations  # Adaptaciones específicas para el estudiante
        self.code = code  # Si es None, se usa el código de la simulación original
        self.status = status
        self.created_at = datetime.now()
        self.last_used = None
        self.completion_status = "not_started"  # "not_started", "in_progress", "completed"
        self.time_spent = 0  # Tiempo total en segundos
        self.interactions = 0  # Número de interacciones con la simulación
        self.achievement_data = {}  # Datos sobre logros y progreso
        self.learning_path = []  # Secuencia de interacciones/decisiones tomadas

    def to_dict(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "virtual_topic_id": self.virtual_topic_id,
            "student_id": self.student_id,
            "adaptations": self.adaptations,
            "code": self.code,
            "status": self.status,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "completion_status": self.completion_status,
            "time_spent": self.time_spent,
            "interactions": self.interactions,
            "achievement_data": self.achievement_data,
            "learning_path": self.learning_path
        }

class SimulationResult:
    """
    Almacena los resultados y análisis de una sesión de simulación para un estudiante.
    Útil para evaluaciones o para seguimiento del progreso.
    """
    def __init__(self,
                 virtual_simulation_id: str,
                 student_id: str,
                 session_date: datetime = None,
                 completion_percentage: float = 0.0,
                 score: Optional[float] = None,
                 data_points: Dict = None,
                 feedback: str = None):
        self.virtual_simulation_id = ObjectId(virtual_simulation_id)
        self.student_id = ObjectId(student_id)
        self.session_date = session_date or datetime.now()
        self.completion_percentage = completion_percentage
        self.score = score
        self.data_points = data_points or {}  # Datos específicos recopilados durante la simulación
        self.feedback = feedback
        self.created_at = datetime.now()
        self.analysis = {}  # Análisis automatizado del desempeño

    def to_dict(self) -> dict:
        return {
            "virtual_simulation_id": self.virtual_simulation_id,
            "student_id": self.student_id,
            "session_date": self.session_date,
            "completion_percentage": self.completion_percentage,
            "score": self.score,
            "data_points": self.data_points,
            "feedback": self.feedback,
            "created_at": self.created_at,
            "analysis": self.analysis
        } 