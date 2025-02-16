from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.study_plan.db_evaluations import (
    get_module_evaluations,
    get_student_evaluations,
    record_student_evaluation
)

@handle_errors
def get_module_evaluations_endpoint(module_id):
    """Obtiene las actividades de evaluación de un módulo"""
    evaluations = get_module_evaluations(module_id)
    return jsonify({"evaluations": evaluations}), 200

@handle_errors
def get_student_evaluations_endpoint(student_id):
    """Obtiene las evaluaciones de un estudiante"""
    module_id = request.args.get('module_id')
    evaluations = get_student_evaluations(student_id, module_id)
    return jsonify({"evaluations": evaluations}), 200

@handle_errors
def record_evaluation_endpoint():
    """Registra una evaluación para un estudiante"""
    data = request.get_json()
    required_fields = ['module_id', 'activity_id', 'student_id', 'score']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
        
    evaluation_id = record_student_evaluation(
        data['module_id'],
        data['activity_id'],
        data['student_id'],
        data['score'],
        data.get('feedback', '')
    )
    
    return jsonify({
        "message": "Evaluación registrada exitosamente",
        "evaluation_id": str(evaluation_id)
    }), 201

def register_evaluation_routes(bp):
    bp.add_url_rule(
        '/module/<module_id>/evaluations',
        'get_module_evaluations',
        get_module_evaluations_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/student/<student_id>/evaluations',
        'get_student_evaluations',
        get_student_evaluations_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/evaluation/record',
        'record_evaluation',
        record_evaluation_endpoint,
        methods=['POST']
    )