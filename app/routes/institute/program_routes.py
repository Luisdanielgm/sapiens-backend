from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.institute.db_programs import (
    create_educational_program,
    update_educational_program,
    delete_educational_program,
    get_institute_programs
)
from bson.objectid import ObjectId

@handle_errors
def get_institute_programs_endpoint():
    institute_id = request.args.get('institute_id')
    if not institute_id:
        return jsonify({
            "error": "Se requiere el ID del instituto",
            "programs": []
        }), 400

    # Validar formato del ID
    if not ObjectId.is_valid(institute_id):
        return jsonify({
            "error": "ID de instituto inválido",
            "programs": []
        }), 400

    programs = get_institute_programs(institute_id)
    return jsonify({
        "programs": programs,
        "institute_id": institute_id
    }), 200

@handle_errors
def create_program_endpoint():
    data = request.get_json()
    required_fields = ['institute_id', 'name', 'type', 'description']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Se requieren los campos: institute_id, name, type y description"}), 400

    success, result = create_educational_program(
        data['institute_id'],
        data['name'],
        data['type'],
        data['description']
    )

    if success:
        return jsonify({"message": "Programa creado exitosamente", "id": result}), 200
    return jsonify({"error": result}), 400

@handle_errors
def update_program_endpoint(program_id: str):
    """Actualiza un programa educativo existente"""
    data = request.get_json()
    admin_email = data.get('admin_email')
    
    if not admin_email:
        return jsonify({"error": "Se requiere el email del administrador"}), 400

    success, message = update_educational_program(program_id, data, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def delete_program_endpoint(program_id):
    admin_email = request.args.get('admin_email')
    if not admin_email:
        return jsonify({"error": "Se requiere el email del administrador"}), 400

    success, message = delete_educational_program(program_id, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

def register_program_routes(bp):
    """Registra las rutas de programas educativos"""
    bp.add_url_rule(
        '/institute/programs',
        'get_institute_programs',
        get_institute_programs_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/institute/program/create',
        'create_program',
        create_program_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/program/update/<program_id>',
        'update_program',
        update_program_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/program/delete/<program_id>',
        'delete_program',
        delete_program_endpoint,
        methods=['DELETE']
    )