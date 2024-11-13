from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.analytics.dashboard_stats import (
    get_student_dashboard_stats,
    get_teacher_dashboard_stats
)
from database.common import get_user_id_by_email

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard/student', methods=['GET'])
@handle_errors
def get_student_dashboard():
    """
    Obtiene las estadísticas para el dashboard del estudiante
    
    Query params:
        email: correo del estudiante
        period_id: (opcional) ID del período académico
    """
    email = request.args.get('email')
    period_id = request.args.get('period_id')

    if not email:
        return jsonify({
            "error": "Se requiere el email del estudiante"
        }), 400

    try:
        student_id = get_user_id_by_email(email)
        if not student_id:
            return jsonify({
                "error": "Estudiante no encontrado"
            }), 404

        stats = get_student_dashboard_stats(
            student_id=str(student_id),
            period_id=period_id
        )

        if not stats:
            return jsonify({
                "error": "No se pudieron obtener las estadísticas"
            }), 404

        return jsonify({
            "stats": stats,
            "message": "Estadísticas obtenidas exitosamente"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error al obtener estadísticas: {str(e)}"
        }), 500

@dashboard_bp.route('/dashboard/teacher', methods=['GET'])
@handle_errors
def get_teacher_dashboard():
    """
    Obtiene las estadísticas para el dashboard del profesor
    
    Query params:
        email: correo del profesor
        period_id: (opcional) ID del período académico
    """
    email = request.args.get('email')
    period_id = request.args.get('period_id')

    if not email:
        return jsonify({
            "error": "Se requiere el email del profesor"
        }), 400

    try:
        teacher_id = get_user_id_by_email(email)
        if not teacher_id:
            return jsonify({
                "error": "Profesor no encontrado"
            }), 404

        stats = get_teacher_dashboard_stats(
            teacher_id=str(teacher_id),
            period_id=period_id
        )

        if not stats:
            return jsonify({
                "error": "No se pudieron obtener las estadísticas"
            }), 404

        return jsonify({
            "stats": stats,
            "message": "Estadísticas obtenidas exitosamente"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error al obtener estadísticas: {str(e)}"
        }), 500

@dashboard_bp.route('/dashboard/student/subjects', methods=['GET'])
@handle_errors
def get_student_subjects_stats():
    """
    Obtiene estadísticas detalladas por materia para un estudiante
    
    Query params:
        email: correo del estudiante
        subject_id: (opcional) ID de la materia específica
    """
    email = request.args.get('email')
    subject_id = request.args.get('subject_id')

    if not email:
        return jsonify({
            "error": "Se requiere el email del estudiante"
        }), 400

    try:
        student_id = get_user_id_by_email(email)
        if not student_id:
            return jsonify({
                "error": "Estudiante no encontrado"
            }), 404

        # Aquí se podría implementar una función específica para estadísticas por materia
        # get_student_subject_stats(student_id, subject_id)

        return jsonify({
            "message": "Endpoint en desarrollo"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error al obtener estadísticas: {str(e)}"
        }), 500

@dashboard_bp.route('/dashboard/teacher/classroom/<classroom_id>', methods=['GET'])
@handle_errors
def get_teacher_classroom_stats(classroom_id):
    """
    Obtiene estadísticas detalladas de un salón específico
    
    Path params:
        classroom_id: ID del salón
    Query params:
        email: correo del profesor
    """
    email = request.args.get('email')

    if not email:
        return jsonify({
            "error": "Se requiere el email del profesor"
        }), 400

    try:
        teacher_id = get_user_id_by_email(email)
        if not teacher_id:
            return jsonify({
                "error": "Profesor no encontrado"
            }), 404

        # Aquí se podría implementar una función específica para estadísticas por salón
        # get_classroom_detailed_stats(teacher_id, classroom_id)

        return jsonify({
            "message": "Endpoint en desarrollo"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error al obtener estadísticas: {str(e)}"
        }), 500 