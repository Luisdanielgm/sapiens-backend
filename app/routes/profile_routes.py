from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.db_profiles import (
    get_teacher_profile,
    update_teacher_profile,
    get_student_profile,
    update_student_profile
)

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile/teacher', methods=['GET'])
@handle_errors
def get_teacher_profile_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del profesor"}), 400

    profile, error = get_teacher_profile(email)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"profile": profile}), 200

@profile_bp.route('/profile/teacher/update', methods=['PUT'])
@handle_errors
def update_teacher_profile_endpoint():
    data = request.get_json()
    email = data.get('email')
    profile_data = data.get('profile')

    if not email or not profile_data:
        return jsonify({"error": "Se requieren email y datos del perfil"}), 400

    success, message = update_teacher_profile(email, profile_data)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@profile_bp.route('/profile/student', methods=['GET'])
@handle_errors
def get_student_profile_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    profile, error = get_student_profile(email)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"profile": profile}), 200

@profile_bp.route('/profile/student/update', methods=['PUT'])
@handle_errors
def update_student_profile_endpoint():
    data = request.get_json()
    email = data.get('email')
    profile_data = data.get('profile')

    if not email or not profile_data:
        return jsonify({"error": "Se requieren email y datos del perfil"}), 400

    success, message = update_student_profile(email, profile_data)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400 