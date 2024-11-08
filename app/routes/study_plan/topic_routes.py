from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.study_plan.db_topics import (
    create_topic,
    get_topics,
    update_topic,
    delete_topic
)

@handle_errors
def create_topic_endpoint():
    """Crea un nuevo tema en un módulo"""
    data = request.get_json()
    required_fields = ['module_id', 'name', 'description', 'date_range', 'class_schedule']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    topic_id = create_topic(
        module_id=data['module_id'],
        name=data['name'],
        description=data['description'],
        date_range=data['date_range'],
        class_schedule=data['class_schedule']
    )
    
    return jsonify({
        "message": "Tema creado exitosamente",
        "topic_id": str(topic_id)
    }), 201

@handle_errors
def get_topics_endpoint(module_id):
    """Obtiene todos los temas de un módulo"""
    topics = get_topics(module_id)
    return jsonify({"topics": topics}), 200

@handle_errors
def update_topic_endpoint(topic_id):
    """Actualiza un tema existente"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
    
    updated = update_topic(topic_id, data)
    if not updated:
        return jsonify({"error": "Tema no encontrado"}), 404
    
    return jsonify({"message": "Tema actualizado exitosamente"}), 200

@handle_errors
def delete_topic_endpoint(topic_id):
    """Elimina un tema específico"""
    deleted = delete_topic(topic_id)
    if not deleted:
        return jsonify({"error": "Tema no encontrado"}), 404
    
    return jsonify({"message": "Tema eliminado exitosamente"}), 200

def register_topic_routes(bp):
    """Registra las rutas relacionadas con temas"""
    bp.add_url_rule(
        '/topic',
        'create_topic',
        create_topic_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/module/<module_id>/topics',
        'get_topics',
        get_topics_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/topic/<topic_id>',
        'update_topic',
        update_topic_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/topic/<topic_id>',
        'delete_topic',
        delete_topic_endpoint,
        methods=['DELETE']
    )