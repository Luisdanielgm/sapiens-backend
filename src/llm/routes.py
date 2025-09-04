from flask import Blueprint, request, jsonify
from src.llm.models import APIKeyValidationRequest, APIKeyValidationResponse
from src.llm.services import LLMValidationService
from src.shared.logging import get_logger
from pydantic import ValidationError

logger = get_logger(__name__)

# Create blueprint
llm_bp = Blueprint('llm', __name__)

@llm_bp.route('/validate/<provider>', methods=['POST'])
def validate_api_key(provider: str):
    """Validate API key for a specific LLM provider"""
    try:
        # Log the request
        logger.info(f"API key validation request for provider: {provider}")
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'valid': False,
                'message': 'No se proporcionaron datos en el request',
                'provider': provider
            }), 400
        
        # Validate request data
        try:
            validation_request = APIKeyValidationRequest(**data)
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return jsonify({
                'success': False,
                'valid': False,
                'message': f'Datos de request inválidos: {str(e)}',
                'provider': provider
            }), 400
        
        # Validate the API key
        result = LLMValidationService.validate_api_key(
            provider=provider,
            api_key=validation_request.apiKey,
            test_connection=True  # Always test connection
        )
        
        # Log the result
        logger.info(f"Validation result for {provider}: {result['valid']}")
        
        # Return response
        status_code = 200 if result['success'] else 500
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Unexpected error in validate_api_key: {str(e)}")
        return jsonify({
            'success': False,
            'valid': False,
            'message': f'Error interno del servidor: {str(e)}',
            'provider': provider
        }), 500

@llm_bp.route('/providers', methods=['GET'])
def get_supported_providers():
    """Get list of supported LLM providers"""
    try:
        return jsonify({
            'success': True,
            'providers': list(LLMValidationService.SUPPORTED_PROVIDERS),
            'message': 'Lista de proveedores soportados'
        }), 200
    except Exception as e:
        logger.error(f"Error getting supported providers: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }), 500

@llm_bp.route('/validate/<provider>/format', methods=['POST'])
def validate_api_key_format_only(provider: str):
    """Validate only the format of an API key without testing connection"""
    try:
        # Log the request
        logger.info(f"API key format validation request for provider: {provider}")
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'valid': False,
                'message': 'No se proporcionaron datos en el request',
                'provider': provider
            }), 400
        
        # Validate request data
        try:
            validation_request = APIKeyValidationRequest(**data)
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return jsonify({
                'success': False,
                'valid': False,
                'message': f'Datos de request inválidos: {str(e)}',
                'provider': provider
            }), 400
        
        # Validate only the format
        result = LLMValidationService.validate_api_key(
            provider=provider,
            api_key=validation_request.apiKey,
            test_connection=False  # Only format validation
        )
        
        # Log the result
        logger.info(f"Format validation result for {provider}: {result['valid']}")
        
        # Return response
        status_code = 200 if result['success'] else 500
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Unexpected error in validate_api_key_format_only: {str(e)}")
        return jsonify({
            'success': False,
            'valid': False,
            'message': f'Error interno del servidor: {str(e)}',
            'provider': provider
        }), 500