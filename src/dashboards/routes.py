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
from src.shared.decorators import (
    auth_required,
    role_required
)
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable
from src.shared.database import get_db
from src.shared.middleware import apply_workspace_filter, get_current_workspace_info

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
@auth_required
@role_required([ROLES["TEACHER"]])
@apply_workspace_filter('classes')
def get_teacher_dashboard():
    """Obtiene el dashboard para un profesor con métricas relevantes"""
    try:
        logger = logging.getLogger(__name__)
        
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Usar el ID del usuario autenticado por defecto
        teacher_id = request.user_id
        logger.info(f"Usuario autenticado con ID: {teacher_id}, workspace_type: {workspace_type}")
        
        # Para workspaces individuales de profesor, usar directamente el teacher_id
        if workspace_type == 'INDIVIDUAL_TEACHER':
            dashboard = teacher_dashboard_service.generate_individual_teacher_dashboard(
                teacher_id, workspace_info
            )
        else:
            # Para workspaces institucionales, permitir override administrativo
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
            
            dashboard = teacher_dashboard_service.generate_teacher_dashboard(
                teacher_id
            )
        
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el dashboard de profesor",
                status_code=500
            )
        logging.info(f"Dashboard generado: {dashboard}")
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
@auth_required
@role_required([ROLES["STUDENT"], ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('classes')
def get_student_dashboard(student_id):
    """Obtiene el dashboard para un estudiante con su progreso académico"""
    try:
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        # Para workspaces individuales de estudiante, validar que sea el propio estudiante
        if workspace_type == 'INDIVIDUAL_STUDENT':
            if student_id != request.user_id:
                return APIRoute.error(
                    ErrorCodes.FORBIDDEN,
                    "Solo puedes acceder a tu propio dashboard en workspace individual",
                    status_code=403
                )
        
        period_id = request.args.get('period_id')  # Opcional
        
        dashboard = student_dashboard_service.generate_student_dashboard(
            student_id, period_id
        )
        
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
@auth_required
@role_required([ROLES["INSTITUTE_ADMIN"]])
@apply_workspace_filter('institute')
def get_institute_dashboard(institute_id):
    """Obtiene un dashboard completo y detallado del instituto"""
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"Solicitando dashboard para instituto: {institute_id}")
        
        # Obtener información del workspace actual
        workspace_info = get_current_workspace_info()
        logger.info(f"Workspace info: {workspace_info}")
        
        # Validar que el ID sea válido
        try:
            ObjectId(institute_id)
        except Exception as e:
            logger.error(f"ID de instituto inválido: {institute_id}, error: {str(e)}")
            return APIRoute.error(
                ErrorCodes.INVALID_REQUEST,
                f"ID de instituto inválido: {institute_id}",
                status_code=400
            )
        
        # Validar que el usuario tenga acceso al instituto
        user_id = request.user_id
        db = get_db()
        
        # Verificar si el usuario es miembro del instituto como administrador
        # Primero verificar si es ADMIN del sistema (puede ver cualquier instituto)
        user = db.users.find_one({"_id": ObjectId(user_id)})
        is_system_admin = user and user.get("role") == ROLES["ADMIN"]
        
        if not is_system_admin:
            # Si no es admin del sistema, verificar si es miembro del instituto solicitado
            logger.info(f"Verificando membresía del usuario {user_id} en instituto {institute_id}")
            
            # Primero buscar todas las membresías del usuario para debugging
            all_memberships = list(db.institute_members.find({
                "user_id": ObjectId(user_id),
                "role": "INSTITUTE_ADMIN"
            }))
            logger.info(f"Usuario {user_id} tiene {len(all_memberships)} membresías como INSTITUTE_ADMIN")
            for membership in all_memberships:
                logger.info(f"  - Instituto: {membership.get('institute_id')}, Role: {membership.get('role')}")
            
            # Buscar membresía específica del instituto solicitado
            institute_member = db.institute_members.find_one({
                "user_id": ObjectId(user_id),
                "institute_id": ObjectId(institute_id),
                "role": "INSTITUTE_ADMIN"
            })
            
            if not institute_member:
                logger.warning(f"Usuario {user_id} no tiene acceso al instituto {institute_id}")
                logger.info(f"Workspace actual: {workspace_info.get('workspace_id')}, Institute solicitado: {institute_id}")
                logger.info(f"Institute ID del workspace: {workspace_info.get('institute_id')}")
                return APIRoute.error(
                    ErrorCodes.ACCESS_DENIED,
                    "No tienes acceso a este instituto",
                    status_code=403
                )
            else:
                logger.info(f"Membresía encontrada para usuario {user_id} en instituto {institute_id}")
        
        # Verificar que el instituto existe
        institute = db.institutes.find_one({"_id": ObjectId(institute_id)})
        if not institute:
            logger.warning(f"Instituto no encontrado: {institute_id}")
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Instituto no encontrado",
                status_code=404
            )
        
        # Obtener dashboard general
        dashboard = institute_dashboard_service.generate_institute_dashboard(
            institute_id
        )
        if not dashboard:
            logger.warning(f"No se encontraron datos para generar el dashboard del instituto: {institute_id}")
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "No se encontraron datos para generar el dashboard",
                status_code=404
            )
                
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error en get_institute_dashboard: {str(e)}\n{traceback.format_exc()}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Nuevos endpoints específicos para workspaces individuales

