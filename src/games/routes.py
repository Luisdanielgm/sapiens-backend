from flask import request
from datetime import datetime
from bson.objectid import ObjectId
import logging

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.database import get_db
from src.shared.utils import ensure_json_serializable
from .services import GameService, VirtualGameService, GameTemplateService, GameResultService

# Crear blueprint
games_bp = APIBlueprint('games', __name__, url_prefix='/api/games')

# Inicializar servicios
game_service = GameService()
virtual_game_service = VirtualGameService()

# Rutas para Juegos
@games_bp.route('', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]],
    required_fields=['topic_id', 'title', 'description', 'game_type', 'code']
)
def create_game():
    """Crea un nuevo juego educativo"""
    try:
        data = request.get_json()
        data['creator_id'] = request.user_id  # Añadir ID del creador
        
        success, result = game_service.create_game(data)
        
        if success:
            return APIRoute.success(
                data={"game_id": result},
                message="Juego creado exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/<game_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_game(game_id):
    """Obtiene un juego por su ID"""
    try:
        game = game_service.get_game(game_id)
        if game:
            return APIRoute.success(data={"game": game})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Juego no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/<game_id>', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def update_game(game_id):
    """Actualiza un juego existente"""
    try:
        data = request.get_json()
        success, message = game_service.update_game(game_id, data)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/<game_id>', methods=['DELETE'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"], ROLES["ADMIN"]]
)
def delete_game(game_id):
    """Elimina un juego existente"""
    try:
        success, message = game_service.delete_game(game_id)
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.DELETE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/topic/<topic_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_games_by_topic(topic_id):
    """Obtiene todos los juegos asociados a un tema"""
    try:
        games = game_service.get_games_by_topic(topic_id)
        return APIRoute.success(data={"games": games})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Rutas para Juegos Virtuales
@games_bp.route('/virtual', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['game_id', 'virtual_topic_id', 'student_id', 'adaptations']
)
def create_virtual_game():
    """Crea una nueva instancia virtual de juego para un estudiante"""
    try:
        data = request.get_json()
        success, result = virtual_game_service.create_virtual_game(data)
        
        if success:
            return APIRoute.success(
                data={"virtual_game_id": result},
                message="Juego virtual creado exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/virtual/<virtual_game_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_virtual_game(virtual_game_id):
    """Obtiene un juego virtual por su ID"""
    try:
        virtual_game = virtual_game_service.get_virtual_game(virtual_game_id)
        if virtual_game:
            return APIRoute.success(data={"virtual_game": virtual_game})
        return APIRoute.error(
            ErrorCodes.NOT_FOUND,
            "Juego virtual no encontrado",
            status_code=404
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/virtual/student/<student_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_games(student_id):
    """Obtiene todos los juegos virtuales de un estudiante"""
    try:
        games = virtual_game_service.get_student_games(student_id)
        return APIRoute.success(data={"games": games})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/virtual/<virtual_game_id>/progress', methods=['PUT'])
@APIRoute.standard(
    auth_required_flag=True,
    required_fields=['completion_status', 'score']
)
def update_game_progress(virtual_game_id):
    """Actualiza el progreso de un juego virtual"""
    try:
        data = request.get_json()
        
        success, message = virtual_game_service.update_game_progress(
            virtual_game_id,
            data['completion_status'],
            float(data['score'])
        )
        
        if success:
            return APIRoute.success(message=message)
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            message,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/templates', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_game_templates():
    """Lista plantillas de juegos disponibles, opcionalmente filtradas por tipo"""
    try:
        game_type = request.args.get('type')
        tags = request.args.getlist('tag')
        
        template_service = GameTemplateService()
        templates = template_service.list_templates(
            game_type=game_type, 
            tags=tags if tags else None
        )
        
        return APIRoute.success(data=templates)
    except Exception as e:
        logging.error(f"Error al listar plantillas de juegos: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/templates', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]], 
                  required_fields=['name', 'game_type', 'description', 'template_schema', 'default_code'])
def create_game_template():
    """Crea una nueva plantilla de juego"""
    try:
        data = request.get_json()
        
        # Añadir ID del creador
        if request.user_id:
            data['creator_id'] = request.user_id
            
        template_service = GameTemplateService()
        success, result = template_service.create_template(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Plantilla creada exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al crear plantilla de juego: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/templates/<template_id>', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_game_template(template_id):
    """Obtiene una plantilla de juego por su ID"""
    try:
        template_service = GameTemplateService()
        template = template_service.get_template(template_id)
        
        if not template:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Plantilla no encontrada",
                status_code=404
            )
            
        return APIRoute.success(data=template)
    except Exception as e:
        logging.error(f"Error al obtener plantilla de juego: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/templates/<template_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"], ROLES["INSTITUTE_ADMIN"]])
def update_game_template(template_id):
    """Actualiza una plantilla de juego existente"""
    try:
        data = request.get_json()
        template_service = GameTemplateService()
        success, result = template_service.update_template(template_id, data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            message="Plantilla actualizada exitosamente"
        )
    except Exception as e:
        logging.error(f"Error al actualizar plantilla de juego: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/generate', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]], 
                  required_fields=['template_id', 'topic_id', 'template_variables'])
