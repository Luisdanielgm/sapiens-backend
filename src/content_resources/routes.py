from flask import request, jsonify
import logging
import os
from datetime import datetime
import json

from src.shared.standardization import APIBlueprint, APIRoute, ErrorCodes
from src.shared.constants import ROLES
from src.shared.logging import log_info, log_error
from .services import WebSearchService, SearchProviderService

# Crear blueprint
content_resources_bp = APIBlueprint('content_resources', __name__)

# Inicializar servicios
web_search_service = WebSearchService()
provider_service = SearchProviderService()

# Rutas para búsqueda web
@content_resources_bp.route('/web-search', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, required_fields=['query'])
def search_web():
    """Realiza una búsqueda en la web utilizando SearXNG"""
    try:
        data = request.get_json()
        query = data.get('query')
        result_type = data.get('result_type')
        max_results = data.get('max_results', 10)
        topic_id = data.get('topic_id')
        
        log_info(f"Realizando búsqueda web: {query}", "content_resources.routes")
        
        results = web_search_service.search_web(
            query=query,
            result_type=result_type,
            max_results=max_results,
            topic_id=topic_id
        )
        
        return APIRoute.success(data=results)
    except Exception as e:
        log_error(f"Error al buscar en la web: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/web-search/result/<result_id>/save', methods=['POST'])
@APIRoute.standard(auth_required_flag=True)
def save_search_result(result_id):
    """Marca un resultado de búsqueda como guardado"""
    try:
        log_info(f"Guardando resultado de búsqueda: {result_id}", "content_resources.routes")
        
        success, message = web_search_service.save_search_result(result_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            message="Resultado guardado exitosamente"
        )
    except Exception as e:
        log_error(f"Error al guardar resultado de búsqueda: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers', methods=['GET'])
@APIRoute.standard(auth_required_flag=True)
def list_search_providers():
    """Lista proveedores de búsqueda SearXNG"""
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        log_info(f"Listando proveedores de búsqueda (active_only: {active_only})", "content_resources.routes")
        
        providers = provider_service.list_providers(active_only)
        return APIRoute.success(data=providers)
    except Exception as e:
        log_error(f"Error al listar proveedores de búsqueda: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]], required_fields=['name'])
def create_search_provider():
    """Crea un nuevo proveedor de búsqueda SearXNG"""
    try:
        data = request.get_json()
        
        # Asegurar que es de tipo searxng
        data["provider_type"] = "searxng"
        
        log_info(f"Creando proveedor de búsqueda: {data.get('name')}", "content_resources.routes")
        
        # Validar campos
        if not data.get("instances") and not os.path.exists(os.path.join(os.path.dirname(__file__), 'verified_searxng_instances.json')):
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No se encontraron instancias verificadas. Proporcione una lista de instancias.",
                status_code=400
            )
            
        success, result = provider_service.create_provider(data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {"id": result},
            message="Proveedor SearXNG creado exitosamente",
            status_code=201
        )
    except Exception as e:
        log_error(f"Error al crear proveedor de búsqueda: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/<provider_id>', methods=['PUT'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def update_search_provider(provider_id):
    """Actualiza un proveedor de búsqueda existente"""
    try:
        data = request.get_json()
        
        log_info(f"Actualizando proveedor de búsqueda: {provider_id}", "content_resources.routes")
        
        # Evitar cambio de tipo de proveedor
        if "provider_type" in data:
            del data["provider_type"]
            
        success, message = provider_service.update_provider(provider_id, data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            message="Proveedor actualizado exitosamente"
        )
    except Exception as e:
        log_error(f"Error al actualizar proveedor de búsqueda: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/<provider_id>', methods=['DELETE'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def delete_search_provider(provider_id):
    """Elimina un proveedor de búsqueda"""
    try:
        log_info(f"Eliminando proveedor de búsqueda: {provider_id}", "content_resources.routes")
        
        success, message = provider_service.delete_provider(provider_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            message="Proveedor eliminado exitosamente"
        )
    except Exception as e:
        log_error(f"Error al eliminar proveedor de búsqueda: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/<provider_id>/test', methods=['GET'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def test_search_provider(provider_id):
    """Prueba la conexión con un proveedor de búsqueda SearXNG"""
    try:
        log_info(f"Probando proveedor de búsqueda: {provider_id}", "content_resources.routes")
        
        success, message, results = provider_service.test_provider(provider_id)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                message,
                status_code=400
            )
            
        return APIRoute.success(
            data=results,
            message=message
        )
    except Exception as e:
        log_error(f"Error al probar proveedor de búsqueda: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        )

@content_resources_bp.route('/search-providers/setup-searxng', methods=['POST'])
@APIRoute.standard(auth_required_flag=True, roles=[ROLES["INSTITUTE_ADMIN"]])
def setup_searxng_provider():
    """Configura automáticamente un proveedor SearXNG con instancias verificadas"""
    try:
        log_info("Configurando proveedor SearXNG automáticamente", "content_resources.routes")
        
        # Cargar instancias verificadas desde el archivo JSON
        instances_file = os.path.join(os.path.dirname(__file__), 'verified_searxng_instances.json')
        if not os.path.exists(instances_file):
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "Archivo de instancias verificadas no encontrado",
                status_code=400
            )
            
        with open(instances_file, 'r') as f:
            verified_instances = json.load(f)
        
        if not verified_instances:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                "No hay instancias verificadas disponibles",
                status_code=400
            )
            
        # Crear los datos del proveedor
        provider_data = {
            "name": "SearXNG Instancias Verificadas",
            "provider_type": "searxng",
            "instances": verified_instances,
            "config": {
                "language": "all",
                "safesearch": 0,
                "max_instances_per_query": 5
            }
        }
        
        # Crear el proveedor
        success, result = provider_service.create_provider(provider_data)
        
        if not success:
            return APIRoute.error(
                ErrorCodes.BAD_REQUEST,
                result,
                status_code=400
            )
            
        return APIRoute.success(
            {
                "provider_id": result,
                "instances_count": len(verified_instances)
            },
            message="Proveedor SearXNG configurado exitosamente",
            status_code=201
        )
    except Exception as e:
        log_error(f"Error al configurar proveedor SearXNG: {str(e)}", e, "content_resources.routes")
        return APIRoute.error(
            ErrorCodes.SERVER_ERROR,
            str(e),
            status_code=500
        ) 