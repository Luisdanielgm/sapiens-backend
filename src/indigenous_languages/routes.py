from flask import request
from .services import TranslationService, LanguageService
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES

indigenous_languages_bp = APIBlueprint('translations', __name__)

translation_service = TranslationService()
language_service = LanguageService()

@indigenous_languages_bp.route('/translations', methods=['POST'])
@APIRoute.standard(
    required_fields=['español', 'traduccion', 'dialecto', 'language_pair', 'type_data']
)
def create_translation_endpoint():
    """Crea una nueva traducción"""
    try:
        data = request.get_json()
        
        # Validar formato de language_pair
        if not translation_service.validate_language_pair(data['language_pair']):
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "Formato inválido de language_pair",
                status_code=400
            )
            
        success, result = translation_service.create_translation(data)
        
        if success:
            return APIRoute.success(
                data={"translation_id": result},
                message="Traducción creada exitosamente",
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

@indigenous_languages_bp.route('/translations', methods=['GET'])
@APIRoute.standard()
def get_translations_endpoint():
    """Obtiene traducciones con filtros opcionales"""
    try:
        # Obtener parámetros
        language_pair = request.args.get('language_pair')
        type_data = request.args.get('type_data')
        dialecto = request.args.get('dialecto')
        
        translations = translation_service.get_translations(
            language_pair=language_pair,
            type_data=type_data,
            dialecto=dialecto
        )
        
        return APIRoute.success(data={"translations": translations})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@indigenous_languages_bp.route('/search', methods=['GET'])
@APIRoute.standard()
def search_translations_endpoint():
    """Busca traducciones según términos de búsqueda y filtros"""
    try:
        # Obtener término de búsqueda
        search_term = request.args.get('q', '')
        
        # Obtener filtros
        filters = {
            'language_pair': request.args.get('language_pair'),
            'type_data': request.args.get('type_data'),
            'dialecto': request.args.get('dialecto'),
            'desde': request.args.get('desde'),
            'hasta': request.args.get('hasta'),
        }
        
        # Eliminar filtros vacíos
        filters = {k: v for k, v in filters.items() if v}
        
        # Realizar búsqueda
        results = translation_service.search_translations(
            query=search_term,
            filters=filters
        )
        
        return APIRoute.success(data={"results": results})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@indigenous_languages_bp.route('/languages', methods=['GET'])
@APIRoute.standard()
def get_languages():
    """Obtiene la lista de idiomas indígenas disponibles"""
    try:
        languages = language_service.get_active_languages()
        return APIRoute.success(data={"languages": languages})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@indigenous_languages_bp.route('/language', methods=['POST'])
@APIRoute.standard(
    auth_required_flag=True,
    roles=[ROLES["ADMIN"]],
    required_fields=['name', 'code', 'region']
)
def add_language():
    """Añade un nuevo idioma indígena (solo administradores)"""
    try:
        data = request.get_json()
        success, result = language_service.add_language(data)
        
        if success:
            return APIRoute.success(
                data={"language_id": result},
                message="Idioma añadido exitosamente",
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

@indigenous_languages_bp.route('/bulk', methods=['POST'])
@APIRoute.standard(required_fields=['translations'])
def bulk_create_translations_endpoint():
    """Crea múltiples traducciones en una sola operación"""
    try:
        data = request.get_json()
        translations = data.get('translations', [])
        
        if not translations:
            return APIRoute.error(
                ErrorCodes.VALIDATION_ERROR,
                "No se proporcionaron traducciones",
                status_code=400
            )
            
        success, results = translation_service.bulk_create_translations(translations)
        
        if success:
            return APIRoute.success(
                data={"translation_ids": results},
                message="Traducciones creadas exitosamente",
                status_code=201
            )
        return APIRoute.error(
            ErrorCodes.CREATION_ERROR,
            results[0] if results else "Error al crear traducciones",
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@indigenous_languages_bp.route('/<translation_id>', methods=['PUT'])
@APIRoute.standard()
def update_translation_endpoint(translation_id):
    """Actualiza una traducción existente"""
    try:
        data = request.get_json()
        success, message = translation_service.update_translation(translation_id, data)
        
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

@indigenous_languages_bp.route('/<translation_id>', methods=['DELETE'])
@APIRoute.standard()
def delete_translation_endpoint(translation_id):
    """Elimina una traducción existente"""
    try:
        success, message = translation_service.delete_translation(translation_id)
        
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

@indigenous_languages_bp.route('/language-pairs', methods=['GET'])
@APIRoute.standard()
def get_language_pairs_endpoint():
    """Obtiene los pares de idiomas disponibles"""
    try:
        pairs = translation_service.get_available_language_pairs()
        return APIRoute.success(data={"language_pairs": pairs})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 