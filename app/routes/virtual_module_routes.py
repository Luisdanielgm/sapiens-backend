from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.virtual_module import (
    create_virtual_module,
    get_virtual_module,
    get_personalized_module,
    get_student_modules,
    update_personalized_module_progress,
    add_module_resource,
    get_module_resources
)

virtual_module_bp = Blueprint('virtual_module', __name__)

@handle_errors
def create_virtual_module_endpoint():
    """Crea un módulo virtual general para un classroom"""
    data = request.get_json()
    
    try:
        module_id = create_virtual_module(
            module_id=data['module_id'],
            name=data['name'],
            description=data['description'],
            created_by=data['teacher_id'],
            content=data['content']
        )
        
        return jsonify({
            "message": "Módulo virtual creado exitosamente",
            "module_id": str(module_id)
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def add_module_resource_endpoint():
    """Añade un recurso adicional al módulo virtual"""
    if 'file' not in request.files:
        return jsonify({"error": "No se encontró archivo"}), 400
    
    file = request.files['file']
    data = request.form
    
    try:
        resource_id = add_module_resource(
            virtual_module_id=data['virtual_module_id'],
            file=file,
            type=data['type'],
            learning_style=data['learning_style'],
            description=data['description']
        )
        
        return jsonify({
            "message": "Recurso añadido exitosamente",
            "resource_id": str(resource_id)
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def get_virtual_module_endpoint(module_id):
    """Obtiene los detalles de un módulo virtual"""
    try:
        module = get_virtual_module(module_id)
        if not module:
            return jsonify({"error": "Módulo no encontrado"}), 404
        
        # Obtener recursos asociados
        resources = get_module_resources(module_id)
        module['resources'] = resources
        
        return jsonify(module), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def get_student_modules_endpoint(student_id):
    """Obtiene todos los módulos personalizados de un estudiante"""
    try:
        modules = get_student_modules(student_id)
        return jsonify({
            "modules": modules,
            "count": len(modules)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def get_personalized_module_endpoint(module_id):
    """Obtiene los detalles de un módulo personalizado"""
    try:
        module = get_personalized_module(module_id)
        if not module:
            return jsonify({"error": "Módulo personalizado no encontrado"}), 404
        
        # Obtener módulo virtual base y recursos
        virtual_module = get_virtual_module(str(module['virtual_module_id']))
        resources = get_module_resources(
            str(module['virtual_module_id']),
            learning_style=module.get('learning_style')
        )
        
        module['virtual_module'] = virtual_module
        module['resources'] = resources
        
        return jsonify(module), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def update_module_progress_endpoint():
    """Actualiza el progreso de un contenido específico en un módulo personalizado"""
    data = request.get_json()
    
    try:
        success = update_personalized_module_progress(
            module_id=data['module_id'],
            content_index=data['content_index'],
            completed=data['completed'],
            score=data.get('score')
        )
        
        if not success:
            return jsonify({"error": "No se pudo actualizar el progreso"}), 400
            
        return jsonify({
            "message": "Progreso actualizado exitosamente"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def get_module_resources_endpoint(module_id):
    """Obtiene los recursos de un módulo virtual"""
    learning_style = request.args.get('learning_style')
    
    try:
        resources = get_module_resources(module_id, learning_style)
        return jsonify({
            "resources": resources,
            "count": len(resources)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@handle_errors
def add_batch_resources_endpoint():
    """Añade múltiples recursos a un módulo virtual"""
    if 'files[]' not in request.files:
        return jsonify({"error": "No se encontraron archivos"}), 400
    
    files = request.files.getlist('files[]')
    data = request.form
    virtual_module_id = data.get('virtual_module_id')
    
    try:
        resource_ids = []
        for file in files:
            resource_id = add_module_resource(
                virtual_module_id=virtual_module_id,
                file=file,
                type=data.get('type'),
                learning_style=data.get('learning_style'),
                description=data.get('description')
            )
            resource_ids.append(str(resource_id))
        
        return jsonify({
            "message": f"{len(resource_ids)} recursos añadidos exitosamente",
            "resource_ids": resource_ids
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def register_virtual_module_routes(bp):
    """Registra las rutas del módulo virtual"""
    bp.add_url_rule(
        '/virtual-module/create',
        'create_virtual_module',
        create_virtual_module_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/virtual-module/resource/add',
        'add_module_resource',
        add_module_resource_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/virtual-module/<module_id>',
        'get_virtual_module',
        get_virtual_module_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/virtual-module/student/<student_id>',
        'get_student_modules',
        get_student_modules_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/virtual-module/personalized/<module_id>',
        'get_personalized_module',
        get_personalized_module_endpoint,
        methods=['GET']
    )
    
    bp.add_url_rule(
        '/virtual-module/progress/update',
        'update_module_progress',
        update_module_progress_endpoint,
        methods=['POST']
    )
    
    bp.add_url_rule(
        '/virtual-module/resources/<module_id>',
        'get_module_resources',
        get_module_resources_endpoint,
        methods=['GET']
    )

    bp.add_url_rule(
        '/virtual-module/batch-resources',
        'add_batch_resources',
        add_batch_resources_endpoint,
        methods=['POST']
    )