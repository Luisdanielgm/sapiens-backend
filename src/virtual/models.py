from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional

class VirtualModule:
    def __init__(self,
                 study_plan_id: str,
                 module_id: str,
                 student_id: str,
                 adaptations: Optional[Dict] = None,
                 generated_by: str = "IA",
                 updates: Optional[List[Dict]] = None,
                 generation_status: str = "pending",
                 generation_progress: int = 0,
                 last_generation_attempt: Optional[datetime] = None,
                 completion_status: str = "not_started",
                 progress: float = 0.0):
        self.study_plan_id = ObjectId(study_plan_id)
        self.module_id = ObjectId(module_id)
        self.student_id = ObjectId(student_id)
        self.adaptations = adaptations or {}
        self.generated_by = generated_by
        self.updates = updates or []
        self.generation_status = generation_status  # pending, generating, completed, failed
        self.generation_progress = generation_progress  # 0-100
        self.last_generation_attempt = last_generation_attempt
        self.created_at = datetime.now()
        self.status = "active"
        self.completion_status = completion_status
        self.progress = progress

    def to_dict(self) -> dict:
        return {
            "study_plan_id": self.study_plan_id,
            "module_id": self.module_id,
            "student_id": self.student_id,
            "adaptations": self.adaptations,
            "generated_by": self.generated_by,
            "updates": self.updates,
            "generation_status": self.generation_status,
            "generation_progress": self.generation_progress,
            "last_generation_attempt": self.last_generation_attempt,
            "created_at": self.created_at,
            "status": self.status,
            "completion_status": self.completion_status,
            "progress": self.progress
        }

class VirtualTopic:
    def __init__(self,
                 virtual_module_id: str,
                 topic_id: str,
                 student_id: str,
                 adaptations: Optional[Dict] = None,
                 order: int = 0,
                 status: str = "locked",
                 progress: float = 0.0,
                 completion_status: str = "not_started"):
        self.virtual_module_id = ObjectId(virtual_module_id)
        self.topic_id = ObjectId(topic_id)
        self.student_id = ObjectId(student_id)
        self.adaptations = adaptations or {}
        self.order = order
        self.status = status
        self.progress = progress
        self.completion_status = completion_status
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "virtual_module_id": self.virtual_module_id,
            "topic_id": self.topic_id,
            "student_id": self.student_id,
            "adaptations": self.adaptations,
            "order": self.order,
            "status": self.status,
            "progress": self.progress,
            "completion_status": self.completion_status,
            "created_at": self.created_at
        }

class VirtualGenerationTask:
    """
    Cola de tareas para generación progresiva de módulos virtuales.
    Adaptado para arquitectura serverless.
    """
    def __init__(self,
                 student_id: str,
                 module_id: str,
                 task_type: str,  # "generate" | "update" | "enhance"
                 priority: int = 5,
                 status: str = "pending",
                 attempts: int = 0,
                 max_attempts: int = 3,
                 payload: Optional[Dict] = None):
        self.student_id = ObjectId(student_id)
        self.module_id = ObjectId(module_id)
        self.task_type = task_type
        self.priority = priority  # 1 = más alta, 10 = más baja
        self.status = status  # pending, processing, completed, failed
        self.attempts = attempts
        self.max_attempts = max_attempts
        self.payload = payload or {}
        self.created_at = datetime.now()
        self.processing_started_at = None
        self.completed_at = None
        self.error_message = None
        self.estimated_duration = 30  # segundos estimados
        
    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "module_id": self.module_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "payload": self.payload,
            "created_at": self.created_at,
            "processing_started_at": self.processing_started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "estimated_duration": self.estimated_duration
        }

class ContentTemplate:
    """
    Templates pre-generados para acelerar la creación de módulos virtuales.
    """
    def __init__(self,
                 template_type: str,  # "module", "topic", "content"
                 content_type: str,  # "text", "diagram", "quiz", etc.
                 methodology: str,   # "visual", "kinesthetic", etc.
                 template_data: Dict,
                 usage_count: int = 0,
                 effectiveness_score: float = 0.5):
        self.template_type = template_type
        self.content_type = content_type
        self.methodology = methodology
        self.template_data = template_data
        self.usage_count = usage_count
        self.effectiveness_score = effectiveness_score
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
    def to_dict(self) -> dict:
        return {
            "template_type": self.template_type,
            "content_type": self.content_type,
            "methodology": self.methodology,
            "template_data": self.template_data,
            "usage_count": self.usage_count,
            "effectiveness_score": self.effectiveness_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        } 