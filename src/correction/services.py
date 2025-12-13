from typing import Tuple, Dict, Optional, Any, List
from bson import ObjectId
from datetime import datetime
import logging
import time

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from src.shared.constants import ROLES
from .models import CorrectionTask

class CorrectionService(VerificationBaseService):
    """
    Servicio para orquestar la corrección automática de exámenes con IA.
    Actúa como un gestor de estado para las tareas que ejecuta el frontend.
    """
    def __init__(self):
        super().__init__(collection_name="correction_tasks")
        self.submissions_collection = get_db().evaluation_submissions

    def _is_staff(self, user_id: str, actor_role: Optional[str] = None, actor_roles: Optional[List[str]] = None) -> bool:
        staff_roles = {ROLES["TEACHER"], ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]}

        observed_roles: List[str] = []
        if actor_role:
            observed_roles.append(actor_role)
        if actor_roles:
            observed_roles.extend([r for r in actor_roles if r])

        normalized = {str(r).lower() for r in observed_roles if r is not None}
        if normalized & staff_roles:
            return True

        try:
            db = get_db()
            user = db.users.find_one({"_id": ObjectId(user_id)})
            if user and isinstance(user.get("role"), str) and user["role"].lower() in staff_roles:
                return True
        except Exception:
            pass

        return False

    def _build_ai_correction(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        ai_score = submission.get("ai_score")
        ai_feedback = submission.get("ai_feedback")

        payload = {
            "submission_id": str(submission.get("_id")),
            "ai_grade": ai_score,
            "ai_feedback": ai_feedback,
            "confidence_score": submission.get("ai_confidence_score"),
            "rubric_analysis": submission.get("ai_rubric_analysis"),
            "suggestions": submission.get("ai_suggestions"),
            "detected_issues": submission.get("ai_detected_issues"),
            "processing_time_ms": submission.get("ai_processing_time_ms"),
        }

        return {k: v for k, v in payload.items() if v is not None}

    def save_ai_correction(
        self,
        submission_id: str,
        ai_score: float,
        ai_feedback: str,
        user_id: str,
        actor_role: Optional[str] = None,
        actor_roles: Optional[List[str]] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Guarda el resultado de una corrección de IA realizada en el frontend.
        """
        try:
            submission = self.submissions_collection.find_one({"_id": ObjectId(submission_id)})
            if not submission:
                return False, {"error": "Submission not found", "status_code": 404}

            is_owner = str(submission.get("student_id")) == user_id
            if not is_owner and not self._is_staff(user_id=user_id, actor_role=actor_role, actor_roles=actor_roles):
                return False, {"error": "Permission denied", "status_code": 403}

            update_data: Dict[str, Any] = {
                "ai_score": ai_score,
                "ai_feedback": ai_feedback,
                "ai_corrected_at": datetime.now(),
                "grade": ai_score, # Also update the main grade
                "feedback": ai_feedback, # Also update the main feedback
                "status": "graded",
                "graded_by": ObjectId(user_id),
                "updated_at": datetime.now()
            }

            if extra_fields and isinstance(extra_fields, dict):
                update_data.update(extra_fields)

            result = self.submissions_collection.update_one(
                {"_id": ObjectId(submission_id)},
                {"$set": update_data}
            )

            if result.matched_count == 0:
                return False, {"error": "Submission not found", "status_code": 404}

            updated = self.submissions_collection.find_one({"_id": ObjectId(submission_id)})
            if not updated:
                return True, {"submission_id": submission_id, "status": "graded"}

            return True, self._build_ai_correction(updated)

        except Exception as e:
            logging.error(f"Error saving AI correction: {str(e)}")
            return False, {"error": "Internal server error"}

    def get_ai_correction(
        self,
        submission_id: str,
        user_id: str,
        actor_role: Optional[str] = None,
        actor_roles: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[Dict]]:
        try:
            submission = self.submissions_collection.find_one({"_id": ObjectId(submission_id)})
            if not submission:
                return False, {"error": "Submission not found", "status_code": 404}

            is_owner = str(submission.get("student_id")) == user_id
            if not is_owner and not self._is_staff(user_id=user_id, actor_role=actor_role, actor_roles=actor_roles):
                return False, {"error": "Permission denied", "status_code": 403}

            if submission.get("ai_score") is None and not submission.get("ai_feedback"):
                return False, {"error": "AI correction not found", "status_code": 404}

            return True, self._build_ai_correction(submission)
        except Exception as e:
            logging.error(f"Error getting AI correction: {str(e)}")
            return False, {"error": "Internal server error"}

    def process_one_pending_task(self) -> Optional[str]:
        """
        Simula un worker: toma una tarea pendiente y la marca como en progreso.
        """
        try:
            task = self.collection.find_one({"status": "pending"}, sort=[("created_at", 1)])
            if not task:
                return None

            task_id = str(task["_id"])
            self.collection.update_one(
                {"_id": task["_id"]},
                {"$set": {"status": "ocr_processing", "updated_at": datetime.now()}, "$inc": {"attempts": 1}}
            )
            return task_id
        except Exception as e:
            logging.error(f"Error processing pending task: {str(e)}")
            return None

    def start_correction_task(self, evaluation_id: str, submission_resource_id: str, 
                              rubric_resource_id: Optional[str], teacher_id: str) -> Tuple[bool, str]:
        """
        Inicia una nueva tarea de corrección automática.

        Args:
            evaluation_id: ID de la evaluación.
            submission_resource_id: ID del recurso (entrega del estudiante).
            rubric_resource_id: ID del recurso (rúbrica del profesor).
            teacher_id: ID del profesor que inicia la tarea.

        Returns:
            Tuple[bool, str]: (Éxito, ID de la tarea o mensaje de error).
        """
        try:
            # TODO: Validar que los recursos y la evaluación existen.
            
            task_data = {
                "evaluation_id": ObjectId(evaluation_id),
                "submission_resource_id": ObjectId(submission_resource_id),
                "rubric_resource_id": ObjectId(rubric_resource_id) if rubric_resource_id else None,
                "teacher_id": ObjectId(teacher_id)
            }
            
            task = CorrectionTask(**task_data)
            task_to_insert = task.to_db()
            
            result = self.collection.insert_one(task_to_insert)
            task_id = str(result.inserted_id)
            
            # En un sistema real, aquí se encolaría la tarea para un worker asíncrono.
            # process_correction_task.delay(task_id) # Ejemplo con Celery
            
            logging.info(f"Nueva tarea de corrección iniciada: {task_id}")
            return True, task_id

        except Exception as e:
            logging.error(f"Error al iniciar la tarea de corrección: {str(e)}")
            return False, "Error interno al iniciar la tarea."

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Obtiene el estado y resultado de una tarea de corrección.
        """
        try:
            task = self.collection.find_one({"_id": ObjectId(task_id)})
            if task:
                return CorrectionTask(**task).model_dump(by_alias=True)
            return None
        except Exception as e:
            logging.error(f"Error al obtener estado de la tarea {task_id}: {str(e)}")
            return None

    def update_task(self, task_id: str, update_data: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Actualiza los campos de una tarea de corrección.

        Args:
            task_id: ID de la tarea a actualizar.
            update_data: Diccionario con los campos y valores a actualizar.

        Returns:
            (Éxito, Tarea actualizada o None)
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                updated_task = self.get_task_status(task_id)
                return True, updated_task
            
            # Si no se modificó, puede que no existiera o los datos eran iguales
            return False, None
        except Exception as e:
            logging.error(f"Error al actualizar la tarea {task_id}: {str(e)}")
            return False, None

    # Los métodos _perform_ocr, _get_resource_content, y _perform_grading_with_llm
    # han sido eliminados, ya que esta lógica ahora reside en el frontend.
    # El método process_one_pending_task también se elimina al no ser ya necesario
    # en este flujo de trabajo.
