import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity, get_jwt
from bson import ObjectId
from typing import Dict, Any
import traceback

from .template_services import TemplateService, TemplateInstanceService, TemplateMarkupExtractor
from .template_models import Template, TemplateInstance
from src.shared.decorators import auth_required, role_required
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable

template_bp = Blueprint('templates', __name__, url_prefix='/api/templates')

# Inicializar servicios
template_service = TemplateService()
instance_service = TemplateInstanceService()

@template_bp.route('', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def create_template():
    """
    Crear una nueva plantilla.
    
    Body:
    {
        "name": "Nombre de la plantilla",
        "html": "<html>...</html>",
        "description": "Descripción opcional",
        "scope": "private|org|public",
        "style_tags": ["tag1", "tag2"],
        "subject_tags": ["matematicas", "ciencias"],
        "baseline_mix": {"V": 60, "A": 10, "K": 20, "R": 10},
        "capabilities": {"audio": true, "microphone": false}
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'html' not in data:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "HTML content is required"
            }), 400
        
        # Crear plantilla
        template = template_service.create_template(data, user_id)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Plantilla creada exitosamente",
                "template": ensure_json_serializable(template.to_dict())
            }
        }), 201
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except Exception as e:
        logging.error(f"Error creating template: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('', methods=['GET'])
@auth_required
def list_templates():
    """
    Listar plantillas con filtros.
    
    Query params:
    - owner: "me" | "all" (default: "all")
    - scope: "public" | "org" | "private"
    - style_tags: filtro por tags de estilo (comma separated)
    - subject_tags: filtro por tags de materia (comma separated)
    """
    try:
        user_id = get_jwt_identity()
        claims = get_jwt()
        workspace_id = claims.get('workspace_id')
        
        # Parámetros de filtro
        owner_filter = request.args.get('owner', 'all')
        scope_filter = request.args.get('scope')
        style_tags = request.args.get('style_tags', '').split(',') if request.args.get('style_tags') else None
        subject_tags = request.args.get('subject_tags', '').split(',') if request.args.get('subject_tags') else None
        
        # Obtener plantillas
        templates = template_service.list_templates(
            owner_filter=owner_filter,
            scope_filter=scope_filter,
            user_id=user_id,
            workspace_id=workspace_id
        )
        
        # Aplicar filtros adicionales
        if style_tags:
            templates = [t for t in templates if any(tag in t.style_tags for tag in style_tags)]
        
        if subject_tags:
            templates = [t for t in templates if any(tag in t.subject_tags for tag in subject_tags)]
        
        # Convertir a dict para respuesta
        templates_data = ensure_json_serializable([template.to_dict() for template in templates])
        
        return jsonify({
            "success": True,
            "data": {
                "templates": templates_data,
                "total": len(templates_data)
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error listing templates: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/<template_id>', methods=['GET'])
@auth_required
def get_template(template_id):
    """
    Obtener una plantilla específica.
    """
    try:
        template = template_service.get_template(template_id)
        
        if not template:
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "Plantilla no encontrada"
            }), 404
        
        return jsonify({
            "success": True,
            "data": {
                "template": ensure_json_serializable(template.to_dict())
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error getting template {template_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/<template_id>', methods=['PUT'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def update_template(template_id):
    """
    Actualizar una plantilla existente.
    
    Body: Campos a actualizar (name, html, description, scope, status, etc.)
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "No data provided"
            }), 400
        
        # Si llega 'html' se creará una nueva versión automáticamente en el servicio
        template = template_service.update_template(template_id, data, user_id)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Plantilla actualizada exitosamente",
                "template": ensure_json_serializable(template.to_dict())
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except PermissionError as e:
        return jsonify({
            "success": False,
            "error": "PERMISSION_DENIED",
            "message": str(e)
        }), 403
    except Exception as e:
        logging.error(f"Error updating template {template_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/<template_id>/fork', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def fork_template(template_id):
    """
    Crear un fork (copia) de una plantilla.
    
    Body:
    {
        "name": "Nombre opcional para el fork"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}
        
        new_name = data.get('name')
        
        # Crear fork
        fork = template_service.fork_template(template_id, user_id, new_name)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Fork creado exitosamente",
                "template": ensure_json_serializable(fork.to_dict())
            }
        }), 201
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except PermissionError as e:
        return jsonify({
            "success": False,
            "error": "PERMISSION_DENIED",
            "message": str(e)
        }), 403
    except Exception as e:
        logging.error(f"Error forking template {template_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/<template_id>/extract', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def extract_markers(template_id):
    """
    Extraer marcadores de personalización del HTML de una plantilla.
    """
    try:
        user_id = get_jwt_identity()
        
        # Obtener plantilla
        template = template_service.get_template(template_id)
        if not template:
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "Plantilla no encontrada"
            }), 404
        
        # Verificar permisos
        if str(template.owner_id) != user_id:
            return jsonify({
                "success": False,
                "error": "PERMISSION_DENIED",
                "message": "No tienes permisos para editar esta plantilla"
            }), 403
        
        # Extraer marcadores
        extraction_result = TemplateMarkupExtractor.extract_markers(template.get_latest_html())
        
        # Actualizar plantilla con el schema extraído
        update_data = {
            "props_schema": extraction_result["props_schema"],
            "defaults": extraction_result["defaults"],
            "personalization": {
                "is_extracted": True,
                "last_extraction": current_app.config.get('TESTING', False) and "2024-01-01T00:00:00" or None,
                "extraction_version": template.version
            }
        }
        
        updated_template = template_service.update_template(template_id, update_data, user_id)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Marcadores extraídos exitosamente",
                "extraction_result": extraction_result,
                "template": ensure_json_serializable(updated_template.to_dict())
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error extracting markers from template {template_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/<template_id>', methods=['DELETE'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def delete_template(template_id):
    """
    Eliminar una plantilla.
    """
    try:
        user_id = get_jwt_identity()
        
        success = template_service.delete_template(template_id, user_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": "OPERATION_FAILED",
                "message": "No se pudo eliminar la plantilla"
            }), 400
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Plantilla eliminada exitosamente"
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except PermissionError as e:
        return jsonify({
            "success": False,
            "error": "PERMISSION_DENIED",
            "message": str(e)
        }), 403
    except Exception as e:
        logging.error(f"Error deleting template {template_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

# === TEMPLATE INSTANCES ENDPOINTS ===

instance_bp = Blueprint('template_instances', __name__, url_prefix='/api/template-instances')

@instance_bp.route('', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def create_instance():
    """
    Crear una nueva instancia de plantilla.
    
    Body:
    {
        "template_id": "template_id",
        "topic_id": "topic_id",
        "props": {"param1": "value1"},
        "assets": [{"id": "asset1", "name": "imagen.jpg", "url": "...", "type": "image"}],
        "learning_mix": {"mode": "manual", "values": {"V": 70, "A": 10, "K": 15, "R": 5}}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "No data provided"
            }), 400
        
        # Validar campos requeridos
        required_fields = ["template_id", "topic_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Campo requerido: {field}"}), 400
        
        # Crear instancia
        instance = instance_service.create_instance(data)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Instancia de plantilla creada exitosamente",
                "instance": ensure_json_serializable(instance.to_dict())
            }
        }), 201
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except Exception as e:
        logging.error(f"Error creating template instance: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@instance_bp.route('/<instance_id>', methods=['GET'])
@auth_required
def get_instance(instance_id):
    """
    Obtener una instancia específica.
    """
    try:
        instance = instance_service.get_instance(instance_id)
        
        if not instance:
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "Instancia no encontrada"
            }), 404
        
        return jsonify({
            "success": True,
            "data": {
                "instance": ensure_json_serializable(instance.to_dict())
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error getting template instance {instance_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@instance_bp.route('/topic/<topic_id>', methods=['GET'])
@auth_required
def get_instances_by_topic(topic_id):
    """
    Obtener todas las instancias de un tema.
    """
    try:
        instances = instance_service.get_instances_by_topic(topic_id)
        
        instances_data = ensure_json_serializable([instance.to_dict() for instance in instances])
        
        return jsonify({
            "success": True,
            "data": {
                "instances": instances_data,
                "total": len(instances_data)
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error getting instances for topic {topic_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@instance_bp.route('/<instance_id>', methods=['PUT'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def update_instance(instance_id):
    """
    Actualizar una instancia de plantilla.
    
    Body: Campos a actualizar (props, assets, learning_mix, status)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "No data provided"
            }), 400
        
        # Actualizar instancia
        instance = instance_service.update_instance(instance_id, data)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Instancia actualizada exitosamente",
                "instance": ensure_json_serializable(instance.to_dict())
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except Exception as e:
        logging.error(f"Error updating template instance {instance_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@instance_bp.route('/<instance_id>/publish', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def publish_instance(instance_id):
    """
    Marcar una instancia como publicada/activa.
    """
    try:
        instance = instance_service.publish_instance(instance_id)
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Instancia publicada exitosamente",
                "instance": ensure_json_serializable(instance.to_dict())
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except PermissionError as e:
        return jsonify({
            "success": False,
            "error": "PERMISSION_DENIED",
            "message": str(e)
        }), 403
    except Exception as e:
        logging.error(f"Error publishing template instance {instance_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@instance_bp.route('/<instance_id>', methods=['DELETE'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def delete_instance(instance_id):
    """
    Eliminar una instancia de plantilla.
    """
    try:
        success = instance_service.delete_instance(instance_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": "OPERATION_FAILED",
                "message": "No se pudo eliminar la instancia"
            }), 400
        
        return jsonify({
            "success": True,
            "data": {
                "message": "Instancia eliminada exitosamente"
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400
    except PermissionError as e:
        return jsonify({
            "success": False,
            "error": "PERMISSION_DENIED",
            "message": str(e)
        }), 403
    except Exception as e:
        logging.error(f"Error deleting template instance {instance_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

# === PREVIEW ENDPOINTS ===

preview_bp = Blueprint('template_preview', __name__, url_prefix='/preview')

@preview_bp.route('/template/<template_id>')
def preview_template(template_id):
    """
    Preview del HTML bruto de una plantilla (con placeholders).
    Devuelve HTML para mostrar en iframe.
    """
    try:
        template = template_service.get_template(template_id)
        
        if not template:
            return "<html><body><h1>Plantilla no encontrada</h1></body></html>", 404
        
        # TODO: Aplicar Content Security Policy para sandbox
        # TODO: Envolver en iframe seguro si es necesario
        
        return template.get_latest_html(), 200, {
            'Content-Type': 'text/html',
            'Content-Security-Policy': "sandbox allow-scripts allow-same-origin",
            'X-Frame-Options': 'SAMEORIGIN'
        }
        
    except Exception as e:
        logging.error(f"Error previewing template {template_id}: {str(e)}")
        return "<html><body><h1>Error cargando plantilla</h1></body></html>", 500

@preview_bp.route('/instance/<instance_id>')
def preview_instance(instance_id):
    """
    Preview de una instancia con props aplicadas.
    Devuelve HTML personalizado listo para mostrar.
    """
    try:
        instance = instance_service.get_instance(instance_id)
        
        if not instance:
            return "<html><body><h1>Instancia no encontrada</h1></body></html>", 404
        
        # Obtener plantilla base
        template = template_service.get_template(str(instance.template_id))
        if not template:
            return "<html><body><h1>Plantilla base no encontrada</h1></body></html>", 404
        
        # Aplicar props a la plantilla
        processed_html = _apply_props_to_template(template.get_latest_html(), instance.props)
        
        return processed_html, 200, {
            'Content-Type': 'text/html',
            'Content-Security-Policy': "sandbox allow-scripts allow-same-origin",
            'X-Frame-Options': 'SAMEORIGIN'
        }
        
    except Exception as e:
        logging.error(f"Error previewing instance {instance_id}: {str(e)}")
        return "<html><body><h1>Error cargando instancia</h1></body></html>", 500

def _apply_props_to_template(html: str, props: Dict[str, Any]) -> str:
    """
    Aplica las propiedades de una instancia al HTML de la plantilla.
    """
    try:
        import re
        
        processed_html = html
        
        # Reemplazar marcadores de parámetros
        for prop_name, prop_value in props.items():
            # Buscar data-sapiens-param="prop_name" y reemplazar el contenido
            param_pattern = rf'(<[^>]*data-sapiens-param=["\']?{re.escape(prop_name)}["\']?[^>]*>)([^<]*)'
            
            def replace_param_content(match):
                tag_opening = match.group(1)
                # Mantener la etiqueta pero reemplazar el contenido
                return f"{tag_opening}{prop_value}"
            
            processed_html = re.sub(param_pattern, replace_param_content, processed_html, flags=re.IGNORECASE)
            
            # También buscar atributos que usen el parámetro
            attr_pattern = rf'({prop_name})'
            processed_html = re.sub(attr_pattern, str(prop_value), processed_html)
        
        return processed_html
        
    except Exception as e:
        logging.error(f"Error applying props to template: {str(e)}")
        return html  # Devolver HTML original si falla el procesamiento
