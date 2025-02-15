from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.study_plan.db_basic import (
    create_study_plan,
    assign_study_plan,
    get_study_plan,
    get_study_plan_assignments,
    update_study_plan,
    update_study_plan_assignment,
    delete_study_plan,
    remove_study_plan_assignment
)

@handle_errors
def create_study_plan_endpoint():
    data = request.get_json()
    required_fields = ['name', 'description', 'created_by']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    study_plan_id = create_study_plan(
        name=data['name'],
        description=data['description'],
        created_by=data['created_by'],
        is_template=data.get('is_template', False),
        document_url=data.get('document_url')
    )
    
    return jsonify({
        "message": "Plan de estudios creado exitosamente",
        "study_plan_id": str(study_plan_id)
    }), 201

@handle_errors
def assign_study_plan_endpoint():
    data = request.get_json()
    if not all(k in data for k in ['study_plan_id', 'classroom_id']):
        return jsonify({"error": "Faltan datos requeridos"}), 400
        
    assignment_id = assign_study_plan(
        data['study_plan_id'],
        data['classroom_id']
    )
    
    return jsonify({
        "message": "Plan de estudios asignado exitosamente",
        "assignment_id": str(assignment_id)
    }), 201

@handle_errors
def get_study_plan_assignments_endpoint():
    study_plan_id = request.args.get('study_plan_id')
    classroom_id = request.args.get('classroom_id')
    
    assignments = get_study_plan_assignments(study_plan_id, classroom_id)
    return jsonify({"assignments": assignments}), 200

@handle_errors
def get_study_plan_endpoint():
    """Obtiene un plan de estudios específico"""
    study_plan_id = request.args.get('study_plan_id')
    if not study_plan_id:
        return jsonify({"error": "ID del plan de estudios requerido"}), 400
    
    study_plan = get_study_plan(study_plan_id)
    return jsonify(study_plan), 200

@handle_errors
def update_study_plan_endpoint():
    """Actualiza un plan de estudios existente"""
    study_plan_id = request.json.get('study_plan_id')
    updates = request.json.get('updates')
    
    if not study_plan_id or not updates:
        return jsonify({"error": "Datos incompletos"}), 400
        
    updated_plan = update_study_plan(study_plan_id, updates)
    return jsonify(updated_plan), 200

@handle_errors
def delete_study_plan_endpoint():
    """Elimina un plan de estudios"""
    study_plan_id = request.args.get('study_plan_id')
    if not study_plan_id:
        return jsonify({"error": "ID del plan de estudios requerido"}), 400
        
    delete_study_plan(study_plan_id)
    return jsonify({"message": "Plan de estudios eliminado exitosamente"}), 200

def register_basic_routes(bp):
    """Registra las rutas básicas del plan de estudios"""
    bp.add_url_rule(
        '/study-plan',
        'create_study_plan',
        create_study_plan_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/study-plan/assign',
        'assign_study_plan',
        assign_study_plan_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/study-plan/assignments',
        'get_study_plan_assignments',
        get_study_plan_assignments_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/study-plan',
        'get_study_plan',
        get_study_plan_endpoint,
        methods=['GET']
    )
    bp.add_url_rule(
        '/study-plan',
        'update_study_plan',
        update_study_plan_endpoint,
        methods=['PUT']
    )
    bp.add_url_rule(
        '/study-plan',
        'delete_study_plan',
        delete_study_plan_endpoint,
        methods=['DELETE']
    )