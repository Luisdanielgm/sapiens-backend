from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.institute.db_members import (
    invite_to_institute,
    get_institute_pending_invitations,
    accept_institute_invitation,
    reject_institute_invitation,
    get_institute_members,
    get_user_institutes
)

# Definir los endpoints fuera de la función de registro
@handle_errors
def invite_to_institute_endpoint():
    """Registra una invitación a un instituto"""
    data = request.get_json()
    required_fields = ['admin_email', 'invitee_email', 'institute_id', 'role']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    success, message = invite_to_institute(
        data['admin_email'],
        data['invitee_email'],
        data['institute_id'],
        data['role']
    )

    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def get_institute_invitations_endpoint():
    """Obtiene las invitaciones pendientes de un instituto"""
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    invitations = get_institute_pending_invitations(email)
    return jsonify({"invitations": invitations}), 200

@handle_errors
def accept_institute_invitation_endpoint():
    """Acepta una invitación a un instituto"""
    data = request.get_json()
    email = data.get('email')
    invitation_id = data.get('invitation_id')

    if not email or not invitation_id:
        return jsonify({"error": "Se requieren email e invitation_id"}), 400

    success, message = accept_institute_invitation(email, invitation_id)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def reject_institute_invitation_endpoint():
    """Rechaza una invitación a un instituto"""
    data = request.get_json()
    email = data.get('email')
    invitation_id = data.get('invitation_id')

    if not email or not invitation_id:
        return jsonify({"error": "Se requieren email e invitation_id"}), 400

    success, message = reject_institute_invitation(email, invitation_id)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def get_institute_members_endpoint():
    """Obtiene los miembros de un instituto"""
    institute_id = request.args.get('institute_id')
    if not institute_id:
        return jsonify({"error": "Se requiere el ID del instituto"}), 400

    members = get_institute_members(institute_id)
    print(f"Members: {members}")
    return jsonify({"members": members}), 200

@handle_errors
def get_user_institutes_endpoint():
    """Obtiene los institutos asociados a un usuario"""
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    institutes = get_user_institutes(email)
    return jsonify({"institutes": institutes}), 200

def register_member_routes(bp):
    """Registra las rutas relacionadas con miembros del instituto"""
    bp.add_url_rule(
        '/institute/invite',
        'invite_to_institute',
        invite_to_institute_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/institute/invitations',
        'get_institute_invitations',
        get_institute_invitations_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/institute/invitations/accept',
        'accept_institute_invitation',
        accept_institute_invitation_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/institute/invitations/reject',
        'reject_institute_invitation',
        reject_institute_invitation_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/institute/members',
        'get_institute_members',
        get_institute_members_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/user/institutes',
        'get_user_institutes',
        get_user_institutes_endpoint,
        methods=['GET']
    ) 