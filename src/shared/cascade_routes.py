from flask import Blueprint, request, jsonify
from src.shared.cascade_deletion_service import CascadeDeletionService
from src.shared.decorators import auth_required
import logging

cascade_bp = Blueprint('cascade', __name__, url_prefix='/api/cascade')
logger = logging.getLogger(__name__)

@cascade_bp.route('/delete/<collection>/<entity_id>', methods=['DELETE'])
@auth_required
def delete_with_cascade(collection, entity_id):
    """
    Elimina una entidad y todas sus dependencias en cascada.
    
    Query params:
    - dry_run: Si es 'true', solo simula la eliminación
    """
    try:
        dry_run = request.args.get('dry_run', 'false').lower() == 'true'
        
        service = CascadeDeletionService()
        result = service.delete_with_cascade(collection, entity_id, dry_run=dry_run)
        
        if result['success']:
            status_code = 200 if dry_run else 200
            return jsonify(result), status_code
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in cascade deletion endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@cascade_bp.route('/cleanup/<collection>', methods=['POST'])
@auth_required
def cleanup_orphaned_data(collection):
    """
    Limpia datos huérfanos en una colección específica.
    
    Query params:
    - dry_run: Si es 'true', solo simula la limpieza
    """
    try:
        dry_run = request.args.get('dry_run', 'false').lower() == 'true'
        
        service = CascadeDeletionService()
        result = service.cleanup_orphaned_data(collection, dry_run=dry_run)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in cleanup endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@cascade_bp.route('/report/<collection>/<entity_id>', methods=['GET'])
@auth_required
def get_dependency_report(collection, entity_id):
    """
    Genera un reporte de dependencias para una entidad.
    """
    try:
        service = CascadeDeletionService()
        result = service.get_dependency_report(collection, entity_id)
        
        if 'error' in result:
            return jsonify(result), 400
        else:
            return jsonify(result), 200
            
    except Exception as e:
        logger.error(f"Error in dependency report endpoint: {str(e)}")
        return jsonify({
            'error': 'Internal server error'
        }), 500

@cascade_bp.route('/cleanup-all', methods=['POST'])
@auth_required
def cleanup_all_orphaned_data():
    """
    Limpia datos huérfanos en todas las colecciones.
    
    Query params:
    - dry_run: Si es 'true', solo simula la limpieza
    """
    try:
        dry_run = request.args.get('dry_run', 'false').lower() == 'true'
        
        # Lista de colecciones a limpiar
        collections_to_clean = [
            'content_results',
            'virtual_topic_contents',
            'virtual_topics',
            'virtual_modules',
            'evaluation_submissions',
            'evaluation_resources',
            'topic_contents',
            'student_performance',
            'evaluation_analytics',
            'class_statistics'
        ]
        
        service = CascadeDeletionService()
        results = {}
        total_cleaned = 0
        
        for collection in collections_to_clean:
            result = service.cleanup_orphaned_data(collection, dry_run=dry_run)
            results[collection] = result
            
            if result['success'] and not dry_run:
                total_cleaned += result.get('deleted_count', 0)
        
        return jsonify({
            'success': True,
            'dry_run': dry_run,
            'total_cleaned': total_cleaned,
            'results_by_collection': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error in cleanup all endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@cascade_bp.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint de salud para verificar que el servicio está funcionando.
    """
    return jsonify({
        'status': 'healthy',
        'service': 'cascade_deletion'
    }), 200