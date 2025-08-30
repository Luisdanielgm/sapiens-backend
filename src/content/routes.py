from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
import logging
import datetime

from src.shared.decorators import role_required
from src.shared.database import get_db
from src.shared.standardization import APIRoute, ErrorCodes
from src.content.services import (
    ContentService,
    ContentTypeService,
    VirtualContentService,
    ContentResultService,
)
from src.content.template_integration_service import TemplateIntegrationService
from src.shared.constants import ROLES

content_bp = Blueprint('content', __name__, url_prefix='/api/content')

# Servicios
content_service = ContentService()
content_type_service = ContentTypeService()
virtual_content_service = VirtualContentService()
content_result_service = ContentResultService()
template_integration_service = TemplateIntegrationService()

# ============================================
# ENDPOINTS DE TIPOS DE CONTENIDO
# ============================================

@content_bp.route('/types', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["ADMIN"]])
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_content():
    """
    Crea contenido de cualquier tipo (game, simulation, quiz, diagram, slide, etc.)
    
    Body:
    {
        "topic_id": "ObjectId",
        "content_type": "game|simulation|quiz|diagram|text|video|slide|...",
        "title": "Título del contenido",
        "description": "Descripción",
        "content_data": {...},  // Contenido específico según tipo
        "interactive_config": {...},  // Para tipos interactivos
        "difficulty": "easy|medium|hard",
        "estimated_duration": 15,
        "learning_objectives": [...],
        "tags": [...],
        "resources": [...],
        "generation_prompt": "...",  // Para contenido generado por IA
        "order": 1,  // Orden secuencial del contenido (opcional)
        "parent_content_id": "ObjectId"  // ID del contenido padre (opcional)
    }
    """
    try:
        data = request.json
        data['creator_id'] = request.user_id
        
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
@APIRoute.standard(auth_required_flag=True)
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


