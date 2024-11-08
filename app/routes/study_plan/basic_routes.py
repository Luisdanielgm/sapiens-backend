from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.study_plan.db_basic import (
    create_study_plan,
    get_study_plan,
    update_study_plan,
    delete_study_plan
)

@handle_errors
def upload_study_plan():
    """Crea plan de estudios a partir de datos JSON"""
    data = request.get_json()
    classroom_id = data.get('classroom_id')
    name = data.get('name')
    description = data.get('description')
    
    if not all([classroom_id, name, description]):
        return jsonify({"error": "Faltan datos requeridos"}), 400
    
    try:
        study_plan_id = create_study_plan(
            classroom_id=classroom_id,
            name=name,
            description=description,
            document_url=None  # O eliminar si ya no es necesario
        )
        
        return jsonify({
            "message": "Plan de estudios creado exitosamente",
            "study_plan_id": str(study_plan_id)
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        '/study-plan/upload',
        'upload_study_plan',
        upload_study_plan,
        methods=['POST']
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