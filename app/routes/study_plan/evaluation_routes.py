from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.study_plan.db_evaluations import (
    create_evaluation_plan,
    create_evaluation,
    get_evaluation_plan,
    get_evaluations,
    update_evaluation_plan,
    update_evaluation,
    delete_evaluation_plan,
    delete_evaluation,
    get_evaluation_by_id,
    get_evaluations_by_module,
    get_evaluations_by_topic
)

@handle_errors
def upload_evaluation_plan():
    """Crea plan de evaluación a partir de datos JSON"""
    data = request.get_json()
    classroom_ids = data.get('classroom_ids', [])
    evaluations_data = data.get('evaluations', [])
    
    if not classroom_ids or not evaluations_data:
        return jsonify({"error": "Faltan datos requeridos"}), 400
    
    try:
        evaluation_plan_id = create_evaluation_plan(
            classroom_ids=classroom_ids,
            document_url=None  # O eliminar este campo si ya no es necesario
        )
        
        for eval_data in evaluations_data:
            create_evaluation(
                evaluation_plan_id=evaluation_plan_id,
                module_id=eval_data['module_id'],
                topic_ids=eval_data['topic_ids'],
                name=eval_data['name'],
                description=eval_data['description'],
                methodology=eval_data['methodology'],
                weight=eval_data['weight'],
                date=eval_data['date']
            )
        
        return jsonify({
            "message": "Plan de evaluación creado exitosamente",
            "evaluation_plan_id": str(evaluation_plan_id)
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def get_evaluation_plan_details(evaluation_plan_id):
    """Obtiene detalles completos del plan de evaluación"""
    eval_plan = get_evaluation_plan(evaluation_plan_id)
    if not eval_plan:
        return jsonify({"error": "Plan de evaluación no encontrado"}), 404
    
    evaluations = get_evaluations(evaluation_plan_id)
    eval_plan['evaluations'] = evaluations
    return jsonify(eval_plan), 200

@handle_errors
def create_evaluation_endpoint():
    """Crea una nueva evaluación individual"""
    data = request.get_json()
    required_fields = [
        'evaluation_plan_id', 'module_id', 'topic_ids', 'name',
        'description', 'methodology', 'weight', 'date'
    ]
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    evaluation_id = create_evaluation(
        evaluation_plan_id=data['evaluation_plan_id'],
        module_id=data['module_id'],
        topic_ids=data['topic_ids'],
        name=data['name'],
        description=data['description'],
        methodology=data['methodology'],
        weight=data['weight'],
        date=data['date']
    )
    
    return jsonify({
        "message": "Evaluación creada exitosamente",
        "evaluation_id": str(evaluation_id)
    }), 201

@handle_errors
def get_evaluation_details(evaluation_id):
    """Obtiene detalles de una evaluación específica"""
    evaluation = get_evaluation_by_id(evaluation_id)
    if not evaluation:
        return jsonify({"error": "Evaluación no encontrada"}), 404
    
    return jsonify(evaluation), 200

@handle_errors
def get_module_evaluations(module_id):
    """Obtiene todas las evaluaciones de un módulo"""
    evaluations = get_evaluations_by_module(module_id)
    return jsonify({"evaluations": evaluations}), 200

@handle_errors
def get_topic_evaluations(topic_id):
    """Obtiene todas las evaluaciones relacionadas con un tema"""
    evaluations = get_evaluations_by_topic(topic_id)
    return jsonify({"evaluations": evaluations}), 200

@handle_errors
def update_evaluation_plan_endpoint(evaluation_plan_id):
    """Actualiza un plan de evaluación existente"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
    
    updated = update_evaluation_plan(evaluation_plan_id, data)
    if not updated:
        return jsonify({"error": "Plan de evaluación no encontrado"}), 404
    
    return jsonify({"message": "Plan de evaluación actualizado exitosamente"}), 200

@handle_errors
def update_evaluation_endpoint(evaluation_id):
    """Actualiza una evaluación específica"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
    
    updated = update_evaluation(evaluation_id, data)
    if not updated:
        return jsonify({"error": "Evaluación no encontrada"}), 404
    
    return jsonify({"message": "Evaluación actualizada exitosamente"}), 200

@handle_errors
def delete_evaluation_plan_endpoint(evaluation_plan_id):
    """Elimina un plan de evaluación y sus evaluaciones asociadas"""
    deleted = delete_evaluation_plan(evaluation_plan_id)
    if not deleted:
        return jsonify({"error": "Plan de evaluación no encontrado"}), 404
    
    return jsonify({"message": "Plan de evaluación eliminado exitosamente"}), 200

@handle_errors
def delete_evaluation_endpoint(evaluation_id):
    """Elimina una evaluación específica"""
    deleted = delete_evaluation(evaluation_id)
    if not deleted:
        return jsonify({"error": "Evaluación no encontrada"}), 404
    
    return jsonify({"message": "Evaluación eliminada exitosamente"}), 200

def register_evaluation_routes(bp):
    """Registra las rutas relacionadas con evaluaciones"""
    # Rutas para Plan de Evaluación
    bp.add_url_rule(
        '/evaluation-plan/upload',
        'upload_evaluation_plan',
        upload_evaluation_plan,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/evaluation-plan/<evaluation_plan_id>',
        'get_evaluation_plan_details',
        get_evaluation_plan_details,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/evaluation-plan/<evaluation_plan_id>',
        'update_evaluation_plan',
        update_evaluation_plan_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/evaluation-plan/<evaluation_plan_id>',
        'delete_evaluation_plan',
        delete_evaluation_plan_endpoint,
        methods=['DELETE']
    )
    
    # Rutas para Evaluaciones individuales
    bp.add_url_rule(
        '/evaluation',
        'create_evaluation',
        create_evaluation_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/evaluation/<evaluation_id>',
        'get_evaluation_details',
        get_evaluation_details,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/evaluation/<evaluation_id>',
        'update_evaluation',
        update_evaluation_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/evaluation/<evaluation_id>',
        'delete_evaluation',
        delete_evaluation_endpoint,
        methods=['DELETE']
    )
    
    # Rutas para consultas específicas
    bp.add_url_rule(
        '/module/<module_id>/evaluations',
        'get_module_evaluations',
        get_module_evaluations,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/topic/<topic_id>/evaluations',
        'get_topic_evaluations',
        get_topic_evaluations,
        methods=['GET']
    )