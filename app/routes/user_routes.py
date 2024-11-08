from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors, serialize_doc
from database.db_user import (
    verify_user_exists, 
    register_user, 
    get_user_by_email,
    search_users_by_partial_email,
    delete_student
)
from database.cognitive_profile import get_cognitive_profile, update_cognitive_profile
import json

user_bp = Blueprint('user', __name__)

@user_bp.route('/users/check', methods=['POST'])
def verify_user_endpoint():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    picture = data.get('picture')

    if not email or not name or not picture:
        return jsonify({'error': 'Missing required fields'}), 400

    user_exists = verify_user_exists(email)
    return jsonify({'userExists': user_exists}), 200

@user_bp.route('/users/register', methods=['POST'])
def register_user_endpoint():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    picture = data.get('picture')
    birth_date = data.get('birthDate')
    classroom_name = data.get('classroomName')
    role = data.get('role')

    if not all([email, name, picture, birth_date, role, classroom_name]):
        return jsonify({'error': 'Missing required fields'}), 400

    result = register_user(email, name, picture, birth_date, role, classroom_name)
    
    if result:
        return jsonify({'message': 'User registered successfully'}), 200
    return jsonify({'error': 'Failed to register user'}), 500

@user_bp.route('/users/search', methods=['GET'])
@handle_errors
def search_users():
    partial_email = request.args.get('email')
    if not partial_email or '@' not in partial_email:
        return jsonify({"error": "Correo electrónico inválido"}), 400

    suggestions = search_users_by_partial_email(partial_email)
    return jsonify({"suggestions": suggestions}), 200

@user_bp.route('/user/info', methods=['GET'])
@handle_errors
def get_user_info():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    try:
        user = get_user_by_email(email)
        if user:
            user_data = serialize_doc(user)
            return jsonify({"user": user_data}), 200
        return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener información del usuario: {str(e)}"}), 500

@user_bp.route('/student/delete', methods=['DELETE'])
@handle_errors
def delete_student_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    success, message = delete_student(email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@user_bp.route('/user/cognitive-profile', methods=['GET'])
@handle_errors
def get_user_cognitive_profile():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del usuario"}), 400

    try:
        profile = get_cognitive_profile(email)
        if profile:
            return jsonify({"profile": profile}), 200
        return jsonify({"error": "No se encontró el perfil cognitivo"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener el perfil cognitivo: {str(e)}"}), 500

@user_bp.route('/cognitive-profile/update', methods=['PUT'])
@handle_errors
def update_cognitive_profile_endpoint():
    data = request.get_json()
    email = data.get('email')
    profile = data.get('profile')

    if not email or not profile:
        return jsonify({
            "error": "Se requiere el email del estudiante y los datos del perfil"
        }), 400

    try:
        profile_json_string = json.dumps(profile) if isinstance(profile, dict) else profile
        success = update_cognitive_profile(email, profile_json_string)
        
        if success:
            return jsonify({
                "message": "Perfil cognitivo actualizado exitosamente"
            }), 200
        return jsonify({
            "error": "No se pudo actualizar el perfil cognitivo"
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"Error al actualizar el perfil cognitivo: {str(e)}"
        }), 500