import logging
from flask import request, jsonify
from bson import ObjectId

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.database import get_db
from src.users.services import ProfileService
from .services import TopicResourceService
from src.resources.services import ResourceService

# Crear blueprint para el módulo topic_resources
topic_resources_bp = APIBlueprint('topic_resources', __name__)

# Instanciar servicios
topic_resource_service = TopicResourceService()
resource_service = ResourceService()

@topic_resources_bp.route('/<topic_id>/<resource_id>', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def link_resource_to_topic(topic_id, resource_id):
    """
    Vincula un recurso específico a un tema.
    
    Args:
        topic_id: ID del tema
        resource_id: ID del recurso a vincular
    
    Returns:
        Respuesta con el estado de la operación
    """
    data = request.get_json()
    current_user_id = request.user_id
    
    relevance_score = data.get("relevance_score", 0.5)
    recommended_for = data.get("recommended_for", [])
    usage_context = data.get("usage_context", "supplementary")
    content_types = data.get("content_types", [])
    
    success, result = topic_resource_service.link_resource_to_topic(
        topic_id=topic_id,
        resource_id=resource_id,
        relevance_score=relevance_score,
        recommended_for=recommended_for,
        usage_context=usage_context,
        content_types=content_types,
        created_by=current_user_id
    )
    
    if success:
        return APIRoute.success(
            data={"id": result},
            message="Recurso vinculado correctamente al tema"
        )
    else:
        return APIRoute.error(
            ErrorCodes.BAD_REQUEST,
            result,
            status_code=400
        )

@topic_resources_bp.route('/<topic_id>/<resource_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def unlink_resource_from_topic(topic_id, resource_id):
    """
    Desvincula un recurso de un tema.
    
    Args:
        topic_id: ID del tema
        resource_id: ID del recurso
    
    Returns:
        Respuesta con el estado de la operación
    """
    current_user_id = request.user_id
    
    success, message = topic_resource_service.unlink_resource_from_topic(topic_id, resource_id)
    
    if success:
        return APIRoute.success(
            data={"message": message},
            message=message
        )
    else:
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            message,
            status_code=404
        )

@topic_resources_bp.route('/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_resources(topic_id):
    """
    Obtiene todos los recursos asociados a un tema específico.
    
    Args:
        topic_id: ID del tema
    
    Returns:
        Lista de recursos asociados al tema
    """
    current_user_id = request.user_id
    content_type = request.args.get('content_type')
    usage_context = request.args.get('usage_context')
    personalized = request.args.get('personalized', 'false').lower() == 'true'
    
    # Obtener perfil cognitivo si es necesario para personalización
    cognitive_profile = None
    if personalized:
        profile_service = ProfileService()
        profile = profile_service.get_user_profile(current_user_id)
        if profile:
            cognitive_profile = profile.get("cognitive_profile", {})
    
    resources = topic_resource_service.get_topic_resources(
        topic_id=topic_id,
        cognitive_profile=cognitive_profile,
        content_type=content_type,
        usage_context=usage_context
    )
    
    return APIRoute.success(
        data=resources,
        message=f"Se encontraron {len(resources)} recursos para el tema"
    )

@topic_resources_bp.route('/by-resource/<resource_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_resource_topics(resource_id):
    """
    Obtiene todos los temas asociados a un recurso específico.
    
    Args:
        resource_id: ID del recurso
    
    Returns:
        Lista de temas asociados al recurso
    """
    current_user_id = request.user_id
    
    topics = topic_resource_service.get_resource_topics(resource_id)
    
    return APIRoute.success(
        data=topics,
        message=f"Se encontraron {len(topics)} temas para el recurso"
    ) 