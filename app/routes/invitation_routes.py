from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.db_classrom import (
    invite_user_to_classroom,
    accept_invitation,
    reject_invitation,
    get_user_pending_invitations
)

invitation_bp = Blueprint('invitation', __name__)

@invitation_bp.route('/user/invite', methods=['POST'])
@handle_errors
def invite_user_endpoint():
    data = request.json
    email = data.get('email')
    classroom_id = data.get('classroomId')
    invitee_email = data.get('inviteeEmail')

    if not all([email, classroom_id, invitee_email]):
        return jsonify({"error": "Faltan parámetros requeridos"}), 400

    try:
        success, message = invite_user_to_classroom(email, classroom_id, invitee_email)
        if success:
            return jsonify({"message": message}), 200
        return jsonify({"error": message}), 400
    except Exception as e:
        return jsonify({"error": f"Error al enviar la invitación: {str(e)}"}), 500

@invitation_bp.route('/user/invitations', methods=['GET'])
@handle_errors
def get_user_invitations():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    try:
        invitations = get_user_pending_invitations(email)
        return jsonify({"invitations": invitations}), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener invitaciones: {str(e)}"}), 500

@invitation_bp.route('/invitations/accept', methods=['POST'])
@handle_errors
def accept_classroom_invitation():
    data = request.json
    email = data.get('email')
    invitation_id = data.get('invitation_id')

    if not email or not invitation_id:
        return jsonify({"error": "Se requieren email e invitation_id"}), 400

    try:
        success = accept_invitation(email, invitation_id)
        if success:
            return jsonify({"message": "Invitación aceptada exitosamente"}), 200
        return jsonify({"error": "No se pudo aceptar la invitación"}), 400
    except Exception as e:
        return jsonify({"error": f"Error al aceptar la invitación: {str(e)}"}), 500

@invitation_bp.route('/invitations/reject', methods=['POST'])
@handle_errors
def reject_classroom_invitation():
    data = request.json
    email = data.get('email')
    invitation_id = data.get('invitation_id')

    if not email or not invitation_id:
        return jsonify({"error": "Se requieren email e invitation_id"}), 400

    try:
        success = reject_invitation(email, invitation_id)
        if success:
            return jsonify({"message": "Invitación rechazada exitosamente"}), 200
        return jsonify({"error": "No se pudo rechazar la invitación"}), 400
    except Exception as e:
        return jsonify({"error": f"Error al rechazar la invitación: {str(e)}"}), 500 