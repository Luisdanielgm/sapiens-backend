from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.statistics import get_teacher_statistics, get_student_statistics

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/statistics/teacher', methods=['GET'])
@handle_errors
def get_teacher_stats():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del profesor"}), 400

    try:
        stats = get_teacher_statistics(email)
        if stats:
            return jsonify({"statistics": stats}), 200
        return jsonify({"error": "No se pudieron obtener las estadísticas"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener estadísticas: {str(e)}"}), 500

@statistics_bp.route('/statistics/student', methods=['GET'])
@handle_errors
def get_student_stats():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    try:
        stats = get_student_statistics(email)
        if stats:
            return jsonify({"statistics": stats}), 200
        return jsonify({"error": "No se pudieron obtener las estadísticas"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener estadísticas: {str(e)}"}), 500 