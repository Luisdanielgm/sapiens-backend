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