"""
Excepciones personalizadas para la aplicación.

Estas excepciones son capturadas por el decorador handle_errors en decorators.py
y convertidas automáticamente en respuestas JSON apropiadas.

Ejemplos de uso:
    # Lanzar una excepción básica
    raise AppException("Datos inválidos", 400)
    
    # Usar constantes predefinidas
    raise AppException("Usuario no encontrado", AppException.NOT_FOUND)
    
    # Incluir detalles adicionales
    raise AppException("Validación fallida", 400, {"campo": "El campo es obligatorio"})
"""

class AppException(Exception):
    """
    Excepción base para errores de la aplicación.
    
    Permite especificar un código HTTP personalizado y detalles adicionales.
    """
    
    # Códigos de error HTTP comunes
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_ERROR = 500
    
    def __init__(self, message: str, code: int = BAD_REQUEST, details: dict = None):
        """
        Inicializa una nueva excepción de aplicación.
        
        Args:
            message: Mensaje descriptivo del error
            code: Código HTTP de estado (por defecto 400)
            details: Diccionario con detalles adicionales del error
        """
        self.message = message
        self.code = code
        self.details = details
        super().__init__(self.message) 