from flask_jwt_extended import get_jwt_identity, create_access_token
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.logging import log_error
from src.members.services import MembershipService

workspaces_bp = APIBlueprint('workspaces', __name__)
membership_service = MembershipService()

@workspaces_bp.route('/', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_workspaces():
    try:
        user_id = get_jwt_identity()
        workspaces = membership_service.get_user_workspaces(user_id)
        return APIRoute.success(data={"workspaces": workspaces})
    except Exception as e:
        log_error(f"Error listing workspaces: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudieron obtener los workspaces")

@workspaces_bp.route('/switch/<workspace_id>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def switch_workspace(workspace_id):
    try:
        user_id = get_jwt_identity()
        membership = membership_service.collection.find_one({
            "_id": ObjectId(workspace_id),
            "user_id": ObjectId(user_id)
        })
        if not membership:
            return APIRoute.error(ErrorCodes.UNAUTHORIZED, "Workspace no válido")

        claims = {
            "workspace_id": workspace_id,
            "institute_id": str(membership["institute_id"]),
            "role": membership.get("role")
        }
        token = create_access_token(identity=user_id, additional_claims=claims)
        return APIRoute.success(data={"token": token})
    except Exception as e:
        log_error(f"Error switching workspace: {str(e)}", e, "workspaces.routes")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "No se pudo cambiar de workspace")
