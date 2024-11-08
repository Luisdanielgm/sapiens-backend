from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.study_plan.db_modules import (
    create_module,
    get_modules,
    update_module,
    delete_module
)

@handle_errors
def create_module_endpoint():
    """Crea un nuevo módulo en el plan de estudios"""
    data = request.get_json()
    required_fields = ['study_plan_id', 'name', 'start_date', 'end_date', 'objectives']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    module_id = create_module(
        study_plan_id=data['study_plan_id'],
        name=data['name'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        objectives=data['objectives']
    )
    
    return jsonify({
        "message": "Módulo creado exitosamente",
        "module_id": str(module_id)
    }), 201

@handle_errors
def get_modules_endpoint(study_plan_id):
    """Obtiene todos los módulos de un plan de estudios"""
    modules = get_modules(study_plan_id)
    return jsonify({"modules": modules}), 200

@handle_errors
def update_module_endpoint(module_id):
    """Actualiza un módulo existente"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
    
    updated = update_module(module_id, data)
    if not updated:
        return jsonify({"error": "Módulo no encontrado"}), 404
    
    return jsonify({"message": "Módulo actualizado exitosamente"}), 200

@handle_errors
def delete_module_endpoint(module_id):
    """Elimina un módulo y sus temas asociados"""
    deleted = delete_module(module_id)
    if not deleted:
        return jsonify({"error": "Módulo no encontrado"}), 404
    
    return jsonify({"message": "Módulo eliminado exitosamente"}), 200

def register_module_routes(bp):
    """Registra las rutas relacionadas con módulos"""
    bp.add_url_rule(
        '/module',
        'create_module',
        create_module_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/study-plan/<study_plan_id>/modules',
        'get_modules',
        get_modules_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/module/<module_id>',
        'update_module',
        update_module_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/module/<module_id>',
        'delete_module',
        delete_module_endpoint,
        methods=['DELETE']
    ) 