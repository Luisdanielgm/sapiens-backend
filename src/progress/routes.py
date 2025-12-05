"""
Progress Routes - Endpoints para consultar progreso de estudiantes.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.shared.standardization import APIRoute
from src.shared.decorators import auth_required, role_required
from src.shared.constants import ROLES
from .services import ProgressService

progress_bp = Blueprint('progress', __name__, url_prefix='/api/progress')

progress_service = ProgressService()


@progress_bp.route('/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_progress(student_id: str):
    """
    Obtiene el progreso completo de un estudiante.
    
    Puede ser llamado por:
    - El propio estudiante
    - Un profesor de sus clases
    - Un administrador
    
    Returns:
        {
            "student_id": str,
            "overall_progress": float,
            "by_subject": [
                {
                    "subject_id": str,
                    "subject_name": str,
                    "progress_percentage": float,
                    "completed_topics": int,
                    "total_topics": int,
                    "current_module": str,
                    "current_topic": str,
                    "modules": [...]
                }
            ],
            "activity_breakdown": {
                "slides": {"viewed": int, "total": int, "percentage": float},
                "interactive": {"completed": int, "total": int, "percentage": float},
                "quizzes": {"passed": int, "total": int, "percentage": float, "average_score": float}
            },
            "recent_activity": [...],
            "vark_profile": {...}
        }
    """
    try:
        current_user = get_jwt_identity()
        
        # TODO: Agregar validación de permisos
        # Por ahora permitimos que cualquier usuario autenticado consulte
        
        progress = progress_service.get_student_progress(student_id)
        
        return APIRoute.success(
            data=progress,
            message="Progreso obtenido exitosamente"
        )
        
    except Exception as e:
        return APIRoute.error(
            error_code="PROGRESS_ERROR",
            message=f"Error obteniendo progreso: {str(e)}",
            status_code=500
        )


@progress_bp.route('/student/me', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
def get_my_progress():
    """
    Obtiene el progreso del estudiante autenticado.
    """
    try:
        student_id = get_jwt_identity()
        
        progress = progress_service.get_student_progress(student_id)
        
        return APIRoute.success(
            data=progress,
            message="Progreso obtenido exitosamente"
        )
        
    except Exception as e:
        return APIRoute.error(
            error_code="PROGRESS_ERROR",
            message=f"Error obteniendo progreso: {str(e)}",
            status_code=500
        )


@progress_bp.route('/class/<class_id>/students', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]])
def get_class_students_progress(class_id: str):
    """
    Obtiene el progreso de todos los estudiantes de una clase.
    
    Solo accesible por profesores de la clase o administradores.
    
    Returns:
        {
            "class_id": str,
            "class_name": str,
            "students": [
                {
                    "student_id": str,
                    "student_name": str,
                    "overall_progress": float,
                    "current_module": str,
                    "current_topic": str,
                    "activities_completed": int,
                    "last_activity": str
                }
            ],
            "class_average": float,
            "total_students": int
        }
    """
    try:
        # TODO: Validar que el profesor pertenece a la clase
        
        progress = progress_service.get_class_students_progress(class_id)
        
        return APIRoute.success(
            data=progress,
            message="Progreso de clase obtenido exitosamente"
        )
        
    except Exception as e:
        return APIRoute.error(
            error_code="PROGRESS_ERROR",
            message=f"Error obteniendo progreso de clase: {str(e)}",
            status_code=500
        )


@progress_bp.route('/student/<student_id>/topic/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_topic_progress(student_id: str, topic_id: str):
    """
    Obtiene el progreso detallado de un estudiante en un tema específico.
    
    Returns:
        {
            "student_id": str,
            "topic_id": str,
            "topic_name": str,
            "progress": float,
            "completed_count": int,
            "total_count": int,
            "average_score": float,
            "contents": [
                {
                    "content_id": str,
                    "content_type": str,
                    "title": str,
                    "is_interactive": bool,
                    "status": "completed" | "in_progress" | "not_started",
                    "score": float,
                    "completed_at": str
                }
            ]
        }
    """
    try:
        progress = progress_service.get_topic_progress(student_id, topic_id)
        
        return APIRoute.success(
            data=progress,
            message="Progreso del tema obtenido exitosamente"
        )
        
    except Exception as e:
        return APIRoute.error(
            error_code="PROGRESS_ERROR",
            message=f"Error obteniendo progreso del tema: {str(e)}",
            status_code=500
        )


@progress_bp.route('/summary/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_progress_summary(student_id: str):
    """
    Obtiene un resumen rápido del progreso de un estudiante.
    Versión ligera para dashboards y listas.
    
    Returns:
        {
            "student_id": str,
            "overall_progress": float,
            "activities_completed": int,
            "total_activities": int,
            "quizzes_passed": int,
            "average_quiz_score": float,
            "last_activity": str
        }
    """
    try:
        progress = progress_service.get_student_progress(student_id)
        
        breakdown = progress.get("activity_breakdown", {})
        recent = progress.get("recent_activity", [])
        
        summary = {
            "student_id": student_id,
            "overall_progress": progress.get("overall_progress", 0),
            "activities_completed": breakdown.get("completed_activities", 0),
            "total_activities": breakdown.get("total_activities", 0),
            "slides_viewed": breakdown.get("slides", {}).get("viewed", 0),
            "interactive_completed": breakdown.get("interactive", {}).get("completed", 0),
            "quizzes_passed": breakdown.get("quizzes", {}).get("passed", 0),
            "quizzes_total": breakdown.get("quizzes", {}).get("total", 0),
            "average_quiz_score": breakdown.get("quizzes", {}).get("average_score", 0),
            "last_activity": recent[0].get("recorded_at") if recent else None
        }
        
        return APIRoute.success(
            data=summary,
            message="Resumen de progreso obtenido exitosamente"
        )
        
    except Exception as e:
        return APIRoute.error(
            error_code="PROGRESS_ERROR",
            message=f"Error obteniendo resumen de progreso: {str(e)}",
            status_code=500
        )

