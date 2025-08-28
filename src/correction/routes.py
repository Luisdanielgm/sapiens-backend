from flask import request, g
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId
import logging
from datetime import datetime

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.decorators import auth_required, role_required
from src.shared.constants import ROLES
from .services import CorrectionService

correction_bp = APIBlueprint('correction', __name__)
correction_service = CorrectionService()

@correction_bp.route('/submission/<submission_id>/ai-result', methods=['PUT'])
@auth_required
def record_ai_correction(submission_id):
    """
    Endpoint para que el frontend guarde el resultado de una corrección hecha por IA.
    """
    try:
        data = request.json
        user_id = get_jwt_identity()

        required_fields = ["ai_score", "ai_feedback"]
        if not all(field in data for field in required_fields):
            return APIRoute.error(ErrorCodes.MISSING_FIELDS, "Faltan campos requeridos (ai_score, ai_feedback).")

        success, result = correction_service.save_ai_correction(
            submission_id=submission_id,
            ai_score=data["ai_score"],
            ai_feedback=data["ai_feedback"],
            user_id=user_id
        )

        if success:
            return APIRoute.success(
                data=result,
                message="Resultado de la corrección IA guardado exitosamente."
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error en endpoint record_ai_correction: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor.")

@correction_bp.route('/start', methods=['POST'])
@auth_required
@role_required(ROLES["TEACHER"])
def start_correction():
    """
    Inicia una nueva tarea de corrección automática para una entrega.
    
    Body:
    {
        "evaluation_id": "ObjectId",
        "submission_resource_id": "ObjectId",
        "rubric_resource_id": "ObjectId" (Opcional)
    }
    """
    try:
        data = request.json
        teacher_id = get_jwt_identity()

        required_fields = ["evaluation_id", "submission_resource_id"]
        if not all(field in data for field in required_fields):
            return APIRoute.error(ErrorCodes.MISSING_FIELDS, "Faltan campos requeridos.")

        success, result = correction_service.start_correction_task(
            evaluation_id=data["evaluation_id"],
            submission_resource_id=data["submission_resource_id"],
            rubric_resource_id=data.get("rubric_resource_id"),
            teacher_id=teacher_id
        )

        if success:
            return APIRoute.success(
                data={"task_id": result},
                message="Tarea de corrección iniciada. La calificación estará disponible pronto.",
                status_code=202  # Accepted
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error en endpoint start_correction: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor.")

@correction_bp.route('/task/<task_id>', methods=['GET'])
@auth_required
def get_correction_task_status(task_id):
    """
    Consulta el estado y resultado de una tarea de corrección.
    """
    try:
        task_status = correction_service.get_task_status(task_id)

        if task_status:
            # Verificar permisos: solo el profesor que la creó o un admin pueden verla.
            user_id = get_jwt_identity()
            user_roles = getattr(g, 'user_roles', [])
            
            if str(task_status.get('teacher_id')) != user_id and ROLES["ADMIN"] not in user_roles:
                return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver esta tarea.")

            return APIRoute.success(data=task_status)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Tarea de corrección no encontrada.", status_code=404)
            
    except Exception as e:
        logging.error(f"Error en endpoint get_correction_task_status: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor.")

@correction_bp.route('/task/<task_id>', methods=['PUT'])
@auth_required
def update_correction_task(task_id):
    """
    Permite al frontend (o a un worker) actualizar el estado y los datos de una tarea.
    Esencial para el flujo donde el frontend realiza las llamadas a la IA.
    """
    try:
        data = request.json
        user_id = get_jwt_identity()
        
        # Validar que la tarea exista
        task = correction_service.get_task_status(task_id)
        if not task:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Tarea de corrección no encontrada.")

        # Verificar permisos
        if str(task.get('teacher_id')) != user_id:
            return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para actualizar esta tarea.")

        # Construir el objeto de actualización
        update_data = {"updated_at": datetime.now()}
        allowed_fields = ["status", "ocr_extracted_text", "llm_prompt", "suggested_grade", "feedback", "cost", "error_message"]
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Realizar la actualización en el servicio
        success, result = correction_service.update_task(task_id, update_data)
        
        if success:
            return APIRoute.success(data=result, message="Tarea actualizada exitosamente.")
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, "No se pudo actualizar la tarea.")
            
    except Exception as e:
        logging.error(f"Error en endpoint update_correction_task: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor.")

@correction_bp.route('/process-next', methods=['POST'])
@auth_required
@role_required(ROLES["ADMIN"])  # Solo administradores pueden llamar a este endpoint
def process_next_correction_task():
    """
    Procesa la siguiente tarea de corrección pendiente en la cola.
    Este endpoint simula un worker y debería ser llamado por un cron job.
    """
    try:
        processed_task_id = correction_service.process_one_pending_task()

        if processed_task_id:
            return APIRoute.success(
                data={"processed_task_id": processed_task_id},
                message=f"Tarea {processed_task_id} procesada exitosamente."
            )
        else:
            return APIRoute.success(
                data={},
                message="No hay tareas de corrección pendientes para procesar."
            )
            
    except Exception as e:
        logging.error(f"Error en el worker de corrección: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno durante el procesamiento de la tarea.")