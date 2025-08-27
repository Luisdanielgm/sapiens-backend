"""
Modelos para el sistema de personalización adaptativa
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from bson import ObjectId


class AdaptiveRecommendation:
    """
    Modelo para recomendaciones adaptativas generadas por el sistema RL
    """

    def __init__(self,
                 student_id: str,
                 topic_id: str,
                 content_recommendations: List[Dict],
                 learning_path_adjustment: Dict,
                 confidence_score: float,
                 reasoning: str,
                 rl_model_response: Dict = None,
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.student_id = ObjectId(student_id)
        self.topic_id = ObjectId(topic_id)
        self.content_recommendations = content_recommendations  # Lista de contenidos recomendados con prioridades
        self.learning_path_adjustment = learning_path_adjustment  # Ajustes al plan de aprendizaje
        self.confidence_score = confidence_score  # Puntaje de confianza del modelo (0-1)
        self.reasoning = reasoning  # Explicación de las recomendaciones
        self.rl_model_response = rl_model_response or {}  # Respuesta completa del modelo RL
        self.created_at = created_at or datetime.now()

    def to_dict(self) -> Dict:
        return {
            "_id": self._id,
            "student_id": self.student_id,
            "topic_id": self.topic_id,
            "content_recommendations": self.content_recommendations,
            "learning_path_adjustment": self.learning_path_adjustment,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "rl_model_response": self.rl_model_response,
            "created_at": self.created_at
        }


class VAKRStatistics:
    """
    Modelo para estadísticas V-A-K-R (Visual, Auditivo, Kinestésico, Lectura/Escritura)
    """

    def __init__(self,
                 student_id: str,
                 content_performance: Dict[str, Dict],  # Rendimiento por tipo de contenido
                 vakr_scores: Dict[str, float],         # Puntajes V-A-K-R normalizados (0-1)
                 dominant_styles: List[str],            # Estilos dominantes ordenados por preferencia
                 content_type_effectiveness: Dict[str, float],  # Efectividad por tipo de contenido
                 learning_patterns: Dict,               # Patrones de aprendizaje identificados
                 recommendations: List[str],            # Recomendaciones basadas en estadísticas
                 analysis_period_days: int = 30,
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.student_id = ObjectId(student_id)
        self.content_performance = content_performance
        self.vakr_scores = vakr_scores
        self.dominant_styles = dominant_styles
        self.content_type_effectiveness = content_type_effectiveness
        self.learning_patterns = learning_patterns
        self.recommendations = recommendations
        self.analysis_period_days = analysis_period_days
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict:
        return {
            "_id": self._id,
            "student_id": self.student_id,
            "content_performance": self.content_performance,
            "vakr_scores": self.vakr_scores,
            "dominant_styles": self.dominant_styles,
            "content_type_effectiveness": self.content_type_effectiveness,
            "learning_patterns": self.learning_patterns,
            "recommendations": self.recommendations,
            "analysis_period_days": self.analysis_period_days,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class RLModelRequest:
    """
    Modelo para solicitudes al servicio externo de RL
    """

    def __init__(self,
                 student_id: str,
                 context_data: Dict,
                 action_type: str,  # "get_recommendation" o "submit_feedback"
                 additional_params: Dict = None):
        self.student_id = student_id
        self.context_data = context_data
        self.action_type = action_type
        self.additional_params = additional_params or {}

    def to_rl_payload(self) -> Dict:
        """
        Convierte la solicitud a formato esperado por la API de RL
        """
        return {
            "student_id": self.student_id,
            "context": self.context_data,
            "action": self.action_type,
            "parameters": self.additional_params
        }


class RLModelResponse:
    """
    Modelo para respuestas del servicio externo de RL
    """

    def __init__(self,
                 success: bool,
                 recommendations: List[Dict] = None,
                 feedback_accepted: bool = None,
                 error_message: str = None,
                 raw_response: Dict = None):
        self.success = success
        self.recommendations = recommendations or []
        self.feedback_accepted = feedback_accepted
        self.error_message = error_message
        self.raw_response = raw_response or {}


class LearningFeedback:
    """
    Modelo para feedback de aprendizaje enviado al sistema RL
    """

    def __init__(self,
                 student_id: str,
                 content_id: str,
                 interaction_type: str,
                 performance_score: float,
                 engagement_metrics: Dict,
                 context_data: Dict,
                 timestamp: Optional[datetime] = None,
                 _id: Optional[ObjectId] = None):
        self._id = _id or ObjectId()
        self.student_id = ObjectId(student_id)
        self.content_id = ObjectId(content_id)
        self.interaction_type = interaction_type  # "content_view", "content_complete", "quiz_attempt", etc.
        self.performance_score = performance_score  # 0-100
        self.engagement_metrics = engagement_metrics  # tiempo, clics, etc.
        self.context_data = context_data  # contexto de la sesión
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict:
        return {
            "_id": self._id,
            "student_id": self.student_id,
            "content_id": self.content_id,
            "interaction_type": self.interaction_type,
            "performance_score": self.performance_score,
            "engagement_metrics": self.engagement_metrics,
            "context_data": self.context_data,
            "timestamp": self.timestamp
        }
