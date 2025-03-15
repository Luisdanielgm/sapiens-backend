import logging
from flask import current_app, has_app_context

def get_logger(name: str = None) -> logging.Logger:
    """
    Obtiene un logger configurado para el módulo especificado.
    Si estamos en un contexto de Flask, usa el logger de la aplicación.
    
    Args:
        name: Nombre del módulo o servicio que solicita el logger
        
    Returns:
        logging.Logger: Logger configurado
    """
    if has_app_context():
        return current_app.logger
    else:
        return logging.getLogger(name)

def log_error(message: str, error: Exception = None, module: str = None):
    """
    Registra un mensaje de error en el log.
    
    Args:
        message: Mensaje descriptivo del error
        error: Excepción que causó el error (opcional)
        module: Nombre del módulo donde ocurrió el error (opcional)
    """
    logger = get_logger(module)
    if error:
        logger.error(f"{message}: {str(error)}")
    else:
        logger.error(message)

def log_info(message: str, module: str = None):
    """
    Registra un mensaje informativo en el log.
    
    Args:
        message: Mensaje informativo
        module: Nombre del módulo donde se genera la información (opcional)
    """
    logger = get_logger(module)
    logger.info(message)

def log_warning(message: str, module: str = None):
    """
    Registra un mensaje de advertencia en el log.
    
    Args:
        message: Mensaje de advertencia
        module: Nombre del módulo donde se genera la advertencia (opcional)
    """
    logger = get_logger(module)
    logger.warning(message)

def log_debug(message: str, module: str = None):
    """
    Registra un mensaje de depuración en el log.
    
    Args:
        message: Mensaje de depuración
        module: Nombre del módulo donde se genera el mensaje (opcional)
    """
    logger = get_logger(module)
    logger.debug(message) 