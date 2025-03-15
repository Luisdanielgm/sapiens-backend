from flask import request
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId

from src.shared.constants import ROLES
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.exceptions import AppException
from .services import MembershipService

members_bp = APIBlueprint('members', __name__)
membership_service = MembershipService()

# ========== INSTITUTO MEMBERS ==========
@members_bp.route('/institute/<institute_id>/members', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_institute_members(institute_id):
    """Obtener todos los miembros de un instituto"""
    role = request.args.get('role')
    members = membership_service.get_institute_members(institute_id, role)
    return APIRoute.success(data={"members": members})

@members_bp.route('/institute/<institute_id>/members', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]],
    required_fields=['user_id', 'role']
)
def add_institute_member(institute_id):
    """Añadir un nuevo miembro al instituto"""
    data = request.get_json()
    data['institute_id'] = institute_id
    
    member_id = membership_service.add_institute_member(data)
    return APIRoute.success(
        data={"member_id": member_id},
        message="Miembro añadido correctamente",
        status_code=201
    )

@members_bp.route('/institute/<institute_id>/members/<member_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]]
)
def update_institute_member(institute_id, member_id):
    """Actualizar un miembro del instituto"""
    data = request.get_json()
    membership_service.update_institute_member(member_id, data)
    return APIRoute.success(message="Miembro actualizado correctamente")

@members_bp.route('/institute/<institute_id>/members/<user_id>', methods=['DELETE'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["INSTITUTE_ADMIN"]]
)
def remove_institute_member(institute_id, user_id):
    """Eliminar un miembro del instituto"""
    membership_service.remove_institute_member(institute_id, user_id)
    return APIRoute.success(message="Miembro eliminado correctamente")

# ========== CLASS MEMBERS ==========
@members_bp.route('/class/<class_id>/members', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_class_members(class_id):
    """Obtener todos los miembros de una clase"""
    role = request.args.get('role')
    members = membership_service.get_class_members(class_id, role)
    return APIRoute.success(data={"members": members})

@members_bp.route('/class/<class_id>/members', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]],
    required_fields=['user_id', 'role']
)
def add_class_member(class_id):
    """Añadir un nuevo miembro a la clase"""
    data = request.get_json()
    data['class_id'] = class_id
    
    success, result = membership_service.add_class_member(data)
    if success:
        return APIRoute.success(
            data={"member_id": result},
            message="Miembro añadido correctamente", 
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.MEMBER_ADD_ERROR,
        result,
        status_code=400
    )

@members_bp.route('/class/<class_id>/members/by-email', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]],
    required_fields=['email', 'role']
)
def add_class_member_by_email(class_id):
    """Añadir un nuevo miembro a la clase usando su email"""
    data = request.get_json()
    data['class_id'] = class_id
    
    success, result = membership_service.add_class_member_by_email(data)
    if success:
        return APIRoute.success(
            data={"member_id": result},
            message="Miembro añadido correctamente", 
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.MEMBER_ADD_ERROR,
        result,
        status_code=400
    )

@members_bp.route('/class/<class_id>/members/<member_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def update_class_member(class_id, member_id):
    """Actualizar un miembro de la clase"""
    data = request.get_json()
    success, message = membership_service.update_class_member(member_id, data)
    if success:
        return APIRoute.success(message="Miembro actualizado correctamente")
    return APIRoute.error(
        ErrorCodes.MEMBER_UPDATE_ERROR,
        message,
        status_code=400
    )

@members_bp.route('/class/<class_id>/members/<user_id>', methods=['DELETE'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def remove_class_member(class_id, user_id):
    """Eliminar un miembro de la clase"""
    success, message = membership_service.remove_class_member(class_id, user_id)
    if success:
        return APIRoute.success(message="Miembro eliminado correctamente")
    return APIRoute.error(
        ErrorCodes.MEMBER_DELETE_ERROR,
        message,
        status_code=400
    )

@members_bp.route('/user/institutes', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_institutes():
    """Obtener todos los institutos a los que pertenece el usuario actual"""
    user_id = get_jwt_identity()
    institutes = membership_service.get_user_institutes(user_id)
    return APIRoute.success(data={"institutes": institutes})

@members_bp.route('/user/classes', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_user_classes():
    """Obtener todas las clases a las que pertenece el usuario actual"""
    user_id = get_jwt_identity()
    classes = membership_service.get_user_classes(user_id)
    return APIRoute.success(data={"classes": classes}) 