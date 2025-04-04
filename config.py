import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# Configurar logger
logger = logging.getLogger(__name__)

# Variables de entorno requeridas para producción
REQUIRED_ENV_VARS = ['MONGO_DB_URI', 'DB_NAME', 'JWT_SECRET']

def validate_env_vars():
    """
    Valida que las variables de entorno requeridas estén configuradas.
    En producción, la aplicación no debería iniciarse si faltan variables críticas.
    """
    # Solo validar en producción
    if os.getenv('FLASK_ENV') != 'production':
        return True
        
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Faltan variables de entorno requeridas: {', '.join(missing_vars)}")
        return False
    return True

class Config:
    """Configuración base para la aplicación"""
    # Base de datos
    MONGO_DB_URI = os.getenv('MONGO_DB_URI')
    DB_NAME = os.getenv('DB_NAME')
    INDIGENOUS_DB_NAME = os.getenv('INDIGENOUS_DB_NAME', 'indigenous_languages')
    
    # JWT (Autenticación)
    JWT_SECRET_KEY = os.getenv('JWT_SECRET', 'develop-secret-key')
    # Configuración específica de flask-jwt-extended
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_EXPIRATION_HOURS', 24)) * 3600  # En segundos
    
    # Servidor
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    PORT = int(os.getenv('PORT', 5000))
    
    # CORS
    # Formato de CORS_ORIGINS: "http://ejemplo1.com,http://ejemplo2.com"
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'localhost://3000').split(',')
    
    # Logging
    # Valores posibles: 'none', 'basic', 'detailed'
    API_LOGGING = os.getenv('API_LOGGING', 'basic')
    
    @classmethod
    def validate(cls):
        """Valida que la configuración sea correcta"""
        if cls.MONGO_DB_URI is None:
            logger.warning("MONGO_DB_URI no está configurado. La conexión a la base de datos puede fallar.")
        if cls.DB_NAME is None:
            logger.warning("DB_NAME no está configurado. Se usará el valor por defecto.")
        if cls.JWT_SECRET_KEY == 'develop-secret-key':
            logger.warning("JWT_SECRET tiene el valor por defecto. Esto es inseguro en producción.")


class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo"""
    DEBUG = True


class ProductionConfig(Config):
    """Configuración para entorno de producción"""
    DEBUG = False
    
    @classmethod
    def validate(cls):
        super().validate()
        if not validate_env_vars():
            logger.critical("Faltan variables de entorno críticas en entorno de producción")
            # En producción, fallar si faltan variables críticas
            if os.getenv('ENFORCE_ENV_VALIDATION', '0') == '1':
                sys.exit(1)


class TestingConfig(Config):
    """Configuración para entorno de pruebas"""
    TESTING = True
    DEBUG = True
    # Se puede usar una base de datos de prueba
    DB_NAME = os.getenv('TEST_DB_NAME', 'sapiensai_test')


# Diccionario para seleccionar la configuración según el entorno
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

# Obtener la configuración activa
env = os.getenv('FLASK_ENV', 'development')
active_config = config_by_name[env]

# Validar configuración
active_config.validate()