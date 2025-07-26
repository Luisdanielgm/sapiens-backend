from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
import logging

from src.shared.decorators import role_required
from src.shared.database import get_db
from src.shared.standardization import APIRoute, ErrorCodes
from src.content.services import (
    ContentService,
    ContentTypeService,
    VirtualContentService,
    ContentResultService,
    ContentGenerationService,
)
from src.shared.constants import ROLES

content_bp = Blueprint('content', __name__, url_prefix='/api/content')

# Servicios
content_service = ContentService()
content_type_service = ContentTypeService()
virtual_content_service = VirtualContentService()
content_result_service = ContentResultService()

# ============================================
# ENDPOINTS DE TIPOS DE CONTENIDO
# ============================================

@content_bp.route('/types', methods=['GET'])
@jwt_required()
def get_content_types():
    """
    Obtiene todos los tipos de contenido disponibles.
    Query params: subcategory
    """
    try:
        subcategory = request.args.get('subcategory')  # game, simulation, quiz, diagram, etc.

        content_types = content_type_service.get_content_types(subcategory)

        return APIRoute.success(data={"content_types": content_types})
        
    except Exception as e:
        logging.error(f"Error obteniendo tipos de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/types', methods=['POST'])
@jwt_required()
@role_required(['admin'])
def create_content_type():
    """
    Crea un nuevo tipo de contenido.
    """
    try:
        data = request.json
        
        success, result = content_type_service.create_content_type(data)
        
        if success:
            return APIRoute.success(
                data={"content_type_id": result},
                message="Tipo de contenido creado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando tipo de contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE CONTENIDO UNIFICADO
# ============================================

@content_bp.route('/', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_content():
    """
    Crea contenido de cualquier tipo (game, simulation, quiz, diagram, etc.)
    
    Body:
    {
        "topic_id": "ObjectId",
        "content_type": "game|simulation|quiz|diagram|text|video|...",
        "title": "Título del contenido",
        "description": "Descripción",
        "content_data": {...},  // Contenido específico según tipo
        "interactive_config": {...},  // Para tipos interactivos
        "difficulty": "easy|medium|hard",
        "estimated_duration": 15,
        "learning_objectives": [...],
        "tags": [...],
        "resources": [...],
        "generation_prompt": "..."  // Para contenido generado por IA
    }
    """
    try:
        data = request.json
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)

        if success:
            return APIRoute.success(
                data={"content_id": result},
                message="Contenido creado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>', methods=['GET'])
@jwt_required()
def get_topic_content(topic_id):
    """
    Obtiene todo el contenido de un tema.
    Query params: content_type (para filtrar por tipo específico)
    """
    try:
        content_type = request.args.get('content_type')
        
        contents = content_service.get_topic_content(topic_id, content_type)

        return APIRoute.success(data={"contents": contents})
        
    except Exception as e:
        logging.error(f"Error obteniendo contenido del tema: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/interactive', methods=['GET'])
@jwt_required()
def get_interactive_content(topic_id):
    """
    Obtiene solo contenido interactivo de un tema (games, simulations, quizzes).
    """
    try:
        contents = content_service.get_interactive_content(topic_id)

        return APIRoute.success(data={"interactive_contents": contents})
        
    except Exception as e:
        logging.error(f"Error obteniendo contenido interactivo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>', methods=['PUT'])
@jwt_required()
@role_required(['professor', 'admin'])
def update_content(content_id):
    """
    Actualiza contenido existente.
    """
    try:
        data = request.json
        
        success, result = content_service.update_content(content_id, data)

        if success:
            return APIRoute.success(data={"message": result})
        else:
            return APIRoute.error(ErrorCodes.UPDATE_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error actualizando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>', methods=['DELETE'])
@jwt_required()
@role_required(['professor', 'admin'])
def delete_content(content_id):
    """
    Elimina contenido (soft delete).
    """
    try:
        success, result = content_service.delete_content(content_id)

        if success:
            return APIRoute.success(data={"message": result})
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, result, status_code=404)
            
    except Exception as e:
        logging.error(f"Error eliminando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE CONTENIDO PERSONALIZADO
# ============================================

@content_bp.route('/personalize', methods=['POST'])
@jwt_required()
def personalize_content():
    """
    Personaliza contenido para un estudiante específico.
    
    Body:
    {
        "virtual_topic_id": "ObjectId",
        "content_id": "ObjectId",
        "student_id": "ObjectId",  // Opcional, por defecto usuario actual
        "cognitive_profile": {...}  // Opcional, se obtiene de BD si no se proporciona
    }
    """
    try:
        data = request.json
        student_id = data.get('student_id', get_jwt_identity())
        
        # Obtener perfil cognitivo si no se proporciona
        cognitive_profile = data.get('cognitive_profile')
        if not cognitive_profile:
            profile = get_db().cognitive_profiles.find_one({"user_id": ObjectId(student_id)})
            if profile:
                cognitive_profile = profile
            else:
                return APIRoute.error(
                    ErrorCodes.NOT_FOUND,
                    "No se encontró perfil cognitivo para el estudiante",
                    status_code=404,
                )
        
        success, result = virtual_content_service.personalize_content(
            data['virtual_topic_id'],
            data['content_id'],
            student_id,
            cognitive_profile
        )

        if success:
            return APIRoute.success(
                data={"virtual_content_id": result},
                message="Contenido personalizado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error personalizando contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/interaction', methods=['POST'])
@jwt_required()
def track_interaction():
    """
    Registra interacción con contenido personalizado.
    
    Body:
    {
        "virtual_content_id": "ObjectId",
        "interaction_data": {
            "time_spent": 120,  // segundos
            "completion_percentage": 75.5,
            "completion_status": "in_progress|completed",
            "score": 85.0,  // Para contenido evaluable
            "interactions": [...]  // Detalles específicos de interacción
        }
    }
    """
    try:
        data = request.json
        
        success = virtual_content_service.track_interaction(
            data['virtual_content_id'],
            data['interaction_data']
        )

        if success:
            return APIRoute.success(
                data={"message": "Interacción registrada exitosamente"},
                message="Interacción registrada exitosamente",
            )
        else:
            return APIRoute.error(
                ErrorCodes.OPERATION_FAILED,
                "Error registrando interacción",
            )
            
    except Exception as e:
        logging.error(f"Error registrando interacción: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE RESULTADOS UNIFICADOS
# ============================================

@content_bp.route('/results', methods=['POST'])
@jwt_required()
def record_result():
    """
    Registra resultado de interacción con contenido (game, simulation, quiz, etc.)
    
    Body:
    {
        "virtual_content_id": "ObjectId",
        "student_id": "ObjectId",  // Opcional, por defecto usuario actual
        "session_data": {
            "score": 88.5,
            "completion_percentage": 95.0,
            "time_spent": 420,
            "content_specific_data": {...}  // Datos específicos según tipo de contenido
        },
        "learning_metrics": {
            "effectiveness": 0.87,
            "engagement": 0.92,
            "mastery_improvement": 0.15
        },
        "feedback": "Excelente trabajo...",
        "session_type": "completion|practice|assessment"
    }
    """
    try:
        data = request.json
        data['student_id'] = data.get('student_id', get_jwt_identity())
        
        success, result = content_result_service.record_result(data)

        if success:
            return APIRoute.success(
                data={"result_id": result},
                message="Resultado registrado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error registrando resultado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/results/student/<student_id>', methods=['GET'])
@jwt_required()
def get_student_results(student_id):
    """
    Obtiene resultados de un estudiante.
    Query params: content_type (para filtrar por tipo específico)
    """
    try:
        # Verificar permisos: solo el mismo estudiante o profesores/admin
        current_user = get_jwt_identity()
        if current_user != student_id and not g.user.get('role') in ['professor', 'admin']:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No autorizado para ver estos resultados",
                status_code=403,
            )
        
        content_type = request.args.get('content_type')
        
        results = content_result_service.get_student_results(student_id, content_type)

        return APIRoute.success(data={"results": results})
        
    except Exception as e:
        logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/results/my', methods=['GET'])
@jwt_required()
def get_my_results():
    """
    Obtiene resultados del usuario actual.
    Query params: content_type
    """
    try:
        student_id = get_jwt_identity()
        content_type = request.args.get('content_type')
        
        results = content_result_service.get_student_results(student_id, content_type)

        return APIRoute.success(data={"results": results})
        
    except Exception as e:
        logging.error(f"Error obteniendo mis resultados: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE COMPATIBILIDAD (LEGACY)
# ============================================

@content_bp.route('/games', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_game_legacy():
    """
    Endpoint de compatibilidad para crear juegos.
    Redirige al endpoint unificado con content_type="game"
    """
    # TODO: evaluar eliminar este endpoint legacy tras refactor del frontend
    try:
        data = request.json
        data['content_type'] = 'game'
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)

        if success:
            return APIRoute.success(
                data={"game_id": result},
                message="Juego creado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando juego (legacy): {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/simulations', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_simulation_legacy():
    """
    Endpoint de compatibilidad para crear simulaciones.
    """
    # TODO: revisar si este endpoint legacy sigue siendo necesario
    try:
        data = request.json
        data['content_type'] = 'simulation'
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)

        if success:
            return APIRoute.success(
                data={"simulation_id": result},
                message="Simulación creada exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando simulación (legacy): {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/quizzes', methods=['POST'])
@jwt_required()
@role_required(['professor', 'admin'])
def create_quiz_legacy():
    """
    Endpoint de compatibilidad para crear quizzes.
    """
    # TODO: este endpoint es redundante con la ruta unificada
    try:
        data = request.json
        data['content_type'] = 'quiz'
        data['creator_id'] = get_jwt_identity()
        
        success, result = content_service.create_content(data)

        if success:
            return APIRoute.success(
                data={"quiz_id": result},
                message="Quiz creado exitosamente",
                status_code=201,
            )
        else:
            return APIRoute.error(ErrorCodes.CREATION_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando quiz (legacy): {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS PARA GENERACIÓN ASÍNCRONA DE CONTENIDO
# ============================================

generation_service = ContentGenerationService()

@content_bp.route('/generate-batch', methods=['POST'])
@jwt_required()
@role_required(ROLES["TEACHER"])
def generate_content_batch():
    """
    Inicia una tarea de generación de contenido en lote de forma asíncrona.
    
    Body:
    {
        "topic_id": "ObjectId",
        "content_types": ["slides", "diagram", "quiz"]
    }
    """
    try:
        data = request.json
        topic_id = data.get('topic_id')
        content_types = data.get('content_types')
        user_id = get_jwt_identity()

        if not topic_id or not content_types:
            return APIRoute.error(ErrorCodes.MISSING_FIELDS, "Se requieren topic_id y content_types.")

        success, result = generation_service.create_generation_task(topic_id, user_id, content_types)

        if success:
            return APIRoute.success(
                data={"task_id": result},
                message="Tarea de generación iniciada. Consulta el estado para ver el progreso.",
                status_code=202  # Accepted
            )
        else:
            return APIRoute.error(ErrorCodes.OPERATION_FAILED, result)
            
    except Exception as e:
        logging.error(f"Error en endpoint generate-batch: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor.")

@content_bp.route('/generation-task/<task_id>', methods=['GET'])
@jwt_required()
def get_generation_task_status(task_id):
    """
    Consulta el estado y progreso de una tarea de generación de contenido.
    """
    try:
        task_status = generation_service.get_task_status(task_id)

        if task_status:
            # Verificar que el usuario que consulta es quien creó la tarea (o un admin)
            user_id = get_jwt_identity()
            # Asumiendo que el rol está disponible en `g` gracias a un decorador
            user_roles = getattr(g, 'user_roles', []) 
            
            if str(task_status.get('user_id')) != user_id and ROLES["ADMIN"] not in user_roles:
                return APIRoute.error(ErrorCodes.PERMISSION_DENIED, "No tienes permiso para ver esta tarea.")

            return APIRoute.success(data=task_status)
        else:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Tarea de generación no encontrada.", status_code=404)
            
    except Exception as e:
        logging.error(f"Error en endpoint get_generation_task_status: {str(e)}")
        return APIRoute.error(ErrorCodes.SERVER_ERROR, "Error interno del servidor.")
