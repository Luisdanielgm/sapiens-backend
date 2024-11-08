from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.content import (
    create_content,
    update_content,
    get_content,
    get_student_content,
    delete_content
)
from database.common import get_user_id_by_email

content_bp = Blueprint('content', __name__)

@content_bp.route('/content/create', methods=['POST'])
@handle_errors
def create_content_endpoint():
    data = request.get_json()
    email = data.get('email')
    classroom_id = data.get('classroom_id')
    content_text = data.get('content')

    if not all([email, classroom_id, content_text]):
        return jsonify({
            "error": "Se requieren email, classroom_id y content"
        }), 400

    try:
        student_id = get_user_id_by_email(email)
        if not student_id:
            return jsonify({
                "error": "Estudiante no encontrado"
            }), 404

        content_id = create_content(classroom_id, str(student_id), content_text)
        if content_id:
            return jsonify({
                "message": "Contenido creado exitosamente",
                "content_id": content_id
            }), 200
        return jsonify({
            "error": "No se pudo crear el contenido"
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"Error al crear el contenido: {str(e)}"
        }), 500

@content_bp.route('/content/update', methods=['PUT'])
@handle_errors
def update_content_endpoint():
    data = request.get_json()
    content_id = data.get('content_id')
    content_text = data.get('content')

    if not content_id or not content_text:
        return jsonify({
            "error": "Se requiere content_id y content"
        }), 400

    try:
        success = update_content(content_id, content_text)
        if success:
            return jsonify({
                "message": "Contenido actualizado exitosamente"
            }), 200
        return jsonify({
            "error": "No se pudo actualizar el contenido"
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"Error al actualizar el contenido: {str(e)}"
        }), 500

@content_bp.route('/content/get', methods=['POST'])
@handle_errors
def get_content_endpoint():
    data = request.get_json()
    content_id = data.get('content_id')

    if not content_id:
        return jsonify({
            "error": "Se requiere content_id"
        }), 400

    try:
        content = get_content(content_id)
        if content:
            return jsonify({"content": content}), 200
        return jsonify({
            "error": "Contenido no encontrado"
        }), 404
    except Exception as e:
        return jsonify({
            "error": f"Error al obtener el contenido: {str(e)}"
        }), 500

@content_bp.route('/content/student', methods=['GET'])
@handle_errors
def get_student_content_endpoint():
    email = request.args.get('email')
    classroom_id = request.args.get('classroom_id')

    if not email or not classroom_id:
        return jsonify({
            "error": "Se requieren email y classroom_id"
        }), 400

    try:
        student_id = get_user_id_by_email(email)
        if not student_id:
            return jsonify({
                "error": "Estudiante no encontrado"
            }), 404

        contents = get_student_content(str(student_id), classroom_id)
        return jsonify({
            "contents": contents,
            "count": len(contents)
        }), 200
    except Exception as e:
        return jsonify({
            "error": f"Error al obtener el contenido: {str(e)}"
        }), 500

@content_bp.route('/content/delete/<content_id>', methods=['DELETE'])
@handle_errors
def delete_content_endpoint(content_id):
    try:
        success = delete_content(content_id)
        if success:
            return jsonify({
                "message": "Contenido eliminado exitosamente"
            }), 200
        return jsonify({
            "error": "No se pudo eliminar el contenido"
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"Error al eliminar el contenido: {str(e)}"
        }), 500