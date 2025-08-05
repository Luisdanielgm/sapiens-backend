from flask import request
from flask_jwt_extended import get_jwt_identity, create_access_token, get_jwt
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.logging import log_error
from src.shared.decorators import workspace_access_required, workspace_owner_required, workspace_type_required
from src.members.services import MembershipService
from src.workspaces.services import WorkspaceService
from src.shared.database import get_db
from src.shared.constants import normalize_role

workspaces_bp = APIBlueprint('workspaces', __name__)
membership_service = MembershipService()
workspace_service = WorkspaceService()

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

@workspaces_bp.route('/switch/<workspace_id>', methods=['POST'])
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

@workspaces_bp.route('/<workspace_id>', methods=['GET'])
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

@workspaces_bp.route('/<workspace_id>', methods=['PATCH'])
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
            message="Workspace actualizado exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error updating workspace: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo actualizar el workspace")

@workspaces_bp.route('/<workspace_id>/study-plan', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@workspace_access_required
@workspace_type_required('INDIVIDUAL')
def create_study_plan(workspace_id):
    """
    Crea un plan de estudio para un workspace individual de estudiante
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validar datos del plan de estudio
        if not data or not data.get('study_plan_data'):
            return APIRoute.error(ErrorCodes.BAD_REQUEST, "Los datos del plan de estudio son requeridos")
        
        # Crear el plan de estudio (acceso y tipo ya validados por decoradores)
        success, message, response_data = workspace_service.create_study_plan_for_workspace(workspace_id, user_id, data['study_plan_data'])
        if not success:
            return APIRoute.error(ErrorCodes.SERVER_ERROR, message or "No se pudo crear el plan de estudio")
        
        return APIRoute.success(
            data=response_data,
            message=message or "Plan de estudio creado exitosamente"
        )
        
    except Exception as e:
        log_error(f"Error creating study plan: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo crear el plan de estudio")
