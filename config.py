import os
from dotenv import load_dotenv

load_dotenv()

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
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
    
    # Logging
    # Valores posibles: 'none', 'basic', 'detailed'
    API_LOGGING = os.getenv('API_LOGGING', 'basic')


class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo"""
    DEBUG = True


class ProductionConfig(Config):
    """Configuración para entorno de producción"""
    DEBUG = False


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
active_config = config_by_name[os.getenv('FLASK_ENV', 'development')]