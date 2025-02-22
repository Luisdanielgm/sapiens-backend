from flask import Blueprint, jsonify, request
from app.utils.decorators import handle_errors
from database.indigenous_languages.translations import (
    create_translation,
    get_translations,
    update_translation,
    delete_translation,
    bulk_create_translations,
    get_available_language_pairs,
    search_translations,
    validate_language_pair
)

translations_bp = Blueprint('translations', __name__)

@translations_bp.route('/translations', methods=['POST'])
@handle_errors
def create_translation_endpoint():
    """Crea una nueva traducción"""
    data = request.get_json()
    required_fields = ['español', 'traduccion', 'dialecto', 'language_pair', 'type_data']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    # Validar formato de language_pair
    if not validate_language_pair(data['language_pair']):
        return jsonify({"error": "Formato inválido de language_pair"}), 400
        
    translation_id = create_translation(**{k: data[k] for k in required_fields})
    return jsonify({
        "message": "Traducción creada exitosamente",
        "translation_id": translation_id
    }), 201

@translations_bp.route('/translations/bulk', methods=['POST'])
@handle_errors
def bulk_create_translations_endpoint():
    """Crea múltiples traducciones"""
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({"error": "Se espera una lista de traducciones"}), 400
        
    translation_ids = bulk_create_translations(data)
    return jsonify({
        "message": f"{len(translation_ids)} traducciones creadas exitosamente",
        "translation_ids": translation_ids
    }), 201

@translations_bp.route('/translations', methods=['GET'])
@handle_errors
def get_translations_endpoint():
    """Obtiene traducciones con filtros opcionales"""
    language_pair = request.args.get('language_pair')
    type_data = request.args.get('type_data')
    dialecto = request.args.get('dialecto')
    
    translations = get_translations(language_pair, type_data, dialecto)
    return jsonify({"translations": translations}), 200

@translations_bp.route('/translations/<translation_id>', methods=['PUT'])
@handle_errors
def update_translation_endpoint(translation_id):
    """Actualiza una traducción existente"""
    data = request.get_json()
    success = update_translation(translation_id, data)
    
    if success:
        return jsonify({"message": "Traducción actualizada exitosamente"}), 200
    return jsonify({"error": "No se pudo actualizar la traducción"}), 400

@translations_bp.route('/translations/<translation_id>', methods=['DELETE'])
@handle_errors
def delete_translation_endpoint(translation_id):
    """Elimina una traducción"""
    success = delete_translation(translation_id)
    
    if success:
        return jsonify({"message": "Traducción eliminada exitosamente"}), 200
    return jsonify({"error": "No se pudo eliminar la traducción"}), 400

@translations_bp.route('/language-pairs', methods=['GET'])
@handle_errors
def get_language_pairs_endpoint():
    """Obtiene los pares de idiomas disponibles"""
    pairs = get_available_language_pairs()
    return jsonify({"language_pairs": pairs}), 200

@translations_bp.route('/translations/search', methods=['GET'])
@handle_errors
def search_translations_endpoint():
    """Búsqueda avanzada de traducciones"""
    query = request.args.get('q')
    
    filters = {
        "language_pair": request.args.get('language_pair'),
        "type_data": request.args.get('type_data'),
        "dialecto": request.args.get('dialecto'),
        "created_at": request.args.get('created_at'),
        "updated_at": request.args.get('updated_at')
    }
    
    # Eliminar filtros None o vacíos
    filters = {k: v for k, v in filters.items() if v is not None and v != ''}
    
    print("Filtros recibidos:", filters)  # Debug
    
    translations = search_translations(query, filters)
    
    return jsonify({
        "translations": translations,
        "count": len(translations),
        "filters_applied": filters  # Incluir los filtros aplicados en la respuesta
    }), 200 