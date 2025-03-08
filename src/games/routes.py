from flask import request

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import GameService, VirtualGameService

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