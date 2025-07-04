from flask import request
from bson import ObjectId
from datetime import datetime
from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from .services import (
    TranslationService, 
    LanguageService, 
    VerificadorService, 
    VerificacionService
)

indigenous_languages_bp = APIBlueprint('translations', __name__)

translation_service = TranslationService()
language_service = LanguageService()
verificador_service = VerificadorService()
verificacion_service = VerificacionService()

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
        
        # Parámetros de verificación
        min_verificaciones = request.args.get('min_verificaciones')
        verificador_id = request.args.get('verificador_id')
        include_verificaciones = request.args.get('include_verificaciones', 'false').lower() == 'true'
        
        # Preparar filtros
        filters = {}
        if min_verificaciones:
            try:
                filters['min_verificaciones'] = int(min_verificaciones)
            except ValueError:
                pass
                
        if verificador_id:
            filters['verificador_id'] = verificador_id
            
        if include_verificaciones:
            filters['include_verificaciones'] = True
        
        translations = translation_service.get_translations(
            language_pair=language_pair,
            type_data=type_data,
            dialecto=dialecto,
            filters=filters
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
            
            # Filtros de fecha para created_at
            'created_at': request.args.get('created_at'),
            'desde_created': request.args.get('desde_created') or request.args.get('desde'),
            'hasta_created': request.args.get('hasta_created') or request.args.get('hasta'),
            
            # Filtros de fecha para updated_at
            'updated_at': request.args.get('updated_at'),
            'desde_updated': request.args.get('desde_updated'),
            'hasta_updated': request.args.get('hasta_updated'),
            
            # Filtros de verificaciones
            'min_verificaciones': request.args.get('min_verificaciones'),
            'verificador_id': request.args.get('verificador_id'),
            'include_verificaciones': request.args.get('include_verificaciones', 'false').lower() == 'true'
        }
        
        # Eliminar filtros vacíos
        filters = {k: v for k, v in filters.items() if v is not None}
        
        # Convertir min_verificaciones a entero si existe
        if 'min_verificaciones' in filters:
            try:
                filters['min_verificaciones'] = int(filters['min_verificaciones'])
            except ValueError:
                del filters['min_verificaciones']
        
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
            return APIRoute.success(data={"message": message}, message=message)
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
            return APIRoute.success(data={"message": message}, message=message)
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

# ========== ENDPOINTS PARA VERIFICADORES ==========

# Crear un nuevo verificador
@indigenous_languages_bp.route('/verificadores', methods=['POST'])
@APIRoute.standard(
    required_fields=['nombre', 'tipo', 'etnia']
)
def create_verificador_endpoint():
    """Crea un nuevo verificador"""
    try:
        data = request.get_json()
        success, result = verificador_service.create_verificador(data)
        
        if success:
            return APIRoute.success(
                data={"verificador_id": result},
                message="Verificador creado exitosamente",
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

# Obtener verificadores
@indigenous_languages_bp.route('/verificadores', methods=['GET'])
@APIRoute.standard()
def get_verificadores_endpoint():
    """Obtiene verificadores con filtros opcionales"""
    try:
        etnia = request.args.get('etnia')
        tipo = request.args.get('tipo')
        activo = request.args.get('activo', 'true').lower() == 'true'
        
        verificadores = verificador_service.get_verificadores(
            etnia=etnia,
            tipo=tipo,
            activo=activo
        )
        
        return APIRoute.success(data={"verificadores": verificadores})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Actualizar verificador
@indigenous_languages_bp.route('/verificadores/<verificador_id>', methods=['PUT'])
@APIRoute.standard()
def update_verificador_endpoint(verificador_id):
    """Actualiza un verificador existente"""
    try:
        updates = request.get_json()
        success, result = verificador_service.update_verificador(verificador_id, updates)
        
        if success:
            return APIRoute.success(
                message=result,
                status_code=200
            )
        return APIRoute.error(
            ErrorCodes.UPDATE_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Eliminar verificador
@indigenous_languages_bp.route('/verificadores/<verificador_id>', methods=['DELETE'])
@APIRoute.standard()
def delete_verificador_endpoint(verificador_id):
    """Desactiva un verificador (no lo elimina físicamente)"""
    try:
        success, result = verificador_service.delete_verificador(verificador_id)
        
        if success:
            return APIRoute.success(
                message=result,
                status_code=200
            )
        return APIRoute.error(
            ErrorCodes.DELETION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# ========== ENDPOINTS PARA VERIFICACIONES ==========

# Añadir verificación a una traducción
@indigenous_languages_bp.route('/verificaciones', methods=['POST'])
@APIRoute.standard(
    required_fields=['translation_id', 'verificador_id']
)
def add_verificacion_endpoint():
    """Añade una verificación a una traducción"""
    try:
        data = request.get_json()
        success, result = verificacion_service.add_verificacion(data)
        
        if success:
            return APIRoute.success(
                data={"verificacion_id": result},
                message="Verificación añadida exitosamente",
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

# Obtener verificaciones de una traducción
@indigenous_languages_bp.route('/verificaciones/translation/<translation_id>', methods=['GET'])
@APIRoute.standard()
def get_verificaciones_by_translation_endpoint(translation_id):
    """Obtiene todas las verificaciones para una traducción específica"""
    try:
        verificaciones = verificacion_service.get_verificaciones_by_translation(translation_id)
        
        return APIRoute.success(data={"verificaciones": verificaciones})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Eliminar verificación
@indigenous_languages_bp.route('/verificaciones/<verificacion_id>', methods=['DELETE'])
@APIRoute.standard()
def remove_verificacion_endpoint(verificacion_id):
    """Elimina una verificación"""
    try:
        success, result = verificacion_service.remove_verificacion(verificacion_id)
        
        if success:
            return APIRoute.success(
                message=result,
                status_code=200
            )
        return APIRoute.error(
            ErrorCodes.DELETION_ERROR,
            result,
            status_code=400
        )
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

# Obtener traducciones más verificadas
@indigenous_languages_bp.route('/traducciones/top-verificadas', methods=['GET'])
@APIRoute.standard()
def get_top_verified_translations_endpoint():
    """Obtiene las traducciones con mayor número de verificaciones"""
    try:
        limit = int(request.args.get('limit', 10))
        translations = verificacion_service.get_top_verified_translations(limit=limit)
        
        return APIRoute.success(data={"translations": translations})
    except Exception as e:
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 