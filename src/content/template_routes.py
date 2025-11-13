import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity, get_jwt
from bson import ObjectId
from typing import Dict, Any
import traceback

from .template_services import TemplateService, TemplateMarkupExtractor
from .template_integration_service import TemplateIntegrationService
from .template_models import Template
from .services import ContentService
from .models import ContentTypes
from src.shared.decorators import auth_required, role_required
from src.shared.constants import ROLES
from src.shared.utils import ensure_json_serializable

template_bp = Blueprint('templates', __name__, url_prefix='/api/templates')
preview_bp = Blueprint('templates_preview', __name__, url_prefix='/preview')

# Inicializar servicios
template_service = TemplateService()
template_integration_service = TemplateIntegrationService()

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

@template_bp.route('/<template_id>/apply', methods=['POST'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def apply_template_to_topic(template_id):
    """
    Inserta un artefacto basado en plantilla directamente en un tema/diapositiva.
    Espera un payload con `topic_id` y `content` (estructura completa del contenido a persistir).
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        topic_id = data.get("topic_id")
        content_payload = data.get("content")

        if not topic_id:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "topic_id es requerido"
            }), 400

        if not isinstance(content_payload, dict):
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "content debe ser un objeto"
            }), 400

        success, content_id = template_integration_service.apply_template_to_content(
            template_id=template_id,
            topic_id=topic_id,
            content_payload=content_payload,
            order=data.get("order"),
            parent_content_id=data.get("parent_content_id"),
            learning_mix=data.get("learning_mix"),
            content_type=data.get("content_type", "slide"),
            status=data.get("status", "draft"),
            template_metadata=data.get("template_metadata"),
            personalization_markers=data.get("personalization_markers"),
            created_by=user_id
        )

        if not success:
            return jsonify({
                "success": False,
                "error": "OPERATION_FAILED",
                "message": content_id  # contiene detalle del error
            }), 400

        return jsonify({
            "success": True,
            "data": {
                "content_id": content_id,
                "message": "Plantilla aplicada exitosamente"
            }
        }), 201

    except Exception as e:
        logging.error(f"Error applying template {template_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/available', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def get_available_templates():
    """
    Endpoint optimizado para profesores que retorna plantillas disponibles con filtros avanzados.
    Query params:
      - subject: filtro por materia del tema actual
      - style: filtro por estilo de aprendizaje
      - scope: public|org|private
      - learning_methodology: visual|kinesthetic|gamification etc.
      - compatibility: modo de compatibilidad (p.ej. kinesthetic)
      - limit, skip: paginación
    """
    try:
        user_id = get_jwt_identity()
        claims = get_jwt()
        workspace_id = claims.get('workspace_id')

        subject = request.args.get('subject')
        style = request.args.get('style')
        scope = request.args.get('scope', 'public')
        learning_methodology = request.args.get('learning_methodology')
        compatibility = request.args.get('compatibility')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))

        templates = template_service.get_available_templates_for_teacher(
            teacher_id=user_id,
            workspace_id=workspace_id,
            subject=subject,
            style=style,
            scope=scope,
            learning_methodology=learning_methodology,
            compatibility=compatibility,
            limit=limit,
            skip=skip
        )

        # Asegurar serialización
        templates_serializable = ensure_json_serializable(templates)

        return jsonify({
            "success": True,
            "data": {
                "templates": templates_serializable,
                "total": len(templates_serializable)
            }
        }), 200

    except Exception as e:
        logging.error(f"Error in get_available_templates: {e}")
        traceback.print_exc()
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

@template_bp.route('/recommendations', methods=['GET'])
@auth_required
def get_template_recommendations():
    """
    Obtiene recomendaciones de plantillas basadas en el modelo de aprendizaje por refuerzo.
    
    Query params:
    - student_id: ID del estudiante (requerido)
    - topic_id: ID del tema actual (requerido)
    - limit: Número máximo de recomendaciones (opcional, default: 5)
    """
    try:
        # Importar el servicio de personalización adaptativa
        from src.personalization.services import AdaptivePersonalizationService
        
        # Obtener parámetros
        student_id = request.args.get('student_id')
        topic_id = request.args.get('topic_id')
        limit = int(request.args.get('limit', 5))
        
        # Validar parámetros requeridos
        if not student_id:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "student_id es requerido"
            }), 400
            
        if not topic_id:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "topic_id es requerido"
            }), 400
        
        # Validar que sean ObjectIds válidos
        try:
            ObjectId(student_id)
            ObjectId(topic_id)
        except Exception:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "student_id y topic_id deben ser ObjectIds válidos"
            }), 400
        
        # Obtener información del tema para filtrar por subject_tags
        from src.shared.database import get_db
        db = get_db()
        topic = db.topics.find_one({"_id": ObjectId(topic_id)})
        
        if not topic:
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "Tema no encontrado"
            }), 404
        
        # Inicializar servicio de personalización adaptativa
        personalization_service = AdaptivePersonalizationService()
        
        # Obtener recomendaciones del modelo RL
        rl_success, rl_result = personalization_service.get_adaptive_recommendations(
            student_id=student_id,
            topic_id=topic_id,
            context_data={"request_type": "template_recommendations"}
        )
        fallback_mode_flag = False
        rl_error = None
        if not rl_success:
            rl_error = rl_result.get('message', 'Error desconocido')
            logging.warning(f"RL falló: {rl_error}. Seguimos con heurísticas.")
            fallback_mode_flag = True
            rl_result = {}
        
        # Obtener plantillas disponibles
        user_id = get_jwt_identity()
        claims = get_jwt()
        workspace_id = claims.get('workspace_id')
        
        available_templates = template_service.list_templates(
            owner_filter='all',
            scope_filter=None,
            user_id=user_id,
            workspace_id=workspace_id
        )
        
        # Filtrar plantillas por subject_tags del tema
        topic_subjects = topic.get('subject_tags', [])
        if topic_subjects:
            filtered_templates = [
                t for t in available_templates 
                if any(subject in t.subject_tags for subject in topic_subjects)
            ]
        else:
            filtered_templates = available_templates
        
        # Procesar recomendaciones del RL para scoring de plantillas
        rl_recommendations = rl_result.get('recommendations', [])
        confidence_score = rl_result.get('confidence_score', 0.5)
        reasoning = rl_result.get('reasoning', 'Recomendaciones basadas en modelo RL')
        fallback_mode = rl_result.get('fallback_mode', fallback_mode_flag)
        
        # Crear mapa de tipos de contenido recomendados por RL
        rl_content_types = {}
        for rec in rl_recommendations:
            content_type = rec.get('content_type')
            if content_type:
                rl_content_types[content_type] = {
                    'priority': rec.get('priority', 1),
                    'effectiveness': rec.get('estimated_effectiveness', 0.5),
                    'reasoning': rec.get('reasoning', '')
                }
        
        # Scoring de plantillas basado en recomendaciones RL
        scored_templates = []
        
        for template in filtered_templates:
            # Calcular score base
            base_score = 0.5
            template_reasoning = []
            
            # Score basado en baseline_mix VARK del template vs recomendaciones RL
            if hasattr(template, 'baseline_mix') and template.baseline_mix:
                vark_alignment = 0
                for style, percentage in template.baseline_mix.items():
                    # Buscar recomendaciones RL que coincidan con este estilo
                    style_content_types = {
                        'V': ['video', 'image', 'diagram'],
                        'A': ['audio', 'music'],
                        'K': ['interactive_exercise', 'game', 'simulation'],
                        'R': ['text', 'quiz']
                    }
                    
                    if style in style_content_types:
                        for content_type in style_content_types[style]:
                            if content_type in rl_content_types:
                                vark_alignment += (percentage / 100) * rl_content_types[content_type]['effectiveness']
                
                base_score += vark_alignment * 0.4
                if vark_alignment > 0.3:
                    template_reasoning.append(f"Alineación VARK: {vark_alignment:.2f}")
            
            # Score basado en capabilities del template
            if hasattr(template, 'capabilities') and template.capabilities:
                capability_bonus = 0
                for capability, enabled in template.capabilities.items():
                    if enabled and capability in ['audio', 'video', 'interactive']:
                        # Buscar si RL recomienda contenido que use esta capability
                        capability_content_map = {
                            'audio': ['audio', 'music'],
                            'video': ['video'],
                            'interactive': ['interactive_exercise', 'game', 'simulation']
                        }
                        
                        if capability in capability_content_map:
                            for content_type in capability_content_map[capability]:
                                if content_type in rl_content_types:
                                    capability_bonus += 0.1
                                    template_reasoning.append(f"Capability {capability} recomendada")
                
                base_score += capability_bonus
            
            # Score basado en variedad de actividades (evitar repetición)
            variety_bonus = min(0.2, len(template.style_tags) * 0.05) if hasattr(template, 'style_tags') else 0
            base_score += variety_bonus
            
            # Normalizar score
            final_score = min(1.0, base_score)
            
            scored_templates.append({
                'template': template,
                'score': final_score,
                'reasoning': template_reasoning,
                'rl_alignment': len([r for r in template_reasoning if 'VARK' in r or 'Capability' in r]) > 0
            })
        
        # Ordenar por score descendente
        scored_templates.sort(key=lambda x: x['score'], reverse=True)
        
        # Limitar resultados
        top_templates = scored_templates[:limit]
        
        # Preparar respuesta
        recommendations = []
        for item in top_templates:
            template = item['template']
            recommendations.append({
                'template': ensure_json_serializable(template.to_dict()),
                'recommendation_score': round(item['score'], 3),
                'reasoning': '; '.join(item['reasoning']) if item['reasoning'] else 'Plantilla compatible con perfil',
                'rl_aligned': item['rl_alignment']
            })
        
        return jsonify({
            "success": True,
            "data": {
                "recommendations": recommendations,
                "total_available": len(filtered_templates),
                "rl_confidence": round(confidence_score, 3),
                "rl_reasoning": reasoning,
                "fallback_mode": fallback_mode,
                "topic_subjects": topic_subjects
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error getting template recommendations: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/recommendations/<topic_id>', methods=['GET'])
@auth_required
def get_template_recommendations_for_topic(topic_id):
    """
    Endpoint auxiliar que provee recomendaciones de templates basadas en el topic.
    Usa la lógica existente de ContentService y TemplateRecommendationService.
    """
    try:
        # Validar topic_id
        try:
            ObjectId(topic_id)
        except Exception:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "topic_id debe ser un ObjectId válido"
            }), 400

        content_service = ContentService()
        recs = content_service.get_template_recommendations(topic_id=topic_id, student_id=None)

        # Asegurar formato
        recs_serializable = ensure_json_serializable(recs)

        return jsonify({
            "success": True,
            "data": recs_serializable
        }), 200

    except Exception as e:
        logging.error(f"Error in get_template_recommendations_for_topic for topic {topic_id}: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

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

# === MIGRATION ENDPOINTS (legacy games/simulations -> templates) ===

@template_bp.route('/migration/games', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def migration_suggestions_games():
    """
    Lista games legacy y provee sugerencias de templates equivalentes para migración.
    Query params:
      - topic_id (optional)
      - module_id (optional)
      - workspace_id (optional)
    """
    try:
        topic_id = request.args.get('topic_id')
        module_id = request.args.get('module_id')
        workspace_id = request.args.get('workspace_id')

        content_service = ContentService()
        # Use specialized helper to gather suggestions scoped to games
        suggestions = content_service.get_legacy_content_migration_suggestions(topic_id=topic_id, content_type=ContentTypes.GAME)

        return jsonify({
            "success": True,
            "data": suggestions
        }), 200

    except Exception as e:
        logging.error(f"Error in migration_suggestions_games: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/migration/simulations', methods=['GET'])
@auth_required
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def migration_suggestions_simulations():
    """
    Lista simulations legacy y provee sugerencias de templates equivalentes para migración.
    Query params:
      - topic_id (optional)
      - module_id (optional)
      - workspace_id (optional)
    """
    try:
        topic_id = request.args.get('topic_id')
        module_id = request.args.get('module_id')
        workspace_id = request.args.get('workspace_id')

        content_service = ContentService()
        suggestions = content_service.get_legacy_content_migration_suggestions(topic_id=topic_id, content_type=ContentTypes.SIMULATION)

        return jsonify({
            "success": True,
            "data": suggestions
        }), 200

    except Exception as e:
        logging.error(f"Error in migration_suggestions_simulations: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500

@template_bp.route('/migration/status', methods=['GET'])
@auth_required
def migration_status():
    """
    Reporte de estado general de migración por workspace.
    Query params:
      - workspace_id (optional) (if absent, jwts workspace will be used)
    """
    try:
        claims = get_jwt()
        default_workspace = claims.get('workspace_id')
        workspace_id = request.args.get('workspace_id') or default_workspace

        status = template_service.get_migration_status(workspace_id=workspace_id)

        return jsonify({
            "success": True,
            "data": status
        }), 200

    except Exception as e:
        logging.error(f"Error getting migration status: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Error interno del servidor"
        }), 500
