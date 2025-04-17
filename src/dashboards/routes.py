from flask import request, jsonify
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .services import (
    AdminDashboardService,
    TeacherDashboardService,
    StudentDashboardService,
    InstituteDashboardService
)
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.decorators import auth_required, role_required, handle_errors
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable
from src.shared.database import get_db

dashboards_bp = APIBlueprint('dashboards', __name__)

admin_dashboard_service = AdminDashboardService()
teacher_dashboard_service = TeacherDashboardService()
student_dashboard_service = StudentDashboardService()
institute_dashboard_service = InstituteDashboardService()

@dashboards_bp.route('/admin', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
def get_admin_dashboard():
    """Obtiene un dashboard completo para el administrador del sistema"""
    try:
        dashboard = admin_dashboard_service.generate_admin_dashboard()
        
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el dashboard de administrador",
                status_code=500
            )
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        import traceback
        logging.getLogger(__name__).error(f"Error en get_admin_dashboard: {str(e)}\n{traceback.format_exc()}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 

@dashboards_bp.route('/teacher', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def get_teacher_dashboard():
    """Obtiene el dashboard para un profesor con métricas relevantes"""
    try:
        logger = logging.getLogger(__name__)
        
        # Usar el ID del usuario autenticado por defecto
        teacher_id = request.user_id
        logger.info(f"Usuario autenticado con ID: {teacher_id}")
        
        # Opcionalmente permitir sobrescribir para propósitos administrativos
        # (esto solo funcionaría si el usuario tiene permisos de admin pero aún está protegido por roles)
        override_id = request.args.get('teacher_id')
        if override_id:
            logger.info(f"Solicitando override con ID: {override_id}")
            # Verificar si el usuario autenticado es administrador
            db = get_db()
            user = db.users.find_one({"_id": ObjectId(teacher_id)})
            logger.info(f"Información del usuario: {user}")
            is_admin = user and user.get("role") in [ROLES["ADMIN"], ROLES["INSTITUTE_ADMIN"]]
            logger.info(f"¿Es admin? {is_admin}")
            
            if is_admin:
                teacher_id = override_id
                logger.info(f"Override aceptado, usando ID: {teacher_id}")
        
        dashboard = teacher_dashboard_service.generate_teacher_dashboard(teacher_id)
        
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el dashboard de profesor",
                status_code=500
            )
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        import traceback
        logging.getLogger(__name__).error(f"Error en get_teacher_dashboard: {str(e)}\n{traceback.format_exc()}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@dashboards_bp.route('/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_dashboard(student_id):
    """Obtiene el dashboard para un estudiante con su progreso académico"""
    try:
        period_id = request.args.get('period_id')  # Opcional
        
        dashboard = student_dashboard_service.generate_student_dashboard(student_id, period_id)
        
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el dashboard de estudiante",
                status_code=500
            )
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@dashboards_bp.route('/institute/<institute_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def get_institute_dashboard(institute_id):
    """Obtiene un dashboard completo y detallado del instituto"""
    try:
        # Obtener dashboard general
        dashboard = institute_dashboard_service.generate_institute_dashboard(institute_id)
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "No se encontraron datos para generar el dashboard",
                status_code=404
            )
                
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 