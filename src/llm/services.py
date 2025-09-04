import re
import requests
from typing import Dict, Tuple
from src.shared.logging import get_logger

logger = get_logger(__name__)

class LLMValidationService:
    """Service for validating LLM provider API keys"""
    
    # Supported providers
    SUPPORTED_PROVIDERS = {
        'openai', 'anthropic', 'gemini', 'groq', 
        'replicate', 'requesty', 'openrouter'
    }
    
    # API key format patterns
    API_KEY_PATTERNS = {
        'openai': r'^sk-[a-zA-Z0-9]{48,}$',
        'anthropic': r'^sk-ant-[a-zA-Z0-9\-_]{95,}$',
        'gemini': r'^[a-zA-Z0-9\-_]{39}$',
        'groq': r'^gsk_[a-zA-Z0-9]{52}$',
        'replicate': r'^r8_[a-zA-Z0-9]{40}$',
        'requesty': r'^[a-zA-Z0-9\-_]{32,}$',
        'openrouter': r'^sk-or-v1-[a-zA-Z0-9]{64}$'
    }
    
    # Test endpoints for validation
    TEST_ENDPOINTS = {
        'openai': 'https://api.openai.com/v1/models',
        'anthropic': 'https://api.anthropic.com/v1/messages',
        'gemini': 'https://generativelanguage.googleapis.com/v1/models',
        'groq': 'https://api.groq.com/openai/v1/models',
        'replicate': 'https://api.replicate.com/v1/models',
        'requesty': None,  # Custom endpoint, format validation only
        'openrouter': 'https://openrouter.ai/api/v1/models'
    }
    
    @classmethod
    def validate_provider(cls, provider: str) -> bool:
        """Check if provider is supported"""
        return provider.lower() in cls.SUPPORTED_PROVIDERS
    
    @classmethod
    def validate_api_key_format(cls, provider: str, api_key: str) -> Tuple[bool, str]:
        """Validate API key format for a specific provider"""
        provider = provider.lower()
        
        if not cls.validate_provider(provider):
            return False, f"Proveedor '{provider}' no soportado"
        
        if not api_key or not api_key.strip():
            return False, "API key no puede estar vacía"
        
        pattern = cls.API_KEY_PATTERNS.get(provider)
        if not pattern:
            return False, f"Patrón de validación no definido para {provider}"
        
        if not re.match(pattern, api_key.strip()):
            return False, f"Formato de API key inválido para {provider}"
        
        return True, "Formato de API key válido"
    
    @classmethod
    def test_api_key_connection(cls, provider: str, api_key: str) -> Tuple[bool, str]:
        """Test API key by making a simple request to the provider"""
        provider = provider.lower()
        endpoint = cls.TEST_ENDPOINTS.get(provider)
        
        if not endpoint:
            return True, "Validación de conexión no disponible para este proveedor"
        
        try:
            headers = cls._get_auth_headers(provider, api_key)
            
            # Make a simple GET request to test the key
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, "API key válida y funcional"
            elif response.status_code == 401:
                return False, "API key inválida o sin permisos"
            elif response.status_code == 403:
                return False, "API key sin permisos suficientes"
            else:
                return False, f"Error de conexión: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Timeout al conectar con el proveedor"
        except requests.exceptions.ConnectionError:
            return False, "Error de conexión con el proveedor"
        except Exception as e:
            logger.error(f"Error testing API key for {provider}: {str(e)}")
            return False, f"Error inesperado: {str(e)}"
    
    @classmethod
    def _get_auth_headers(cls, provider: str, api_key: str) -> Dict[str, str]:
        """Get authentication headers for each provider"""
        base_headers = {
            'User-Agent': 'SapiensAI/1.0',
            'Content-Type': 'application/json'
        }
        
        if provider == 'openai':
            base_headers['Authorization'] = f'Bearer {api_key}'
        elif provider == 'anthropic':
            base_headers['x-api-key'] = api_key
            base_headers['anthropic-version'] = '2023-06-01'
        elif provider == 'gemini':
            # Gemini uses API key as query parameter, but we'll add it to headers for consistency
            base_headers['Authorization'] = f'Bearer {api_key}'
        elif provider == 'groq':
            base_headers['Authorization'] = f'Bearer {api_key}'
        elif provider == 'replicate':
            base_headers['Authorization'] = f'Token {api_key}'
        elif provider == 'openrouter':
            base_headers['Authorization'] = f'Bearer {api_key}'
            base_headers['HTTP-Referer'] = 'https://sapiensai.com'
            base_headers['X-Title'] = 'SapiensAI'
        
        return base_headers
    
    @classmethod
    def validate_api_key(cls, provider: str, api_key: str, test_connection: bool = True) -> Dict:
        """Complete API key validation including format and optional connection test"""
        try:
            # Validate provider
            if not cls.validate_provider(provider):
                return {
                    'success': True,
                    'valid': False,
                    'message': f"Proveedor '{provider}' no soportado",
                    'provider': provider
                }
            
            # Validate format
            format_valid, format_message = cls.validate_api_key_format(provider, api_key)
            if not format_valid:
                return {
                    'success': True,
                    'valid': False,
                    'message': format_message,
                    'provider': provider
                }
            
            # Test connection if requested
            if test_connection:
                connection_valid, connection_message = cls.test_api_key_connection(provider, api_key)
                return {
                    'success': True,
                    'valid': connection_valid,
                    'message': connection_message,
                    'provider': provider
                }
            else:
                return {
                    'success': True,
                    'valid': True,
                    'message': format_message,
                    'provider': provider
                }
                
        except Exception as e:
            logger.error(f"Error validating API key for {provider}: {str(e)}")
            return {
                'success': False,
                'valid': False,
                'message': f"Error interno: {str(e)}",
                'provider': provider
            }