@dashboards_bp.route('/individual/student', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["STUDENT"]])
@apply_workspace_filter('classes')
def get_individual_student_dashboard():
    """Obtiene el dashboard personalizado para un estudiante en workspace individual"""
    try:
        workspace_info = get_current_workspace_info()
        if workspace_info.get('workspace_type') != 'INDIVIDUAL_STUDENT':
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "Esta ruta solo aplica a workspace individual de estudiante",
                status_code=403
            )
        student_id = request.user_id
        period_id = request.args.get('period_id')
        
        dashboard = student_dashboard_service.generate_individual_student_dashboard(
            student_id, workspace_info, period_id
        )
        
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el dashboard individual de estudiante",
                status_code=500
            )
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        logging.getLogger(__name__).error(f"Error en get_individual_student_dashboard: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@dashboards_bp.route('/individual/teacher', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
@apply_workspace_filter('classes')
def get_individual_teacher_dashboard():
    """Obtiene el dashboard personalizado para un profesor en workspace individual"""
    try:
        workspace_info = get_current_workspace_info()
        if workspace_info.get('workspace_type') != 'INDIVIDUAL_TEACHER':
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "Esta ruta solo aplica a workspace individual de profesor",
                status_code=403
            )
        teacher_id = request.user_id
        
        dashboard = teacher_dashboard_service.generate_individual_teacher_dashboard(
            teacher_id, workspace_info
        )
        
        if not dashboard:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el dashboard individual de profesor",
                status_code=500
            )
            
        return APIRoute.success(data={"dashboard": dashboard})
    except Exception as e:
        logging.getLogger(__name__).error(f"Error en get_individual_teacher_dashboard: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@dashboards_bp.route('/workspace/summary', methods=['GET'])
@auth_required
@apply_workspace_filter('workspace')
def get_workspace_summary():
    """Obtiene un resumen del workspace actual (funciona para todos los tipos)"""
    try:
        workspace_info = get_current_workspace_info()
        workspace_type = workspace_info.get('workspace_type')
        
        if workspace_type == 'INDIVIDUAL_STUDENT':
            summary = student_dashboard_service.generate_workspace_summary(
                request.user_id, workspace_info
            )
        elif workspace_type == 'INDIVIDUAL_TEACHER':
            summary = teacher_dashboard_service.generate_workspace_summary(
                request.user_id, workspace_info
            )
        else:  # INSTITUTE
            summary = institute_dashboard_service.generate_workspace_summary(
                workspace_info.get('institute_id'), workspace_info
            )
        
        if not summary:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "Error al generar el resumen del workspace",
                status_code=500
            )
            
        return APIRoute.success(data={"summary": summary})
    except Exception as e:
        logging.getLogger(__name__).error(f"Error en get_workspace_summary: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )