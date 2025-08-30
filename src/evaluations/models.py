from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional
from src.shared.constants import STATUS

class Evaluation:
    """Represents an evaluation that can span multiple topics."""

    def __init__(self,
                 topic_ids: List[str],
                 title: str,
                 description: str,
                 weight: float,
                 criteria: List[Dict],
                 due_date: datetime,
                 evaluation_type: str = "assignment",  # "assignment", "quiz", "project", "exam"
                 use_quiz_score: bool = False,
                 requires_submission: bool = False,
                 linked_quiz_id: Optional[str] = None,
                 auto_grading: bool = False,
                 weightings: Optional[Dict[str, float]] = None,
                 rubric: Optional[Dict] = None,
                 max_attempts: int = 1,
                 time_limit: Optional[int] = None,  # in minutes
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 status: str = "pending"):
        self._id = _id or ObjectId()
        self.topic_ids = [ObjectId(tid) for tid in topic_ids]
        self.title = title
        self.description = description
        self.weight = weight
        self.criteria = criteria
        self.due_date = due_date
        self.evaluation_type = evaluation_type
        self.use_quiz_score = use_quiz_score
        self.requires_submission = requires_submission
        self.linked_quiz_id = ObjectId(linked_quiz_id) if linked_quiz_id else None
        self.auto_grading = auto_grading
        self.weightings = weightings or {}  # Dict[topic_id: weight] for multi-topic evaluations
        self.rubric = rubric or {}  # Rubric configuration or reference
        self.max_attempts = max_attempts
        self.time_limit = time_limit
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.status = status

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "topic_ids": self.topic_ids,
            "title": self.title,
            "description": self.description,
            "weight": self.weight,
            "criteria": self.criteria,
            "due_date": self.due_date,
            "evaluation_type": self.evaluation_type,
            "use_quiz_score": self.use_quiz_score,
            "requires_submission": self.requires_submission,
            "linked_quiz_id": self.linked_quiz_id,
            "auto_grading": self.auto_grading,
            "weightings": self.weightings,
            "rubric": self.rubric,
            "max_attempts": self.max_attempts,
            "time_limit": self.time_limit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }

    def is_multi_topic(self) -> bool:
        """Check if this evaluation spans multiple topics."""
        return len(self.topic_ids) > 1

    def get_topic_weight(self, topic_id: str) -> float:
        """Get the weight for a specific topic in multi-topic evaluations."""
        if not self.is_multi_topic():
            return 1.0
        return self.weightings.get(str(topic_id), 0.0)

    def validate_weightings(self) -> bool:
        """Validate that weightings sum to 1.0 for multi-topic evaluations."""
        if not self.is_multi_topic():
            return True
        total_weight = sum(self.weightings.values())
        return abs(total_weight - 1.0) < 0.001  # Allow for floating point precision

