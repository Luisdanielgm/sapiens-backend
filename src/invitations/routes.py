from flask import request
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId, errors

from src.shared.constants import ROLES
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.exceptions import AppException
from .services import InvitationService

invitations_bp = APIBlueprint('invitations', __name__)
invitation_service = InvitationService()

# ========== INSTITUTO INVITATIONS ==========
@invitations_bp.route('/institute/<institute_id>/invitations', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]]
)
def get_institute_invitations(institute_id):
    """Obtener todas las invitaciones de un instituto"""
    status = request.args.get('status')
    invitations = invitation_service.get_institute_invitations(institute_id, status)
    return APIRoute.success(data={"invitations": invitations})

@invitations_bp.route('/institute/<institute_id>/invitations', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]],
    required_fields=['invitee_email', 'role']
)
def create_institute_invitation(institute_id):
    """Crear una invitación para unirse a un instituto"""
    data = request.get_json()
    data['institute_id'] = institute_id
    data['inviter_id'] = get_jwt_identity()
    
    success, result = invitation_service.create_institute_invitation(data)
    if success:
        return APIRoute.success(
            data={"invitation_id": result},
            message="Invitación creada exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.OPERATION_FAILED,
        result,
        status_code=400
    )

@invitations_bp.route('/institute/invitations/<invitation_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['action']
)
def process_institute_invitation(invitation_id):
    """Procesar una invitación a instituto (aceptar/rechazar)"""
    data = request.get_json()
    user_id = get_jwt_identity()
    
    # Verificar si la invitación está dirigida a este usuario
    invitation = invitation_service.get_invitation_by_id(invitation_id)
    if not invitation:
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Invitación no encontrada",
            status_code=404
        )
    
    # Obtener email del usuario
    user_profile = invitation_service.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_profile or user_profile.get('email') != invitation.get('invitee_email'):
        return APIRoute.error(
            ErrorCodes.UNAUTHORIZED,
            "No estás autorizado para procesar esta invitación",
            status_code=403
        )
    
    success, message = invitation_service.process_institute_invitation(
        invitation_id, 
        user_id, 
        data.get('action')
    )
    
    if success:
        return APIRoute.success(message=message)
    return APIRoute.error(
        ErrorCodes.PROCESSING_ERROR,
        message,
        status_code=400
    )

# ========== CLASS INVITATIONS ==========
@invitations_bp.route('/class/<class_id>/invitations', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def get_class_invitations(class_id):
    """Obtener todas las invitaciones de una clase"""
    status = request.args.get('status')
    invitations = invitation_service.get_class_invitations(class_id, status)
    return APIRoute.success(data={"invitations": invitations})

@invitations_bp.route('/class/<class_id>/invitations', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]],
    required_fields=['invitee_email', 'role']
)
def create_class_invitation(class_id):
    """Crear una invitación para unirse a una clase"""
    data = request.get_json()
    data['class_id'] = class_id
    data['inviter_id'] = get_jwt_identity()
    
    success, result = invitation_service.create_class_invitation(data)
    if success:
        return APIRoute.success(
            data={"invitation_id": result},
            message="Invitación creada exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.OPERATION_FAILED,
        result,
        status_code=400
    )

@invitations_bp.route('/class/invitations/<invitation_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['action']
)
def process_class_invitation(invitation_id):
    """Procesar una invitación a clase (aceptar/rechazar)"""
    data = request.get_json()
    user_id = get_jwt_identity()
    
    # Verificar si la invitación está dirigida a este usuario
    invitation = invitation_service.get_invitation_by_id(invitation_id, "class_invitations")
    if not invitation:
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Invitación no encontrada",
            status_code=404
        )
    
    # Obtener email del usuario
    user_profile = invitation_service.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_profile or user_profile.get('email') != invitation.get('invitee_email'):
        return APIRoute.error(
            ErrorCodes.UNAUTHORIZED,
            "No estás autorizado para procesar esta invitación",
            status_code=403
        )
    
    success, message = invitation_service.process_class_invitation(
        invitation_id, 
        user_id, 
        data.get('action')
    )
    
    if success:
        return APIRoute.success(message=message)
    return APIRoute.error(
        ErrorCodes.PROCESSING_ERROR,
        message,
        status_code=400
    )

# ========== MEMBERSHIP REQUESTS ==========
@invitations_bp.route('/institute/<institute_id>/requests', methods=['GET'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]]
)
def get_membership_requests(institute_id):
    """Obtener todas las solicitudes de membresía de un instituto"""
    status = request.args.get('status')
    requests = invitation_service.get_membership_requests(institute_id, status)
    return APIRoute.success(data={"requests": requests})

@invitations_bp.route('/institute/<institute_id>/requests', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['requested_role']
)
def create_membership_request(institute_id):
    """Crear una solicitud para unirse a un instituto"""
    data = request.get_json()
    data['institute_id'] = institute_id
    data['user_id'] = get_jwt_identity()
    
    success, result = invitation_service.create_membership_request(data)
    if success:
        return APIRoute.success(
            data={"request_id": result},
            message="Solicitud creada exitosamente",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.OPERATION_FAILED,
        result,
        status_code=400
    )

@invitations_bp.route('/institute/requests/<request_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]],
    required_fields=['action']
)
def process_membership_request(request_id):
    """Procesar una solicitud de membresía (aprobar/rechazar)"""
    data = request.get_json()
    action = data.get('action')
    
    success, message = invitation_service.process_membership_request(request_id, action)
    if success:
        return APIRoute.success(message=message)
    return APIRoute.error(
        ErrorCodes.PROCESSING_ERROR,
        message,
        status_code=400
    )

# ========== USER INVITATIONS ==========
@invitations_bp.route('/user/invitations', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_invitations():
    """Obtener todas las invitaciones pendientes para el usuario actual"""
    user_id = get_jwt_identity()
    
    # Obtener email del usuario
    user = invitation_service.db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Usuario no encontrado",
            status_code=404
        )
        
    invitations = invitation_service.get_user_invitations(user.get('email', ''))
    return APIRoute.success(data=invitations) 