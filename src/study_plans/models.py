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
                 approval_date: Optional[datetime] = None,
                 # Nuevos campos opcionales para unificación
                 institute_id: Optional[str] = None,
                 workspace_id: Optional[str] = None,
                 workspace_type: Optional[str] = None,
                 is_personal: bool = False,
                 objectives: Optional[List[str]] = None,
                 is_public: bool = False,
                 price: Optional[float] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.version = version
        self.author_id = ObjectId(author_id) if isinstance(author_id, str) else author_id
        self.name = name
        self.description = description
        self.status = status
        self.subject_id = ObjectId(subject_id) if subject_id else None
        self.approval_date = approval_date
        # Nuevos campos
        self.institute_id = ObjectId(institute_id) if institute_id else None
        self.workspace_id = ObjectId(workspace_id) if workspace_id else None
        self.workspace_type = workspace_type
        self.is_personal = is_personal
        self.objectives = objectives or []
        self.is_public = is_public
        self.price = price
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "author_id": self.author_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "subject_id": self.subject_id,
            "approval_date": self.approval_date,
            # Nuevos campos
            "institute_id": self.institute_id,
            "workspace_id": self.workspace_id,
            "workspace_type": self.workspace_type,
            "is_personal": self.is_personal,
            "objectives": self.objectives,
            "is_public": self.is_public,
            "price": self.price,
            "created_at": self.created_at,
            "updated_at": self.updated_at
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

# NOTA: Las clases Evaluation, EvaluationResource, EvaluationSubmission y EvaluationRubric
# han sido migradas al módulo src/evaluations/models.py para evitar duplicación.
# Usar las importaciones desde el módulo de evaluaciones:
# from src.evaluations.models import Evaluation, EvaluationResource, EvaluationSubmission, EvaluationRubric