class EvaluationResource:
    """
    Modelo para la vinculación entre una Evaluación y un Recurso.
    Define el rol del recurso en la evaluación (plantilla, entregable, material de apoyo).
    """
    def __init__(self,
                 evaluation_id: str,
                 resource_id: str,
                 role: str,  # e.g., "template", "submission", "supporting_material", "rubric"
                 created_by: str,
                 status: str = STATUS["ACTIVE"],
                 metadata: Optional[Dict] = None,
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.evaluation_id = ObjectId(evaluation_id)
        self.resource_id = ObjectId(resource_id)
        self.role = role
        self.created_by = ObjectId(created_by)
        self.status = status
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "evaluation_id": self.evaluation_id,
            "resource_id": self.resource_id,
            "role": self.role,
            "created_by": self.created_by,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class EvaluationSubmission:
    """
    Modelo para las entregas de estudiantes para evaluaciones.
    """
    def __init__(self,
                 evaluation_id: str,
                 student_id: str,
                 submission_type: str = "file",  # "file", "text", "url", "quiz_response"
                 content: Optional[str] = None,
                 file_path: Optional[str] = None,
                 url: Optional[str] = None,
                 grade: Optional[float] = None,
                 feedback: Optional[str] = None,
                 graded_by: Optional[str] = None,
                 graded_at: Optional[datetime] = None,
                 is_late: bool = False,
                 attempts: int = 1,
                 status: str = "submitted",
                 ai_score: Optional[float] = None,
                 ai_feedback: Optional[str] = None,
                 ai_corrected_at: Optional[datetime] = None,
                 topic_scores: Optional[Dict[str, float]] = None,  # For multi-topic evaluations
                 submission_metadata: Optional[Dict] = None,
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.evaluation_id = ObjectId(evaluation_id)
        self.student_id = student_id  # Keep as string to match database storage
        self.submission_type = submission_type
        self.content = content
        self.file_path = file_path
        self.url = url
        self.grade = grade
        self.feedback = feedback
        self.graded_by = ObjectId(graded_by) if graded_by else None
        self.graded_at = graded_at
        self.is_late = is_late
        self.attempts = attempts
        self.status = status
        self.ai_score = ai_score
        self.ai_feedback = ai_feedback
        self.ai_corrected_at = ai_corrected_at
        self.topic_scores = topic_scores or {}  # Dict[topic_id: score]
        self.submission_metadata = submission_metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "evaluation_id": self.evaluation_id,
            "student_id": self.student_id,
            "submission_type": self.submission_type,
            "content": self.content,
            "file_path": self.file_path,
            "url": self.url,
            "grade": self.grade,
            "feedback": self.feedback,
            "graded_by": self.graded_by,
            "graded_at": self.graded_at,
            "is_late": self.is_late,
            "attempts": self.attempts,
            "status": self.status,
            "ai_score": self.ai_score,
            "ai_feedback": self.ai_feedback,
            "ai_corrected_at": self.ai_corrected_at,
            "topic_scores": self.topic_scores,
            "submission_metadata": self.submission_metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def calculate_weighted_grade(self, evaluation: Evaluation) -> float:
        """Calculate weighted grade for multi-topic evaluations."""
        if not evaluation.is_multi_topic() or not self.topic_scores:
            return self.grade or 0.0
        
        weighted_score = 0.0
        for topic_id, score in self.topic_scores.items():
            weight = evaluation.get_topic_weight(topic_id)
            weighted_score += score * weight
        
        return weighted_score

class EvaluationRubric:
    """
    Modelo para las rúbricas de evaluación.
    """
    def __init__(self,
                 evaluation_id: str,
                 title: str,
                 description: str = "",
                 criteria: List[Dict] = None,
                 total_points: float = 100.0,
                 grading_scale: Optional[Dict] = None,
                 created_by: str = None,
                 status: str = STATUS["ACTIVE"],
                 rubric_type: str = "standard",  # "standard", "holistic", "analytic"
                 _id: Optional[ObjectId] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self._id = _id or ObjectId()
        self.evaluation_id = ObjectId(evaluation_id)
        self.title = title
        self.description = description
        self.criteria = criteria or []
        self.total_points = total_points
        self.grading_scale = grading_scale or self._default_grading_scale()
        self.created_by = ObjectId(created_by) if created_by else None
        self.status = status
        self.rubric_type = rubric_type
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def _default_grading_scale(self) -> Dict:
        """Default grading scale for letter grades."""
        return {
            "A": {"min": 90, "max": 100},
            "B": {"min": 80, "max": 89},
            "C": {"min": 70, "max": 79},
            "D": {"min": 60, "max": 69},
            "F": {"min": 0, "max": 59}
        }

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "evaluation_id": self.evaluation_id,
            "title": self.title,
            "description": self.description,
            "criteria": self.criteria,
            "total_points": self.total_points,
            "grading_scale": self.grading_scale,
            "created_by": self.created_by,
            "status": self.status,
            "rubric_type": self.rubric_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def calculate_grade(self, criteria_scores: Dict[str, float]) -> Dict:
        """
        Calcula una calificación basada en los puntajes de criterios.
        
        Args:
            criteria_scores: Diccionario con puntajes por criterio
            
        Returns:
            Diccionario con el resultado del cálculo
        """
        try:
            total_score = 0
            max_possible = 0
            detailed_scores = []
            
            for criterion in self.criteria:
                criterion_id = criterion.get("id")
                max_points = criterion.get("points", 0)
                score = criteria_scores.get(criterion_id, 0)
                
                # Validar que el puntaje no exceda el máximo
                if score > max_points:
                    score = max_points
                    
                total_score += score
                max_possible += max_points
                
                detailed_scores.append({
                    "criterion_id": criterion_id,
                    "criterion_name": criterion.get("name", ""),
                    "score": score,
                    "max_points": max_points,
                    "percentage": (score / max_points) * 100 if max_points > 0 else 0
                })
            
            # Calcular porcentaje final
            final_percentage = (total_score / max_possible) * 100 if max_possible > 0 else 0
            
            return {
                "total_score": total_score,
                "max_possible": max_possible,
                "final_percentage": round(final_percentage, 2),
                "grade": self.percentage_to_letter_grade(final_percentage),
                "detailed_scores": detailed_scores,
                "rubric_id": str(self._id)
            }
            
        except Exception as e:
            return {"error": f"Error al calcular calificación: {str(e)}"}
    
    def percentage_to_letter_grade(self, percentage: float) -> str:
        """Convierte un porcentaje a calificación letra usando la escala configurada."""
        for grade, range_dict in self.grading_scale.items():
            if range_dict["min"] <= percentage <= range_dict["max"]:
                return grade
        return "F"  # Default fallback

    def validate_criteria(self) -> bool:
        """Validate that criteria are properly configured."""
        if not self.criteria:
            return False
        
        total_points = sum(criterion.get("points", 0) for criterion in self.criteria)
        return abs(total_points - self.total_points) < 0.001