from flask_jwt_extended import get_jwt_identity, create_access_token
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.logging import log_error
from src.members.services import MembershipService
from src.shared.database import get_db

workspaces_bp = APIBlueprint('workspaces', __name__)
membership_service = MembershipService()

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
                "role_in_workspace": workspace.get("role"),
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
            "role": membership.get("role"),
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
            "role_in_workspace": membership.get("role"),
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
