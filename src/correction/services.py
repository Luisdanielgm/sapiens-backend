from typing import Tuple, Dict, Optional
from bson import ObjectId
from datetime import datetime
import logging
import time

from src.shared.database import get_db
from src.shared.standardization import VerificationBaseService, ErrorCodes
from src.shared.exceptions import AppException
from .models import CorrectionTask

class CorrectionService(VerificationBaseService):
    """
    Servicio para orquestar la corrección automática de exámenes con IA.
    Actúa como un gestor de estado para las tareas que ejecuta el frontend.
    """
    def __init__(self):
        super().__init__(collection_name="correction_tasks")

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
