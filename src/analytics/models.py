from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class StudentPerformance:
    def __init__(self,
                 student_id: str,
                 class_id: str,
                 period_id: str,
                 metrics: Dict[str, float],
                 details: Dict[str, any]):
        self.student_id = ObjectId(student_id)
        self.class_id = ObjectId(class_id)
        self.period_id = ObjectId(period_id)
        self.metrics = metrics  # e.g., {"attendance": 0.95, "avg_score": 85.5}
        self.details = details  # Detalles específicos por evaluación/actividad
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "class_id": self.class_id,
            "period_id": self.period_id,
            "metrics": self.metrics,
            "details": self.details,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class ClassStatistics:
    def __init__(self,
                 class_id: str,
                 period_id: str,
                 metrics: Dict[str, float],
                 distribution: Dict[str, List[int]],
                 trends: Dict[str, List[float]]):
        self.class_id = ObjectId(class_id)
        self.period_id = ObjectId(period_id)
        self.metrics = metrics  # e.g., {"avg_attendance": 0.88, "passing_rate": 0.75}
        self.distribution = distribution  # e.g., {"grades": [5,10,15,8,2]}
        self.trends = trends  # e.g., {"weekly_attendance": [0.9,0.85,0.92]}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "period_id": self.period_id,
            "metrics": self.metrics,
            "distribution": self.distribution,
            "trends": self.trends,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class EvaluationAnalytics:
    def __init__(self,
                 evaluation_id: str,
                 class_id: str,
                 metrics: Dict[str, float],
                 question_stats: List[Dict],
                 time_stats: Dict[str, float]):
        self.evaluation_id = ObjectId(evaluation_id)
        self.class_id = ObjectId(class_id)
        self.metrics = metrics  # e.g., {"avg_score": 82.5, "completion_rate": 0.95}
        self.question_stats = question_stats  # Estadísticas por pregunta
        self.time_stats = time_stats  # e.g., {"avg_completion_time": 45.5}
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "class_id": self.class_id,
            "metrics": self.metrics,
            "question_stats": self.question_stats,
            "time_stats": self.time_stats,
            "created_at": self.created_at
        }

class TeacherAnalytics:
    def __init__(self,
                 teacher_id: str,
                 period_id: str,
                 class_metrics: Dict[str, Dict[str, float]],
                 overall_metrics: Dict[str, float],
                 feedback_stats: Dict[str, any]):
        self.teacher_id = ObjectId(teacher_id)
        self.period_id = ObjectId(period_id)
        self.class_metrics = class_metrics  # Métricas por clase
        self.overall_metrics = overall_metrics  # Métricas generales
        self.feedback_stats = feedback_stats  # Estadísticas de retroalimentación
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "teacher_id": self.teacher_id,
            "period_id": self.period_id,
            "class_metrics": self.class_metrics,
            "overall_metrics": self.overall_metrics,
            "feedback_stats": self.feedback_stats,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        } 