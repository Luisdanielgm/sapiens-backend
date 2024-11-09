from flask import jsonify, request
from app.utils.decorators import handle_errors
from database.institute.db_periods import (
    create_academic_period,
    update_academic_period,
    delete_academic_period,
    get_institute_periods,
    create_section,
    update_section,
    create_subject,
    update_subject,
    get_period_sections,
    get_period_subjects
)

@handle_errors
def create_period_endpoint():
    data = request.get_json()
    required_fields = ['program_id', 'name', 'type']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    success, result = create_academic_period(
        data['program_id'],
        data['name'],
        data['type']
    )

    if success:
        return jsonify({"message": "Periodo académico creado exitosamente", "id": result}), 200
    return jsonify({"error": result}), 400

@handle_errors
def update_period_endpoint(period_id):
    data = request.get_json()
    admin_email = data.get('admin_email')
    
    if not admin_email:
        return jsonify({"error": "Se requiere el email del administrador"}), 400

    success, message = update_academic_period(period_id, data, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def delete_period_endpoint(period_id):
    admin_email = request.args.get('admin_email')
    if not admin_email:
        return jsonify({"error": "Se requiere el email del administrador"}), 400

    success, message = delete_academic_period(period_id, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def create_section_endpoint():
    data = request.get_json()
    required_fields = ['program_id', 'period_id', 'name']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    success, result = create_section(
        data['program_id'],
        data['period_id'],
        data['name']
    )

    if success:
        return jsonify({"message": "Sección creada exitosamente", "id": result}), 200
    return jsonify({"error": result}), 400

@handle_errors
def update_section_endpoint(section_id):
    data = request.get_json()
    admin_email = data.get('admin_email')
    name = data.get('name')
    
    if not all([admin_email, name]):
        return jsonify({"error": "Se requieren admin_email y name"}), 400

    success, message = update_section(section_id, name, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def create_subject_endpoint():
    data = request.get_json()
    required_fields = ['program_id', 'period_id', 'name']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    success, result = create_subject(
        data['program_id'],
        data['period_id'],
        data['name']
    )

    if success:
        return jsonify({"message": "Materia creada exitosamente", "id": result}), 200
    return jsonify({"error": result}), 400

@handle_errors
def update_subject_endpoint(subject_id):
    data = request.get_json()
    admin_email = data.get('admin_email')
    name = data.get('name')
    
    if not all([admin_email, name]):
        return jsonify({"error": "Se requieren admin_email y name"}), 400

    success, message = update_subject(subject_id, name, admin_email)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400

@handle_errors
def get_program_periods_endpoint():
    program_id = request.args.get('program_id')
    if not program_id:
        return jsonify({"error": "Se requiere el ID del programa"}), 400

    periods = get_institute_periods(program_id)
    return jsonify({"periods": periods}), 200

@handle_errors
def get_period_sections_endpoint():
    period_id = request.args.get('period_id')
    if not period_id:
        return jsonify({"error": "Se requiere el ID del periodo"}), 400

    sections = get_period_sections(period_id)
    return jsonify({"sections": sections}), 200

@handle_errors
def get_period_subjects_endpoint():
    period_id = request.args.get('period_id')
    if not period_id:
        return jsonify({"error": "Se requiere el ID del periodo"}), 400

    subjects = get_period_subjects(period_id)
    return jsonify({"subjects": subjects}), 200

def register_period_routes(bp):
    """Registra las rutas de periodos académicos"""
    # Rutas de periodos
    bp.add_url_rule(
        '/institute/periods',
        'get_program_periods',
        get_program_periods_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/period/create',
        'create_period',
        create_period_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/period/update/<period_id>',
        'update_period',
        update_period_endpoint,
        methods=['PUT']
    )
    
    bp.add_url_rule(
        '/period/delete/<period_id>',
        'delete_period',
        delete_period_endpoint,
        methods=['DELETE']
    )
    
    # Rutas de secciones
    bp.add_url_rule(
        '/period/sections',
        'get_period_sections',
        get_period_sections_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/section/create',
        'create_section',
        create_section_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/section/update/<section_id>',
        'update_section',
        update_section_endpoint,
        methods=['PUT']
    )
    
    # Rutas de materias
    bp.add_url_rule(
        '/period/subjects',
        'get_period_subjects',
        get_period_subjects_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/subject/create',
        'create_subject',
        create_subject_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/subject/update/<subject_id>',
        'update_subject',
        update_subject_endpoint,
        methods=['PUT']
    )