def generate_game_from_template():
    """Genera un juego basado en una plantilla"""
    try:
        data = request.get_json()
        template_id = data.get('template_id')
        topic_id = data.get('topic_id')
        template_variables = data.get('template_variables')
        
        # Añadir ID del creador
        creator_id = request.user_id
        
        template_service = GameTemplateService()
        success, result = template_service.generate_game_from_template(
            template_id=template_id,
            topic_id=topic_id,
            template_variables=template_variables,
            creator_id=creator_id
        )
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Juego generado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al generar juego desde plantilla: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/results', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['virtual_game_id', 'student_id'])
def record_game_result():
    """Registra el resultado de una sesión de juego"""
    try:
        data = request.get_json()
        
        # Si no se proporciona fecha, usar fecha actual
        if 'session_date' not in data:
            data['session_date'] = datetime.now()
            
        result_service = GameResultService()
        success, result = result_service.record_result(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Resultado registrado exitosamente",
            status_code=201
        )
    except Exception as e:
        logging.error(f"Error al registrar resultado de juego: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/student/<student_id>/results', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_game_results(student_id):
    """Obtiene resultados de juegos de un estudiante"""
    try:
        virtual_game_id = request.args.get('virtual_game_id')
        
        result_service = GameResultService()
        results = result_service.get_student_results(
            student_id=student_id,
            virtual_game_id=virtual_game_id
        )
        
        return APIRoute.success(data=results)
    except Exception as e:
        logging.error(f"Error al obtener resultados de juegos: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/student/<student_id>/analytics', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def get_student_game_analytics(student_id):
    """Obtiene análisis de aprendizaje basado en resultados de juegos"""
    try:
        topic_id = request.args.get('topic_id')
        
        result_service = GameResultService()
        analytics = result_service.get_learning_analytics(
            student_id=student_id,
            topic_id=topic_id
        )
        
        return APIRoute.success(data=analytics)
    except Exception as e:
        logging.error(f"Error al obtener análisis de aprendizaje: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@games_bp.route('/personalize', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['game_id', 'virtual_topic_id', 'student_id'])
def personalize_game():
    """Crea o actualiza un juego personalizado para un estudiante"""
    try:
        data = request.get_json()
        game_id = data.get('game_id')
        virtual_topic_id = data.get('virtual_topic_id')
        student_id = data.get('student_id')
        adaptations = data.get('adaptations', {})
        
        # Verificar que el juego existe
        game_service = GameService()
        game = game_service.get_game(game_id)
        if not game:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Juego no encontrado",
                status_code=404
            )
            
        # Verificar que el tema virtual existe
        virtual_topic = get_db().virtual_topics.find_one({"_id": ObjectId(virtual_topic_id)})
        if not virtual_topic:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Tema virtual no encontrado",
                status_code=404
            )
            
        # Verificar que el estudiante existe
        student = get_db().users.find_one({"_id": ObjectId(student_id)})
        if not student:
            return APIRoute.error(
                ErrorCodes.NOT_FOUND,
                "Estudiante no encontrado",
                status_code=404
            )
            
        # Verificar si ya existe un juego virtual para este juego y estudiante
        existing = get_db().virtual_games.find_one({
            "game_id": ObjectId(game_id),
            "student_id": ObjectId(student_id),
            "virtual_topic_id": ObjectId(virtual_topic_id)
        })
        
        if existing:
            # Actualizar juego virtual existente
            update_data = {
                "adaptations": adaptations,
                "updated_at": datetime.now()
            }
            
            # Si se proporciona código personalizado, actualizarlo
            if "code" in data:
                update_data["code"] = data["code"]
                
            result = get_db().virtual_games.update_one(
                {"_id": existing["_id"]},
                {"$set": update_data}
            )
            
            return APIRoute.success(
                {"id": str(existing["_id"])},
                message="Juego personalizado actualizado",
                status_code=200
            )
        else:
            # Crear nuevo juego virtual
            virtual_game_data = {
                "game_id": game_id,
                "virtual_topic_id": virtual_topic_id,
                "student_id": student_id,
                "adaptations": adaptations
            }
            
            # Si se proporciona código personalizado, utilizarlo
            if "code" in data:
                virtual_game_data["code"] = data["code"]
                
            success, result = game_service.create_virtual_game(virtual_game_data)
            
            if not success:
                return APIRoute.error(
                    ErrorCodes.BAD_REQUEST,
                    result,
                    status_code=400
                )
                
            return APIRoute.success(
                {"id": result},
                message="Juego personalizado creado exitosamente",
                status_code=201
            )
    except Exception as e:
        logging.error(f"Error al personalizar juego: {str(e)}")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Ruta para convertir un juego en TopicContent
@games_bp.route('/<game_id>/convert-to-content', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["TEACHER"]]
)
def convert_game_to_content(game_id):
    """Convierte un juego existente en contenido asociado al tema"""
    success, content_id = game_service.convert_game_to_content(game_id)
    if success:
        return APIRoute.success(
            data={"content_id": content_id},
            message="Contenido creado desde juego",
            status_code=201
        )
    return APIRoute.error(
        ErrorCodes.CREATION_ERROR,
        content_id,
        status_code=400
    )

@games_bp.route('/<game_id>/toggle-evaluation', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["TEACHER"]])
def toggle_game_evaluation_status(game_id):
    """Activa o desactiva el marcador 'is_evaluation' de un juego."""
    success, message, new_status = game_service.toggle_evaluation_status(game_id)
    
    if success:
        return APIRoute.success(data={"is_evaluation": new_status}, message=message)
    else:
        status_code = 404 if "no encontrado" in message else 400
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR, 
            message, 
            status_code=status_code
        ) 