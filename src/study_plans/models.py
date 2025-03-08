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
                 multimedia_resources: List[Dict],
                 theory_content: str = ""):
        self.module_id = ObjectId(module_id)
        self.name = name
        self.difficulty = difficulty
        self.multimedia_resources = multimedia_resources
        self.theory_content = theory_content
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "name": self.name,
            "difficulty": self.difficulty,
            "multimedia_resources": self.multimedia_resources,
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