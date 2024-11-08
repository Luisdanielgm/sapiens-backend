from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.institute.db_basic import (
    create_institute,
    update_institute,
    delete_institute,
    get_institute_details,
    get_institute_statistics
)
from bson import ObjectId

@handle_errors
def create_institute_endpoint():
    """Crea un nuevo instituto con la información proporcionada"""
    data = request.get_json()
    required_fields = ['name', 'address', 'phone', 'email', 'website', 'admin_email']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    success, result = create_institute(**{k: data[k] for k in required_fields})
    
    if success:
        return jsonify({"message": "Instituto creado exitosamente", "id": result}), 200
    return jsonify({"error": result}), 400

@handle_errors
def update_institute_endpoint(institute_id):
    """Actualiza la información de un instituto existente"""
    data = request.get_json()
    admin_email = data.get('admin_email')
    
    if not admin_email:
        return jsonify({"error": "Se requiere el email del administrador"}), 400

    success, message = update_institute(institute_id, data, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def delete_institute_endpoint(institute_id):
    admin_email = request.args.get('admin_email')
    if not admin_email:
        return jsonify({"error": "Se requiere el email del administrador"}), 400

    success, message = delete_institute(institute_id, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def get_institute_details_endpoint(institute_id):
    """Obtiene los detalles de un instituto específico"""
    try:
        ObjectId(institute_id)
    except:
        return jsonify({"error": "ID de instituto inválido"}), 400
        
    details = get_institute_details(institute_id)
    if details:
        return jsonify({"institute": details}), 200
    return jsonify({"error": "Instituto no encontrado"}), 404

@handle_errors
def get_institute_statistics_endpoint(institute_id):
    stats = get_institute_statistics(institute_id)
    if stats:
        return jsonify({"statistics": stats}), 200
    return jsonify({"error": "No se pudieron obtener las estadísticas"}), 404

def register_basic_routes(bp):
    """Registra las rutas básicas del instituto"""
    bp.add_url_rule(
        '/institute/create',
        'create_institute',
        create_institute_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/institute/update/<institute_id>',
        'update_institute',
        update_institute_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/institute/delete/<institute_id>',
        'delete_institute',
        delete_institute_endpoint,
        methods=['DELETE']
    )
    
    bp.add_url_rule(
        '/institute/details/<institute_id>',
        'get_institute_details',
        get_institute_details_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/institute/statistics/<institute_id>',
        'get_institute_statistics',
        get_institute_statistics_endpoint,
        methods=['GET']
    )