@content_bp.route('/topic/<topic_id>/type/<content_type>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_topic_content_by_type(topic_id, content_type):
    """Obtiene el contenido de un tema filtrado por tipo"""
    try:
        contents = content_service.get_topic_content(topic_id, content_type)
        return APIRoute.success(data={"contents": contents})
    except Exception as e:
        logging.error(f"Error obteniendo contenido por tipo: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/interactive', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
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

@content_bp.route('/<content_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_content_by_id(content_id):
    """
    Obtiene un contenido específico por su ID.
    """
    try:
        content = content_service.get_content(content_id)
        if not content:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Contenido no encontrado",
                status_code=404,
            )
        return APIRoute.success(data={"content": content})
    except Exception as e:
        logging.error(f"Error obteniendo contenido: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
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
@APIRoute.standard(auth_required_flag=True)
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
        student_id = data.get('student_id', request.user_id)
        
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
@APIRoute.standard(auth_required_flag=True)
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
@APIRoute.standard(auth_required_flag=True)
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
        data['student_id'] = data.get('student_id', request.user_id)
        
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
@APIRoute.standard(auth_required_flag=True)
def get_student_results(student_id):
    """
    Obtiene resultados de un estudiante.
    Query params: 
        - virtual_content_id (filtrar por contenido virtual específico - clave principal)
        - content_type (filtrar por tipo de contenido - para compatibilidad)
    """
    try:
        # Verificar permisos: solo el mismo estudiante o profesores/admin
        current_user = get_jwt_identity()
        if current_user != student_id and not g.user.get('role') in [ROLES["TEACHER"], ROLES["ADMIN"]]:
            return APIRoute.error(
                ErrorCodes.PERMISSION_DENIED,
                "No autorizado para ver estos resultados",
                status_code=403,
            )
        
        virtual_content_id = request.args.get('virtual_content_id')
        content_type = request.args.get('content_type')
        
        results = content_result_service.get_student_results(
            student_id, 
            virtual_content_id=virtual_content_id,
            content_type=content_type
        )

        return APIRoute.success(data={"results": results})
        
    except Exception as e:
        logging.error(f"Error obteniendo resultados del estudiante: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/results/my', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_game_legacy():
    """
    DEPRECATED - Endpoint de compatibilidad para crear juegos.
    
    Este endpoint será eliminado en la próxima versión.
    Usar: POST /api/content/ con content_type="game"
    
    Redirige al endpoint unificado con content_type="game"
    """
    import warnings
    warnings.warn(
        "El endpoint /api/content/games está obsoleto. Usar /api/content/ con content_type='game'",
        DeprecationWarning,
        stacklevel=2
    )
    
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_simulation_legacy():
    """
    DEPRECATED - Endpoint de compatibilidad para crear simulaciones.
    
    Este endpoint será eliminado en la próxima versión.
    Usar: POST /api/content/ con content_type="simulation"
    """
    import warnings
    warnings.warn(
        "El endpoint /api/content/simulations está obsoleto. Usar /api/content/ con content_type='simulation'",
        DeprecationWarning,
        stacklevel=2
    )
    
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
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def create_quiz_legacy():
    """
    DEPRECATED - Endpoint de compatibilidad para crear quizzes.
    
    Este endpoint será eliminado en la próxima versión.
    Usar: POST /api/content/ con content_type="quiz"
    """
    import warnings
    warnings.warn(
        "El endpoint /api/content/quizzes está obsoleto. Usar /api/content/ con content_type='quiz'",
        DeprecationWarning,
        stacklevel=2
    )
    
    try:
        data = request.json
        data['content_type'] = 'quiz'
        data['creator_id'] = request.user_id
        
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
# ENDPOINTS DE INTEGRACIÓN CON PLANTILLAS
# ============================================

@content_bp.route('/from-template', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def create_content_from_template():
    """
    Crea contenido basado en una plantilla.
    
    Body:
    {
        "template_id": "template_id",
        "topic_id": "topic_id", 
        "props": {"param1": "value1"},
        "assets": [{"id": "asset1", "name": "imagen.jpg", "url": "...", "type": "image"}],
        "learning_mix": {"V": 70, "A": 10, "K": 15, "R": 5},
        "content_type": "diagram" // opcional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Datos requeridos")
        
        # Validar campos requeridos
        required_fields = ["template_id", "topic_id"]
        for field in required_fields:
            if field not in data:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Campo requerido: {field}")
        
        # Crear contenido desde plantilla
        success, result = template_integration_service.create_content_from_template(
            template_id=data["template_id"],
            topic_id=data["topic_id"],
            props=data.get("props"),
            assets=data.get("assets"),
            learning_mix=data.get("learning_mix"),
            content_type=data.get("content_type")
        )
        
        if success:
            return APIRoute.success(
                data={"content_id": result},
                message="Contenido creado desde plantilla exitosamente"
            )
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, result)
            
    except Exception as e:
        logging.error(f"Error creando contenido desde plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/template-data', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_template_content_data(content_id):
    """
    Obtiene datos enriquecidos de contenido basado en plantilla.
    """
    try:
        content = template_integration_service.get_template_content(content_id)
        
        if not content:
            return APIRoute.error(ErrorCodes.NOT_FOUND, "Contenido no encontrado", status_code=404)
        
        return APIRoute.success(data={"content": content})
        
    except Exception as e:
        logging.error(f"Error obteniendo datos de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/template-update', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def update_template_content(content_id):
    """
    Actualiza contenido basado en plantilla.
    
    Body:
    {
        "props": {"param1": "new_value"},
        "assets": [...],
        "learning_mix": {...},
        "status": "active"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Datos requeridos")
        
        success, message = template_integration_service.update_template_content(content_id, data)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error actualizando contenido de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/template-publish', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def publish_template_content(content_id):
    """
    Publica contenido basado en plantilla.
    """
    try:
        success, message = template_integration_service.publish_template_content(content_id)
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error publicando contenido de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/templates/available/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_available_templates_for_topic(topic_id):
    """
    Obtiene plantillas disponibles para usar en un tema.
    """
    try:
        user_id = get_jwt_identity()
        
        templates = template_integration_service.get_available_templates_for_topic(topic_id, user_id)
        
        return APIRoute.success(data={
            "templates": templates,
            "total": len(templates)
        })
        
    except Exception as e:
        logging.error(f"Error obteniendo plantillas disponibles: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<content_id>/migrate-to-template', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
@role_required([ROLES["TEACHER"], ROLES["ADMIN"]])
def migrate_content_to_template(content_id):
    """
    Migra contenido legacy existente para usar una plantilla.
    
    Body:
    {
        "template_id": "template_id"
    }
    """
    try:
        data = request.get_json()
        
        if not data or "template_id" not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "template_id requerido")
        
        success, message = template_integration_service.migrate_content_to_template(
            content_id, data["template_id"]
        )
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error migrando contenido a plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# ============================================
# ENDPOINTS DE RECOMENDACIONES DE PLANTILLAS
# ============================================

@content_bp.route('/topic/<topic_id>/template-recommendations', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_template_recommendations(topic_id):
    """
    Obtiene recomendaciones de plantillas para cada diapositiva de un tema.
    
    Query params:
        student_id: ID del estudiante (opcional, para personalización futura)
    """
    try:
        student_id = request.args.get('student_id')
        
        recommendations = content_service.get_template_recommendations(
            topic_id=topic_id,
            student_id=student_id
        )
        
        return APIRoute.success(data={
            "recommendations": recommendations,
            "topic_id": topic_id
        })
        
    except Exception as e:
        logging.error(f"Error obteniendo recomendaciones de plantillas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/topic/<topic_id>/apply-template-recommendations', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def apply_template_recommendations(topic_id):
    """
    Aplica recomendaciones de plantillas a las diapositivas de un tema.
    
    Body:
    {
        "recommendations": {
            "slide_id_1": "template_id_1",
            "slide_id_2": "template_id_2"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data or "recommendations" not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "Campo 'recommendations' requerido")
        
        recommendations = data["recommendations"]
        
        success, message = content_service.apply_template_recommendations(
            topic_id=topic_id,
            recommendations=recommendations
        )
        
        if success:
            return APIRoute.success(message=message)
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, message)
            
    except Exception as e:
        logging.error(f"Error aplicando recomendaciones de plantillas: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/slide/<slide_id>/template-compatibility/<template_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_slide_template_compatibility(slide_id, template_id):
    """
    Analiza la compatibilidad entre una diapositiva y una plantilla específica.
    """
    try:
        compatibility = content_service.get_slide_template_compatibility(
            slide_id=slide_id,
            template_id=template_id
        )
        
        return APIRoute.success(data={
            "compatibility": compatibility,
            "slide_id": slide_id,
            "template_id": template_id
        })
        
    except Exception as e:
        logging.error(f"Error analizando compatibilidad de plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/<virtual_content_id>/complete-auto', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def mark_content_complete_auto(virtual_content_id):
    """
    Marca automáticamente un contenido virtual como completado al 100%.
    Se usa para contenidos de solo lectura que no requieren interacción del usuario.

    Path params:
        virtual_content_id: ID del contenido virtual a marcar como completado
    """
    try:
        user_id = get_jwt_identity()

        # Validar que el virtual_content_id sea válido
        if not ObjectId.is_valid(virtual_content_id):
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "ID de contenido virtual inválido")

        # Buscar el contenido virtual
        db = get_db()
        virtual_content = db.virtual_topic_contents.find_one({
            "_id": ObjectId(virtual_content_id),
            "student_id": ObjectId(user_id)
        })

        if not virtual_content:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Contenido virtual no encontrado o no pertenece al usuario"
            )

        # Verificar que no esté ya completado
        interaction_tracking = virtual_content.get("interaction_tracking", {}) or {}
        if interaction_tracking.get("completion_status") == "completed":
            return APIRoute.success(
                message="El contenido ya estaba marcado como completado",
                data={"already_completed": True}
            )

        # Actualizar el estado de completitud
        update_data = {
            "interaction_tracking": {
                **interaction_tracking,
                "completion_status": "completed",
                "completion_percentage": 100.0,
                "completed_at": datetime.now()
            },
            "updated_at": datetime.now()
        }

        # Actualizar en la base de datos
        result = db.virtual_topic_contents.update_one(
            {"_id": ObjectId(virtual_content_id)},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            return APIRoute.error(
                ErrorCodes.SERVER_ERROR,
                "No se pudo actualizar el estado del contenido"
            )

        logging.info(f"Contenido virtual {virtual_content_id} marcado como completado automáticamente")

        return APIRoute.success(
            message="Contenido marcado como completado exitosamente",
            data={
                "virtual_content_id": virtual_content_id,
                "completion_percentage": 100.0,
                "completion_status": "completed"
            }
        )

    except Exception as e:
        logging.error(f"Error marcando contenido como completado: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/template-feedback', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def submit_template_feedback():
    """
    Envía feedback sobre el uso de plantillas al sistema de RL.
    """
    try:
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['student_id', 'topic_id', 'slide_id', 'template_id', 
                          'engagement_score', 'completion_score', 'satisfaction_score']
        
        for field in required_fields:
            if field not in data:
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"Campo requerido faltante: {field}")
        
        # Validar rangos de scores (0.0 - 1.0)
        score_fields = ['engagement_score', 'completion_score', 'satisfaction_score']
        for field in score_fields:
            if not (0.0 <= data[field] <= 1.0):
                return APIRoute.error(ErrorCodes.VALIDATION_ERROR, f"{field} debe estar entre 0.0 y 1.0")
        
        success = content_service.submit_template_feedback(
            data['student_id'], data['topic_id'], data['slide_id'],
            data['template_id'], data['engagement_score'],
            data['completion_score'], data['satisfaction_score']
        )
        
        if success:
            return APIRoute.success(message="Feedback enviado exitosamente al sistema de RL")
        else:
            return APIRoute.error(ErrorCodes.BUSINESS_LOGIC_ERROR, "Error al enviar feedback al sistema de RL")
            
    except Exception as e:
        logging.error(f"Error submitting template feedback: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

# Rutas para contenido embebido vs separado
@content_bp.route('/embedding/analyze', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def analyze_embedding_strategy():
    """
    Analiza si un contenido debe ser embebido o separado de una diapositiva.
    """
    try:
        data = request.get_json()
        
        if 'slide_id' not in data or 'content_id' not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "slide_id y content_id son requeridos")
        
        analysis = content_service.analyze_content_embedding_strategy(
            data['slide_id'], data['content_id']
        )
        
        return APIRoute.success(data={"analysis": analysis})
        
    except Exception as e:
        logging.error(f"Error analyzing embedding strategy: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/embed', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def embed_content():
    """
    Embebe un contenido dentro de una diapositiva.
    """
    try:
        data = request.get_json()
        
        if 'slide_id' not in data or 'content_id' not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "slide_id y content_id son requeridos")
        
        embed_position = data.get('embed_position', 'bottom')
        
        result = content_service.embed_content_in_slide(
            data['slide_id'], data['content_id'], embed_position
        )
        
        return APIRoute.success(data={"result": result})
        
    except Exception as e:
        logging.error(f"Error embedding content: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/extract', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["ADMIN"]])
def extract_embedded_content():
    """
    Extrae un contenido embebido y lo convierte en contenido separado.
    """
    try:
        data = request.get_json()
        
        if 'slide_id' not in data or 'content_id' not in data:
            return APIRoute.error(ErrorCodes.VALIDATION_ERROR, "slide_id y content_id son requeridos")
        
        result = content_service.extract_embedded_content(
            data['slide_id'], data['content_id']
        )
        
        return APIRoute.success(data={"result": result})
        
    except Exception as e:
        logging.error(f"Error extracting embedded content: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/recommendations/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_embedding_recommendations(topic_id):
    """
    Obtiene recomendaciones de embedding para todos los contenidos de un tema.
    """
    try:
        recommendations = content_service.get_embedding_recommendations(topic_id)
        
        return APIRoute.success(data={"recommendations": recommendations})
        
    except Exception as e:
        logging.error(f"Error getting embedding recommendations: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )

@content_bp.route('/embedding/statistics/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_embedding_statistics(topic_id):
    """
    Obtiene estadísticas de embedding para un tema.
    """
    try:
        statistics = content_service.get_embedding_statistics(topic_id)
        
        return APIRoute.success(data={"statistics": statistics})
        
    except Exception as e:
        logging.error(f"Error getting embedding statistics: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            "Error interno del servidor",
            status_code=500,
        )