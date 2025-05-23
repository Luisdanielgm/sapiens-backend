from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class VirtualModule:
    def __init__(self,
                 study_plan_id: str,
                 student_id: str,
                 name: str,
                 description: str,
                 adaptations: Optional[Dict] = None,
                 generated_by: str = "IA"):
        self.study_plan_id = ObjectId(study_plan_id)
        self.student_id = ObjectId(student_id)
        self.name = name
        self.description = description
        self.adaptations = adaptations or {}
        self.generated_by = generated_by
        self.created_at = datetime.now()
        self.status = "active"

    def to_dict(self) -> dict:
        return {
            "study_plan_id": self.study_plan_id,
            "student_id": self.student_id,
            "name": self.name,
            "description": self.description,
            "adaptations": self.adaptations,
            "generated_by": self.generated_by,
            "created_at": self.created_at,
            "status": self.status
        }

class VirtualTopic:
    def __init__(self,
                 virtual_module_id: str,
                 name: str,
                 description: str,
                 content: str,
                 multimedia_resources: List[Dict],
                 order: int):
        self.virtual_module_id = ObjectId(virtual_module_id)
        self.name = name
        self.description = description
        self.content = content
        self.multimedia_resources = multimedia_resources
        self.order = order
        self.created_at = datetime.now()
        self.status = "active"

    def to_dict(self) -> dict:
        return {
            "virtual_module_id": self.virtual_module_id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "multimedia_resources": self.multimedia_resources,
            "order": self.order,
            "created_at": self.created_at,
            "status": self.status
        }

class Quiz:
    """
    Modelo para quizzes o evaluaciones formativas interactivas.
    Permite almacenar preguntas detalladas y calcular puntuaciones.
    """
    def __init__(self,
                 virtual_module_id: str,
                 title: str,
                 description: str,
                 due_date: datetime,
                 topics_covered: List[str],
                 questions: List[Dict],  # See comment below for expected structure
                 total_points: float,
                 passing_score: float):
        """
        Args:
            questions: Lista de diccionarios, cada uno representando una pregunta.
                       Structure expected per question:
                       {
                           "id": str,  # Unique question identifier within the quiz
                           "type": "multiple_choice" | "true_false" | "short_answer",
                           "text": str,  # Question text
                           "options": Optional[List[str]],  # For multiple_choice
                           "correct_option": Optional[int],  # Index for multiple_choice
                           "correct_value": Optional[bool],  # For true_false
                           "correct_answer": Optional[str],  # For short_answer
                           "points": float  # Points for this question
                       }
        """
        self.virtual_module_id = ObjectId(virtual_module_id)
        self.title = title
        self.description = description
        self.due_date = due_date
        self.topics_covered = [ObjectId(topic_id) for topic_id in topics_covered]
        self.questions = questions
        self.total_points = total_points
        self.passing_score = passing_score
        self.created_at = datetime.now()
        self.status = "pending"

    def to_dict(self) -> dict:
        return {
            "virtual_module_id": self.virtual_module_id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date,
            "topics_covered": self.topics_covered,
            "questions": self.questions,
            "total_points": self.total_points,
            "passing_score": self.passing_score,
            "created_at": self.created_at,
            "status": self.status
        }

class QuizResult:
    """
    Almacena el resultado de un intento de quiz por parte de un estudiante.
    """
    def __init__(self,
                 quiz_id: str,  # Renamed from virtual_evaluation_id
                 student_id: str,
                 answers: List[Dict],
                 score: float,
                 feedback: Optional[str] = None):
        self.quiz_id = ObjectId(quiz_id)
        self.student_id = ObjectId(student_id)
        self.answers = answers
        self.score = score
        self.feedback = feedback
        self.submitted_at = datetime.now()
        self.status = "completed"

    def to_dict(self) -> dict:
        return {
            "quiz_id": self.quiz_id,
            "student_id": self.student_id,
            "answers": self.answers,
            "score": self.score,
            "feedback": self.feedback,
            "submitted_at": self.submitted_at,
            "status": self.status
        } 