from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.db_classroom import (
    get_teacher_classrooms,
    get_classroom_students,
    get_student_classrooms
)

classroom_bp = Blueprint('classroom', __name__)

@classroom_bp.route('/teacher/classrooms', methods=['GET'])
@handle_errors
def get_teacher_classrooms_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del profesor"}), 400

    try:
        classrooms = get_teacher_classrooms(email)
        return jsonify({"classrooms": classrooms}), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener los salones: {str(e)}"}), 500

@classroom_bp.route('/classroom/students', methods=['GET'])
@handle_errors
def get_classroom_students_endpoint():
    try:
        classroom_id = request.args.get('classroomId')
        result = get_classroom_students(classroom_id)
        if result["success"]:
            return jsonify({
                "students": result["students"],
                "count": result["count"]
            }), 200
        return jsonify({"error": result["error"]}), 400
    except Exception as e:
        return jsonify({"error": f"Error al obtener estudiantes: {str(e)}"}), 500

@classroom_bp.route('/student/classrooms', methods=['GET'])
@handle_errors
def get_student_classrooms_endpoint():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Se requiere el email del estudiante"}), 400

    try:
        classrooms = get_student_classrooms(email)
        return jsonify({
            "classrooms": classrooms,
            "count": len(classrooms)
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener los salones: {str(e)}"}), 500 