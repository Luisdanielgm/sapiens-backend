"""
Rutas para el módulo de investigación profunda (deep research)
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
import logging

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.logging import log_info, log_error
from .services import DeepResearchService

# Crear blueprint
deep_research_bp = APIBlueprint('deep_research', __name__)

# Inicializar servicio
deep_research_service = DeepResearchService()

# Rutas de proxy para API externa de deep research
@deep_research_bp.route('/search', methods=['GET', 'POST'])
@APIRoute.standard(auth_required_flag=True)
def search():
    """
    Proxy para el endpoint /search de la API externa
    Realiza una búsqueda en la web, imagen, video o noticias
    """
    try:
        # Determinar si los parámetros vienen por GET o POST
        if request.method == 'GET':
            params = request.args.to_dict()
        else:
            params = request.get_json()
            
        # Validar parámetros requeridos
        if not params.get('provider'):
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "El parámetro 'provider' es requerido",
                status_code=400
            )
        
        if not params.get('q'):
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "El parámetro 'q' (consulta) es requerido",
                status_code=400
            )
            
        # Extraer parámetros específicos
        provider = params.pop('provider')
        query = params.pop('q')
        search_type = params.pop('search_type', 'web')
        
        # Realizar búsqueda
        success, results = deep_research_service.search(provider, query, search_type, **params)
        
        if success:
            return APIRoute.success(data=results)
        else:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                results.get('error', 'Error en la búsqueda'),
                details=results.get('details'),
                status_code=500
            )
    except Exception as e:
        log_error(f"Error en búsqueda: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/search/unified', methods=['GET', 'POST'])
@APIRoute.standard(auth_required_flag=True)
def search_unified():
    """
    Proxy para el endpoint /search/unified de la API externa
    Realiza una búsqueda combinada (web, imagen, video)
    """
    try:
        # Determinar si los parámetros vienen por GET o POST
        if request.method == 'GET':
            params = request.args.to_dict()
        else:
            params = request.get_json()
            
        # Validar parámetros requeridos
        if not params.get('provider'):
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "El parámetro 'provider' es requerido",
                status_code=400
            )
        
        if not params.get('q'):
            return APIRoute.error(
                ErrorCodes.MISSING_FIELDS,
                "El parámetro 'q' (consulta) es requerido",
                status_code=400
            )
            
        # Extraer parámetros específicos
        provider = params.pop('provider')
        query = params.pop('q')
        
        # Realizar búsqueda unificada
        success, results = deep_research_service.search_unified(provider, query, **params)
        
        if success:
            return APIRoute.success(data=results)
        else:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                results.get('error', 'Error en la búsqueda unificada'),
                details=results.get('details'),
                status_code=500
            )
    except Exception as e:
        log_error(f"Error en búsqueda unificada: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/extract', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['url'])
def extract():
    """
    Proxy para el endpoint /extract de la API externa
    Extrae el contenido textual de una URL
    """
    try:
        data = request.get_json()
        url = data.get('url')
        
        success, result = deep_research_service.extract_content(url)
        
        if success:
            return APIRoute.success(data=result)
        else:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                result.get('error', 'Error al extraer contenido'),
                details=result.get('details'),
                status_code=500
            )
    except Exception as e:
        log_error(f"Error al extraer contenido: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/ai/format', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['raw_content'])
def format_content():
    """
    Proxy para el endpoint /ai/format de la API externa
    Formatea texto crudo en Markdown legible
    """
    try:
        data = request.get_json()
        raw_content = data.get('raw_content')
        
        success, result = deep_research_service.format_content(raw_content)
        
        if success:
            return APIRoute.success(data=result)
        else:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                result.get('error', 'Error al formatear contenido'),
                details=result.get('details'),
                status_code=500
            )
    except Exception as e:
        log_error(f"Error al formatear contenido: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/ai/suggest-questions', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['text_block'])
def suggest_questions():
    """
    Proxy para el endpoint /ai/suggest-questions de la API externa
    Genera preguntas sugeridas basadas en un texto
    """
    try:
        data = request.get_json()
        text_block = data.get('text_block')
        
        success, result = deep_research_service.suggest_questions(text_block)
        
        if success:
            return APIRoute.success(data=result)
        else:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                result.get('error', 'Error al sugerir preguntas'),
                details=result.get('details'),
                status_code=500
            )
    except Exception as e:
        log_error(f"Error al sugerir preguntas: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/ai/process', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['task', 'params'])
def ai_process():
    """
    Proxy para el endpoint /ai/process de la API externa
    Procesa una tarea de IA para Deep Research
    """
    try:
        data = request.get_json()
        task = data.get('task')
        params = data.get('params')
        
        # Validar que params sea un objeto
        if not isinstance(params, dict):
            return APIRoute.error(
                ErrorCodes.INVALID_DATA,
                "El campo 'params' debe ser un objeto",
                status_code=400
            )
        
        success, result = deep_research_service.ai_process(task, params)
        
        if success:
            return APIRoute.success(data=result)
        else:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                result.get('error', f'Error al procesar tarea IA: {task}'),
                details=result.get('details'),
                status_code=500
            )
    except Exception as e:
        log_error(f"Error en proceso IA: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para administración de sesiones de investigación
@deep_research_bp.route('/session', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['topic'])
def create_session():
    """
    Crea una nueva sesión de investigación profunda
    """
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        
        topic = data.get('topic')
        format_requirements = data.get('format_requirements')
        topic_id = data.get('topic_id')
        
        success, result = deep_research_service.create_session(
            user_id=user_id,
            topic=topic,
            format_requirements=format_requirements,
            topic_id=topic_id
        )
        
        if success:
            return APIRoute.success(
                data={"session_id": result},
                message="Sesión de investigación creada exitosamente",
                status_code=201
            )
        else:
            return APIRoute.error(
                ErrorCodes.CREATION_ERROR,
                result,
                status_code=400
            )
    except Exception as e:
        log_error(f"Error al crear sesión: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/session/<session_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_session(session_id):
    """
    Obtiene una sesión de investigación por ID
    """
    try:
        session = deep_research_service.get_session(session_id)
        
        if not session:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND,
                "Sesión de investigación no encontrada",
                status_code=404
            )
        
        return APIRoute.success(data=session)
    except Exception as e:
        log_error(f"Error al obtener sesión: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/session/<session_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True)
def update_session(session_id):
    """
    Actualiza una sesión de investigación
    """
    try:
        data = request.get_json()
        
        # Remover campos que no se deben actualizar manualmente
        if 'user_id' in data:
            del data['user_id']
        if 'created_at' in data:
            del data['created_at']
        
        success, message = deep_research_service.update_session(session_id, data)

        if success:
            return APIRoute.success(
                data={"session_id": session_id, "operation": "update"},
                message=message,
            )
        else:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND,
                message,
                status_code=404
            )
    except Exception as e:
        log_error(f"Error al actualizar sesión: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@deep_research_bp.route('/session/<session_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True)
def delete_session(session_id):
    """
    Elimina una sesión de investigación
    """
    try:
        success, message = deep_research_service.delete_session(session_id)

        if success:
            return APIRoute.success(
                data={"session_id": session_id, "deleted": True},
                message=message,
            )
        else:
            return APIRoute.error(
                ErrorCodes.RESOURCE_NOT_FOUND,
                message,
                status_code=404
            )
    except Exception as e:
        log_error(f"Error al eliminar sesión: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Ruta específica para actualizar theory_content de un topic con el resultado de deep research
@deep_research_bp.route('/update-topic-content', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], required_fields=['topic_id', 'content'])
def update_topic_theory():
    """
    Actualiza el contenido teórico de un tema con el resultado de la investigación profunda
    """
    try:
        data = request.get_json()
        topic_id = data.get('topic_id')
        content = data.get('content')
        
        success, message = deep_research_service.update_topic_theory_content(topic_id, content)

        if success:
            return APIRoute.success(
                data={"topic_id": topic_id, "updated": True},
                message="Contenido teórico actualizado exitosamente",
            )
        else:
            return APIRoute.error(
                ErrorCodes.UPDATE_ERROR,
                message,
                status_code=400
            )
    except Exception as e:
        log_error(f"Error al actualizar theory content: {str(e)}", e, "deep_research.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 