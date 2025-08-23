from flask import request
from flask_jwt_extended import get_jwt_identity, create_access_token, get_jwt
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.logging import log_error
from src.shared.decorators import (
    workspace_access_required, 
    workspace_owner_required, 
    workspace_type_required,
    auth_required,
    role_required
)
from src.shared.middleware import get_current_workspace_info
from src.members.services import MembershipService
from src.workspaces.services import WorkspaceService
from src.shared.database import get_db
from src.shared.constants import normalize_role
from src.study_plans.services import StudyPlanService

workspaces_bp = APIBlueprint('workspaces', __name__)
membership_service = MembershipService()
workspace_service = WorkspaceService()
study_plan_service = StudyPlanService()

@workspaces_bp.route('/', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_workspaces():
    try:
        user_id = get_jwt_identity()
        workspaces = membership_service.get_user_workspaces(user_id)
        
        # Enriquecer información de workspaces
        enriched_workspaces = []
        for workspace in workspaces:
            enriched_workspace = {
                "workspace_id": str(workspace["_id"]),
                "institute_id": str(workspace["institute_id"]),
                "workspace_type": workspace.get("workspace_type"),
                "workspace_name": workspace.get("workspace_name"),
                "role_in_workspace": normalize_role(workspace.get("role")),
                "status": workspace.get("status", "active"),
                "is_active": workspace.get("status") == "active",
                "joined_at": workspace.get("joined_at"),
                "class_id": str(workspace["class_id"]) if workspace.get("class_id") else None,
                "metadata": {
                    "institute_name": workspace.get("institute_name"),
                    "institute_description": workspace.get("institute_description")
                }
            }
            enriched_workspaces.append(enriched_workspace)
        
        return APIRoute.success(data={
            "workspaces": enriched_workspaces,
            "total_count": len(enriched_workspaces)
        })
    except Exception as e:
        log_error(f"Error listing workspaces: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudieron obtener los workspaces")

@workspaces_bp.route('/switch/<string:workspace_id>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def switch_workspace(workspace_id):
    try:
        user_id = get_jwt_identity()
        
        # Validar formato del workspace_id
        try:
            ObjectId(workspace_id)
        except:
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "ID de workspace inválido")
        
        # Buscar membresía del usuario en el workspace
        membership = membership_service.collection.find_one({
            "_id": ObjectId(workspace_id),
            "user_id": ObjectId(user_id),
            "status": "active"  # Solo workspaces activos
        })
        
        if not membership:
            return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Workspace no válido o inactivo")
        
        # Verificar que el workspace tiene la información necesaria
        if not membership.get("workspace_type") or not membership.get("workspace_name"):
            return APIRoute.error(ErrorCodes.SERVER_ERROR, "Workspace con información incompleta")
        
        # Crear claims para el nuevo token
        claims = {
            "workspace_id": workspace_id,
            "institute_id": str(membership["institute_id"]),
            "role": normalize_role(membership.get("role")),
            "workspace_type": membership.get("workspace_type"),
            "workspace_name": membership.get("workspace_name")
        }
        
        # Agregar class_id si existe
        if membership.get("class_id"):
            claims["class_id"] = str(membership["class_id"])
        
        # Crear nuevo token con claims del workspace
        token = create_access_token(identity=user_id, additional_claims=claims)
        
        # Respuesta con información del workspace activo
        workspace_info = {
            "workspace_id": workspace_id,
            "workspace_type": membership.get("workspace_type"),
            "workspace_name": membership.get("workspace_name"),
            "role_in_workspace": normalize_role(membership.get("role")),
            "institute_id": str(membership["institute_id"]),
            "class_id": str(membership["class_id"]) if membership.get("class_id") else None
        }
        
        return APIRoute.success(data={
            "token": token,
            "workspace": workspace_info,
            "message": f"Cambiado a workspace: {membership.get('workspace_name')}"
        })
        
    except Exception as e:
        log_error(f"Error switching workspace: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo cambiar de workspace")

@workspaces_bp.route('/<string:workspace_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
@workspace_access_required
def get_workspace_details(workspace_id):
    """
    Obtiene los detalles de un workspace específico
    """
    try:
        user_id = get_jwt_identity()
        
        # Obtener detalles del workspace (el acceso ya fue validado por el decorador)
        workspace_details = workspace_service.get_workspace_by_id(workspace_id, user_id)
        if not workspace_details:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Workspace no encontrado")
        
        return APIRoute.success(data=workspace_details)
        
    except Exception as e:
        log_error(f"Error getting workspace details: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudieron obtener los detalles del workspace")

@workspaces_bp.route('/personal', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def create_personal_workspace():
    """
    Crea un nuevo workspace personal para el usuario
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validar datos requeridos
        if not data or not data.get('workspace_name'):
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "El nombre del workspace es requerido")
        
        workspace_name = data['workspace_name'].strip()
        if not workspace_name:
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "El nombre del workspace no puede estar vacío")
        
        # Validar longitud del nombre
        if len(workspace_name) < 3 or len(workspace_name) > 50:
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "El nombre debe tener entre 3 y 50 caracteres")
        
        # Preparar datos del workspace
        workspace_data = {
            "workspace_name": workspace_name,
            "workspace_type": data.get("workspace_type", "INDIVIDUAL_STUDENT")  # Por defecto estudiante individual
        }
        
        # Crear el workspace personal
        success, message, response_data = workspace_service.create_personal_workspace(user_id, workspace_data)
        if not success:
            return APIRoute.error(ErrorCodes.SERVER_ERROR, message or "No se pudo crear el workspace personal")
        
        return APIRoute.success(
            data=response_data,
            message=message or "Workspace personal creado exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error creating personal workspace: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo crear el workspace personal")

@workspaces_bp.route('/<string:workspace_id>', methods=['PATCH'])
@APIRoute.standard(auth_required_flag=True)
@workspace_access_required
@workspace_owner_required
def update_workspace(workspace_id):
    """
    Actualiza la información de un workspace
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validar datos de actualización
        if not data:
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "No se proporcionaron datos para actualizar")
        
        # Actualizar workspace (acceso y permisos ya validados por decoradores)
        success, message, response_data = workspace_service.update_workspace_info(workspace_id, user_id, data)
        if not success:
            return APIRoute.error(ErrorCodes.SERVER_ERROR, message or "No se pudo actualizar el workspace")
        
        # Obtener detalles actualizados
        workspace_details = workspace_service.get_workspace_by_id(workspace_id, user_id)
        
        return APIRoute.success(
            data=workspace_details,
            message=message or "Workspace actualizado exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error updating workspace: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo actualizar el workspace")

# Nuevos endpoints específicos para workspaces individuales

@workspaces_bp.route('/<string:workspace_id>/study-plan', methods=['POST'])
@auth_required
@workspace_access_required
@workspace_type_required(['INDIVIDUAL_STUDENT'])
def create_study_plan(workspace_id):
    """
    Generar plan de estudio personalizado para INDIVIDUAL_STUDENT
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validar datos requeridos
        if not data or not data.get('description'):
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "La descripción es requerida")
        
        # Procesar archivo PDF si se proporciona
        pdf_file = request.files.get('pdf_file') if request.files else None
        
        # Crear plan de estudio
        success, message, study_plan_data = workspace_service.create_personal_study_plan(
            workspace_id=workspace_id,
            user_id=user_id,
            description=data['description'],
            objectives=data.get('objectives', []),
            pdf_file=pdf_file
        )
        
        if not success:
            return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
        
        return APIRoute.success(
            data=study_plan_data,
            message="Plan de estudio creado exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error creating study plan: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo crear el plan de estudio")

@workspaces_bp.route('/<string:workspace_id>/progress', methods=['GET'])
@auth_required
@workspace_access_required
def get_workspace_progress(workspace_id):
    """
    Obtener progreso específico del workspace individual
    """
    try:
        user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_type = jwt_claims.get('workspace_type')
        
        # Obtener progreso filtrado por workspace
        progress_data = workspace_service.get_workspace_progress(
            workspace_id=workspace_id,
            user_id=user_id,
            workspace_type=workspace_type
        )
        
        return APIRoute.success(data=progress_data)
        
    except Exception as e:
        log_error(f"Error getting workspace progress: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo obtener el progreso")

@workspaces_bp.route('/<string:workspace_id>/summary', methods=['GET'])
@auth_required
@workspace_access_required
def get_workspace_summary(workspace_id):
    """
    Obtener resumen general del workspace
    """
    try:
        user_id = get_jwt_identity()
        workspace_info = get_current_workspace_info()
        
        # Obtener resumen del workspace
        summary_data = workspace_service.get_workspace_summary(
            workspace_id=workspace_id,
            user_id=user_id,
            workspace_info=workspace_info
        )
        
        return APIRoute.success(data=summary_data)
        
    except Exception as e:
        log_error(f"Error getting workspace summary: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo obtener el resumen del workspace")

@workspaces_bp.route('/<string:workspace_id>/individual/teacher/classes', methods=['GET'])
@auth_required
@workspace_access_required
@workspace_type_required(['INDIVIDUAL_TEACHER'])
def get_individual_teacher_classes(workspace_id):
    """
    Obtener clases específicas para profesor en workspace individual
    """
    try:
        user_id = get_jwt_identity()
        workspace_info = get_current_workspace_info()
        
        # Validar que el usuario es el propietario del workspace
        if user_id != workspace_info.get('user_id'):
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "Solo puedes acceder a tus propias clases en workspace individual"
            )
        
        # Obtener clases del profesor individual
        classes_data = workspace_service.get_individual_teacher_classes(
            workspace_id=workspace_id,
            teacher_id=user_id,
            workspace_info=workspace_info
        )
        
        return APIRoute.success(data=classes_data)
        
    except Exception as e:
        log_error(f"Error getting individual teacher classes: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudieron obtener las clases del profesor")

@workspaces_bp.route('/<string:workspace_id>/individual/student/study-plans', methods=['GET'])
@auth_required
@workspace_access_required
@workspace_type_required(['INDIVIDUAL_STUDENT'])
def get_individual_student_study_plans(workspace_id):
    """
    Obtener planes de estudio específicos para estudiante en workspace individual
    """
    try:
        user_id = get_jwt_identity()
        workspace_info = get_current_workspace_info()
        
        # Validar que el usuario es el propietario del workspace
        if user_id != workspace_info.get('user_id'):
            return APIRoute.error(
                ErrorCodes.FORBIDDEN,
                "Solo puedes acceder a tus propios planes de estudio en workspace individual"
            )
        
        # Obtener planes de estudio del estudiante individual
        study_plans_data = workspace_service.get_individual_student_study_plans(
            workspace_id=workspace_id,
            student_id=user_id,
            workspace_info=workspace_info
        )
        
        return APIRoute.success(data=study_plans_data)
        
    except Exception as e:
        log_error(f"Error getting individual student study plans: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudieron obtener los planes de estudio del estudiante")

# Rutas para recursos personales del workspace
@workspaces_bp.route('/<string:workspace_id>/personal-study-plans', methods=['GET','POST','OPTIONS'])
@auth_required
@workspace_access_required
def personal_study_plans(workspace_id):
    """
    Gestionar planes de estudio personales del workspace
    """
    try:
        user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_type = jwt_claims.get('workspace_type')
        
        if request.method == 'GET':
            # Obtener planes de estudio personales (unificados)
            study_plans = workspace_service.get_personal_study_plans(
                workspace_id=workspace_id,
                user_id=user_id,
                workspace_type=workspace_type
            )
            return APIRoute.success(data=study_plans)
            
        elif request.method == 'POST':
            # Crear nuevo plan de estudio personal
            data = request.get_json()
            if not data or not data.get('title'):
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "El título del plan es requerido")
            
            success, message, plan_data = workspace_service.create_personal_study_plan_with_title(
                workspace_id=workspace_id,
                user_id=user_id,
                title=data['title'],
                description=data.get('description', ''),
                objectives=data.get('objectives', []),
                pdf_file=request.files.get('pdf_file') if request.files else None
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(data=plan_data, message="Plan de estudio personal creado exitosamente")
            
        elif request.method == 'OPTIONS':
            # Manejar preflight request para CORS
            return APIRoute.success(data={}, message="OK")
            
    except Exception as e:
        log_error(f"Error in personal study plans: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo procesar la solicitud")

# Endpoints unificados para acceder a planes del workspace
@workspaces_bp.route('/<string:workspace_id>/study-plans', methods=['GET'])
@auth_required
@workspace_access_required
def list_workspace_study_plans(workspace_id):
    """Lista planes personales del workspace desde la colección unificada"""
    try:
        user_id = get_jwt_identity()
        plans = study_plan_service.list_personal_study_plans_by_workspace(workspace_id, user_id)
        return APIRoute.success(data={"study_plans_per_subject": plans, "total_count": len(plans)})
    except Exception as e:
        log_error(f"Error listing workspace study plans: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudieron listar los planes del workspace")

@workspaces_bp.route('/<string:workspace_id>/study-plans/<string:study_plan_id>', methods=['GET'])
@auth_required
@workspace_access_required
def get_workspace_study_plan(workspace_id, study_plan_id):
    """
    Obtiene un plan de estudio específico del workspace unificado
    """
    try:
        plan = study_plan_service.get_study_plan(study_plan_id)
        if not plan:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Plan de estudio no encontrado")
        
        # Verificar que pertenece al workspace (solo para planes personales)
        if plan.get("is_personal") and str(plan.get("workspace_id")) != str(workspace_id):
            return APIRoute.error(ErrorCodes.FORBIDDEN, "Plan no pertenece a este workspace")
        
        return APIRoute.success(data=plan)
    except Exception as e:
        log_error(f"Error getting workspace study plan: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo obtener el plan de estudio")

@workspaces_bp.route('/<string:workspace_id>/study-goals', methods=['GET','POST','PUT','DELETE','OPTIONS'])
@auth_required
@workspace_access_required
def study_goals(workspace_id):
    """
    Gestionar objetivos de estudio del workspace
    """
    try:
        user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_type = jwt_claims.get('workspace_type')
        
        if request.method == 'GET':
            # Obtener objetivos de estudio
            goals = workspace_service.get_study_goals(
                workspace_id=workspace_id,
                user_id=user_id,
                workspace_type=workspace_type
            )
            return APIRoute.success(data=goals)
            
        elif request.method == 'POST':
            # Crear nuevo objetivo de estudio
            data = request.get_json()
            if not data or not data.get('title'):
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "El título del objetivo es requerido")
            
            success, message, goal_data = workspace_service.create_study_goal(
                workspace_id=workspace_id,
                user_id=user_id,
                title=data['title'],
                description=data.get('description', ''),
                target_date=data.get('target_date'),
                priority=data.get('priority', 'medium')
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(data=goal_data, message="Objetivo de estudio creado exitosamente")
            
        elif request.method == 'PUT':
            # Actualizar objetivo de estudio
            data = request.get_json()
            goal_id = data.get('goal_id')
            if not goal_id:
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "ID del objetivo es requerido")
            
            success, message, goal_data = workspace_service.update_study_goal(
                workspace_id=workspace_id,
                user_id=user_id,
                goal_id=goal_id,
                update_data=data
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(data=goal_data, message="Objetivo de estudio actualizado exitosamente")
            
        elif request.method == 'DELETE':
            # Eliminar objetivo de estudio
            goal_id = request.args.get('goal_id')
            if not goal_id:
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "ID del objetivo es requerido")
            
            success, message = workspace_service.delete_study_goal(
                workspace_id=workspace_id,
                user_id=user_id,
                goal_id=goal_id
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(message="Objetivo de estudio eliminado exitosamente")
            
        elif request.method == 'OPTIONS':
            # Manejar preflight request para CORS
            return APIRoute.success(data={}, message="OK")
            
    except Exception as e:
        log_error(f"Error in personal study plans: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo procesar la solicitud")

@workspaces_bp.route('/<string:workspace_id>/personal-resources', methods=['GET','POST','PUT','DELETE','OPTIONS'])
@auth_required
@workspace_access_required
def personal_resources(workspace_id):
    """
    Gestionar recursos personales del workspace
    """
    try:
        user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        workspace_type = jwt_claims.get('workspace_type')
        
        if request.method == 'GET':
            # Obtener recursos personales
            resources = workspace_service.get_personal_resources(
                workspace_id=workspace_id,
                user_id=user_id,
                workspace_type=workspace_type
            )
            return APIRoute.success(data=resources)
            
        elif request.method == 'POST':
            # Crear nuevo recurso personal
            data = request.get_json()
            if not data or not data.get('title'):
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "El título del recurso es requerido")
            
            success, message, resource_data = workspace_service.create_personal_resource(
                workspace_id=workspace_id,
                user_id=user_id,
                title=data['title'],
                description=data.get('description', ''),
                resource_type=data.get('resource_type', 'document'),
                url=data.get('url'),
                file=request.files.get('file') if request.files else None
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(data=resource_data, message="Recurso personal creado exitosamente")
            
        elif request.method == 'PUT':
            # Actualizar recurso personal
            data = request.get_json()
            resource_id = data.get('resource_id')
            if not resource_id:
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "ID del recurso es requerido")
            
            success, message, resource_data = workspace_service.update_personal_resource(
                workspace_id=workspace_id,
                user_id=user_id,
                resource_id=resource_id,
                update_data=data
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(data=resource_data, message="Recurso personal actualizado exitosamente")
            
        elif request.method == 'DELETE':
            # Eliminar recurso personal
            resource_id = request.args.get('resource_id')
            if not resource_id:
                return APIRoute.error(ErrorCodes.BAD_REQUEST, "ID del recurso es requerido")
            
            success, message = workspace_service.delete_personal_resource(
                workspace_id=workspace_id,
                user_id=user_id,
                resource_id=resource_id
            )
            
            if not success:
                return APIRoute.error(ErrorCodes.SERVER_ERROR, message)
            
            return APIRoute.success(message="Recurso personal eliminado exitosamente")
            
        elif request.method == 'OPTIONS':
            # Manejar preflight request para CORS
            return APIRoute.success(data={}, message="OK")
            
    except Exception as e:
        log_error(f"Error in personal resources: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo procesar la solicitud")
